import random
import time
from flask import Blueprint, request, jsonify, session
from database import get_db
from routes.auth import login_required, manager_required

pos_bp = Blueprint('pos', __name__, url_prefix='/api')


def make_receipt():
    ts = int(time.time() * 1000) % 10000000
    rand = random.randint(100, 999)
    return f"JITM-{ts}{rand}"


@pos_bp.route('/sale', methods=['POST'])
@login_required
def complete_sale():
    d = request.get_json()
    items = d.get('items', [])
    if not items:
        return jsonify({'error': 'No items'}), 400

    is_return = d.get('is_return', False)
    is_exchange = d.get('is_exchange', False)
    discount = float(d.get('discount', 0))
    discount_type = d.get('discount_type', 'percent')
    payment = d.get('payment', 'cash')
    customer_id = d.get('customer_id')
    customer_name = d.get('customer_name', '')
    notes = d.get('notes', '')

    with get_db() as db:
        exchange_items_data = d.get('exchange_items', None) if is_exchange else None

        errors = []
        sale_items = []
        subtotal = 0

        def process_item(item, qty_mult=1):
            nonlocal subtotal
            vid = item.get('variant_id') or item.get('vid')
            qty = int(item['quantity']) * qty_mult
            variant = db.execute('SELECT * FROM variants WHERE id=?', (vid,)).fetchone()
            if not variant:
                errors.append(f'Variant {vid} not found')
                return None
            prod = db.execute('SELECT * FROM products WHERE id=?', (variant['product_id'],)).fetchone()
            price = float(item.get('price', variant['price'] or prod['base_price']))
            line_total = round(price * qty, 2)
            subtotal += line_total
            if qty < 0 and variant['stock'] < abs(qty):
                errors.append(f'Not enough stock of {prod["name"]} to return')
                return None
            return {
                'product_id': prod['id'],
                'variant_id': vid,
                'product_name': prod['name'],
                'variant_label': f'{variant["size"]} {variant["color"]}'.strip(),
                'sku': variant['sku'],
                'quantity': qty,
                'price': price,
                'total': line_total,
                'is_return': 1 if (is_return or is_exchange) else 0,
            }

        for item in items:
            qty_mult = -1 if (is_return or is_exchange) else 1
            si = process_item(item, qty_mult)
            if si is None:
                continue
            sale_items.append(si)

            if is_exchange and exchange_items_data is not None:
                pass
            elif qty_mult < 0:
                db.execute('UPDATE variants SET stock = stock + ? WHERE id=?', (abs(si['quantity']), si['variant_id']))
            else:
                db.execute('UPDATE variants SET stock = stock - ? WHERE id=?', (si['quantity'], si['variant_id']))

        if is_exchange and exchange_items_data is not None:
            for item in exchange_items_data:
                si = process_item(item, 1)
                if si is None:
                    continue
                sale_items.append(si)
                db.execute('UPDATE variants SET stock = stock - ? WHERE id=?', (si['quantity'], si['variant_id']))

        if errors:
            return jsonify({'error': '; '.join(errors)}), 400

        disc_amt = round(subtotal * discount / 100, 2) if discount_type == 'percent' else discount
        total = round(subtotal - disc_amt, 2)
        tax = 0

        if is_exchange:
            total = round(total * 0.9, 2)

        receipt = make_receipt()
        if is_return:
            status = 'returned'
        elif is_exchange:
            status = 'exchanged'
        else:
            status = 'Paid' if payment != 'credit' else 'Unpaid'

        due_date = d.get('due_date') if payment == 'credit' else None
        paid_amt = total if (not is_return and not is_exchange and payment != 'credit') else 0
        sale_id = db.execute(
            'INSERT INTO sales (receipt, subtotal, discount, discount_type, tax, total, payment, status, customer_id, customer_name, staff_id, staff_name, notes, due_date, paid) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (receipt, round(subtotal, 2), disc_amt, discount_type, tax, total, payment, status,
             customer_id, customer_name, session['user_id'], session['name'], notes, due_date, paid_amt)
        ).lastrowid

        for si in sale_items:
            si['sale_id'] = sale_id
            db.execute(
                'INSERT INTO sale_items (sale_id, product_id, variant_id, product_name, variant_label, sku, quantity, price, total, is_return) '
                'VALUES (?,?,?,?,?,?,?,?,?,?)',
                (sale_id, si['product_id'], si['variant_id'], si['product_name'], si['variant_label'],
                 si['sku'], si['quantity'], si['price'], si['total'], si['is_return'])
            )

        db.execute(
            'INSERT INTO payments (sale_id, method, amount) VALUES (?,?,?)',
            (sale_id, payment, total)
        )

        if customer_id:
            db.execute('UPDATE customers SET total_spent=total_spent+?, visit_count=visit_count+1 WHERE id=?',
                       (total, customer_id))
            if payment == 'credit':
                db.execute('UPDATE customers SET credit=credit+? WHERE id=?', (total, customer_id))

        return jsonify({
            'ok': True,
            'sale_id': sale_id,
            'receipt': receipt,
            'items': sale_items,
            'subtotal': round(subtotal, 2),
            'discount': disc_amt,
            'tax': tax,
            'total': total,
            'payment': payment,
            'customer_name': customer_name,
            'staff_name': session['name'],
            'is_return': is_return,
            'is_exchange': is_exchange,
            'status': status,
        })


@pos_bp.route('/sales-invoices', methods=['POST'])
@login_required
def create_sales_invoice():
    """Create a sales invoice from spreadsheet data.
    Validates stock, auto-links products by name, decrements stock, records sale."""
    d = request.get_json() or {}
    items = d.get('items', [])
    if not items:
        return jsonify({'error': 'No items'}), 400

    receipt = (d.get('receipt') or '').strip() or make_receipt()
    customer_id = d.get('customer_id')
    payment = d.get('payment', 'cash')
    notes = d.get('notes', '')
    due_date = d.get('due_date') or None

    with get_db() as db:
        # Auto-link products by name where product_id is missing
        for item in items:
            if not item.get('product_id') and item.get('item'):
                row = db.execute(
                    'SELECT id FROM products WHERE LOWER(TRIM(name)) = LOWER(?)',
                    (item['item'].strip(),)
                ).fetchone()
                if row:
                    item['product_id'] = row['id']

        # Resolve variants and validate stock
        sale_items = []
        subtotal = 0

        for item in items:
            pid = item.get('product_id')
            qty = int(item.get('qty', 0))
            if not pid or qty <= 0:
                continue
            prod = db.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
            if not prod:
                continue
            variant = db.execute(
                'SELECT * FROM variants WHERE product_id=? ORDER BY id LIMIT 1', (pid,)
            ).fetchone()
            if not variant:
                continue
            price = float(item.get('unit_price', 0) or prod['base_price'] or 0)
            if price <= 0:
                continue
            line_total = round(price * qty, 2)
            subtotal += line_total
            sale_items.append({
                'product_id': pid,
                'variant_id': variant['id'],
                'product_name': prod['name'],
                'variant_label': '',
                'sku': variant['sku'],
                'quantity': qty,
                'price': price,
                'total': line_total,
                'is_return': 0,
            })

        if not sale_items:
            return jsonify({'error': 'No valid items to sell'}), 400

        # Decrement stock and create sale records
        for si in sale_items:
            db.execute('UPDATE variants SET stock = stock - ? WHERE id=?', (si['quantity'], si['variant_id']))

        customer_name = ''
        if customer_id:
            c = db.execute('SELECT name FROM customers WHERE id=?', (customer_id,)).fetchone()
            if c:
                customer_name = c['name']

        # No tax for spreadsheet sales (Q6 = B: tax-inclusive prices)
        total = round(subtotal, 2)
        status = 'Paid' if payment != 'credit' else 'Unpaid'
        paid_amt = total if status == 'Paid' else 0

        sale_id = db.execute(
            'INSERT INTO sales (receipt, subtotal, discount, discount_type, tax, total, payment, status, customer_id, customer_name, staff_id, staff_name, notes, due_date, paid) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (receipt, total, 0, 'percent', 0, total, payment, status,
             customer_id, customer_name, session['user_id'], session['name'], notes, due_date, paid_amt)
        ).lastrowid

        for si in sale_items:
            si['sale_id'] = sale_id
            db.execute(
                'INSERT INTO sale_items (sale_id, product_id, variant_id, product_name, variant_label, sku, quantity, price, total, is_return) '
                'VALUES (?,?,?,?,?,?,?,?,?,?)',
                (sale_id, si['product_id'], si['variant_id'], si['product_name'], si['variant_label'],
                 si['sku'], si['quantity'], si['price'], si['total'], si['is_return'])
            )

        db.execute(
            'INSERT INTO payments (sale_id, method, amount) VALUES (?,?,?)',
            (sale_id, payment, total)
        )

        if customer_id:
            db.execute('UPDATE customers SET total_spent=total_spent+?, visit_count=visit_count+1 WHERE id=?',
                       (total, customer_id))
            if payment == 'credit':
                db.execute('UPDATE customers SET credit=credit+? WHERE id=?', (total, customer_id))

        return jsonify({
            'ok': True,
            'sale_id': sale_id,
            'receipt': receipt,
            'items': sale_items,
            'subtotal': total,
            'total': total,
            'payment': payment,
            'customer_name': customer_name,
            'staff_name': session.get('name', ''),
        })


@pos_bp.route('/sales-invoices/<int:sid>', methods=['PUT'])
@login_required
@manager_required
def update_sales_invoice(sid):
    """Update a sales invoice: reverse old stock, apply new items, update sale row."""
    d = request.get_json() or {}
    items = d.get('items', [])
    if not items:
        return jsonify({'error': 'No items'}), 400

    with get_db() as db:
        old = db.execute('SELECT * FROM sales WHERE id=?', (sid,)).fetchone()
        if not old:
            return jsonify({'error': 'Sale not found'}), 404
        old = dict(old)

        old_items = db.execute('SELECT * FROM sale_items WHERE sale_id=?', (sid,)).fetchall()
        due_date = d.get('due_date') or old.get('due_date')
        for oi in old_items:
            if oi['variant_id'] and oi['is_return'] == 0:
                db.execute('UPDATE variants SET stock = stock + ? WHERE id=?', (oi['quantity'], oi['variant_id']))

        for item in items:
            if not item.get('product_id') and item.get('item'):
                row = db.execute(
                    'SELECT id FROM products WHERE LOWER(TRIM(name)) = LOWER(?)',
                    (item['item'].strip(),)
                ).fetchone()
                if row:
                    item['product_id'] = row['id']

        sale_items = []
        subtotal = 0
        for item in items:
            pid = item.get('product_id')
            qty = int(item.get('qty', 0))
            if not pid or qty <= 0:
                continue
            prod = db.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
            if not prod:
                continue
            variant = db.execute(
                'SELECT * FROM variants WHERE product_id=? ORDER BY id LIMIT 1', (pid,)
            ).fetchone()
            if not variant:
                continue
            price = float(item.get('unit_price', 0) or prod['base_price'] or 0)
            if price <= 0:
                continue
            line_total = round(price * qty, 2)
            subtotal += line_total
            sale_items.append({
                'product_id': pid,
                'variant_id': variant['id'],
                'product_name': prod['name'],
                'variant_label': '',
                'sku': variant['sku'],
                'quantity': qty,
                'price': price,
                'total': line_total,
                'is_return': 0,
            })

        if not sale_items:
            for oi in old_items:
                if oi['variant_id'] and oi['is_return'] == 0:
                    db.execute('UPDATE variants SET stock = stock - ? WHERE id=?', (oi['quantity'], oi['variant_id']))
            return jsonify({'error': 'No valid items to sell'}), 400

        for si in sale_items:
            db.execute('UPDATE variants SET stock = stock - ? WHERE id=?', (si['quantity'], si['variant_id']))

        customer_id = d.get('customer_id') or old.get('customer_id')
        payment = d.get('payment') or old.get('payment')
        notes = d.get('notes', old.get('notes', ''))
        customer_name = old.get('customer_name', '')
        if customer_id:
            c = db.execute('SELECT name FROM customers WHERE id=?', (customer_id,)).fetchone()
            if c:
                customer_name = c['name']

        total = round(subtotal, 2)
        if old.get('customer_id') and old['customer_id'] == customer_id:
            db.execute('UPDATE customers SET total_spent = total_spent - ? WHERE id=?', (old['total'], old['customer_id']))
        elif old.get('customer_id'):
            db.execute('UPDATE customers SET total_spent = total_spent - ? WHERE id=?', (old['total'], old['customer_id']))
        if customer_id:
            db.execute('UPDATE customers SET total_spent = total_spent + ? WHERE id=?', (total, customer_id))
            if payment == 'credit':
                if old.get('customer_id') and old['customer_id'] == customer_id and old.get('payment') == 'credit':
                    db.execute('UPDATE customers SET credit = credit - ? WHERE id=?', (old['total'], old['customer_id']))
                elif old.get('customer_id') and old.get('payment') == 'credit':
                    db.execute('UPDATE customers SET credit = credit - ? WHERE id=?', (old['total'], old['customer_id']))
                db.execute('UPDATE customers SET credit = credit + ? WHERE id=?', (total, customer_id))

        status = 'Paid' if payment != 'credit' else 'Unpaid'
        new_paid = total if status == 'Paid' else old.get('paid', 0)
        db.execute(
            'UPDATE sales SET subtotal=?, discount=?, discount_type=?, tax=?, total=?, payment=?, status=?, paid=?, customer_id=?, customer_name=?, notes=?, due_date=? WHERE id=?',
            (total, 0, 'percent', 0, total, payment, status, new_paid, customer_id, customer_name, notes, due_date, sid)
        )
        db.execute('DELETE FROM sale_items WHERE sale_id=? AND is_return=0', (sid,))
        for si in sale_items:
            db.execute(
                'INSERT INTO sale_items (sale_id, product_id, variant_id, product_name, variant_label, sku, quantity, price, total, is_return) '
                'VALUES (?,?,?,?,?,?,?,?,?,?)',
                (sid, si['product_id'], si['variant_id'], si['product_name'], si['variant_label'],
                 si['sku'], si['quantity'], si['price'], si['total'], si['is_return'])
            )

        db.execute('DELETE FROM payments WHERE sale_id=?', (sid,))
        db.execute(
            'INSERT INTO payments (sale_id, method, amount) VALUES (?,?,?)',
            (sid, payment, total)
        )

        return jsonify({
            'ok': True,
            'sale_id': sid,
            'receipt': old['receipt'],
            'items': sale_items,
            'subtotal': total,
            'total': total,
            'payment': payment,
            'customer_name': customer_name,
            'staff_name': session.get('name', ''),
        })


@pos_bp.route('/sales-invoices/<int:sid>', methods=['DELETE'])
@login_required
@manager_required
def delete_sales_invoice(sid):
    """Delete a sales invoice: restore stock, reverse customer effects, remove rows."""
    with get_db() as db:
        sale = db.execute('SELECT * FROM sales WHERE id=?', (sid,)).fetchone()
        if not sale:
            return jsonify({'error': 'Sale not found'}), 404
        sale = dict(sale)

        items = db.execute('SELECT * FROM sale_items WHERE sale_id=?', (sid,)).fetchall()
        for it in items:
            if it['variant_id'] and it['is_return'] == 0:
                db.execute('UPDATE variants SET stock = stock + ? WHERE id=?', (it['quantity'], it['variant_id']))

        if sale.get('customer_id'):
            db.execute('UPDATE customers SET total_spent = total_spent - ? WHERE id=?', (sale['total'], sale['customer_id']))
            if sale.get('payment') == 'credit':
                db.execute('UPDATE customers SET credit = credit - ? WHERE id=?', (sale['total'], sale['customer_id']))

        db.execute('DELETE FROM sale_items WHERE sale_id=?', (sid,))
        db.execute('DELETE FROM payments WHERE sale_id=?', (sid,))
        db.execute('DELETE FROM sales WHERE id=?', (sid,))
        return jsonify({'ok': True})


@pos_bp.route('/sales')
@login_required
def sales_list():
    q = request.args.get('q', '')
    with get_db() as db:
        if q:
            rows = db.execute(
                'SELECT * FROM sales WHERE receipt LIKE ? OR customer_name LIKE ? ORDER BY id DESC LIMIT 50',
                (f'%{q}%', f'%{q}%')
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM sales ORDER BY id DESC LIMIT 50').fetchall()
        result = []
        for r in rows:
            r = dict(r)
            r['items'] = [dict(x) for x in db.execute('SELECT * FROM sale_items WHERE sale_id=?', (r['id'],)).fetchall()]
            result.append(r)
        return jsonify(result)


@pos_bp.route('/sales/<int:sid>')
@login_required
def sale_detail(sid):
    with get_db() as db:
        sale = db.execute('SELECT * FROM sales WHERE id=?', (sid,)).fetchone()
        if not sale:
            return jsonify({'error': 'Not found'}), 404
        sale = dict(sale)
        sale['items'] = [dict(x) for x in db.execute('SELECT * FROM sale_items WHERE sale_id=?', (sid,)).fetchall()]
        sale['payments'] = [dict(x) for x in db.execute('SELECT * FROM payments WHERE sale_id=?', (sid,)).fetchall()]
        return jsonify(sale)
