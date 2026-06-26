import random
import time
from flask import Blueprint, request, jsonify, session
from database import get_db
from routes.auth import login_required

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

        settings = dict(db.execute('SELECT key, value FROM settings').fetchall())
        tax_rate = float(settings.get('tax_rate', '8')) / 100

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
        taxable = round(subtotal - disc_amt, 2)
        tax = round(taxable * tax_rate, 2)
        total = round(taxable + tax, 2)

        if is_exchange:
            total = round(total * 0.9, 2)

        receipt = make_receipt()
        status = 'returned' if is_return else ('exchanged' if is_exchange else 'completed')

        sale_id = db.execute(
            'INSERT INTO sales (receipt, subtotal, discount, discount_type, tax, total, payment, status, customer_id, customer_name, staff_id, staff_name, notes) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (receipt, round(subtotal, 2), disc_amt, discount_type, tax, total, payment, status,
             customer_id, customer_name, session['user_id'], session['name'], notes)
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
