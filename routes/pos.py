import json
import random
import time
from flask import Blueprint, request, jsonify, session
from database import get_db
from routes.auth import login_required, manager_required

pos_bp = Blueprint('pos', __name__, url_prefix='/api')


def compute_sale_status(paid, total):
    """Compute sale status dynamically from paid and total amounts."""
    if paid >= total:
        return 'Paid'
    elif paid > 0:
        return 'Partial'
    else:
        return 'Unpaid'


def generate_receipt_number():
    """Generate a unique receipt number using timestamp and random suffix."""
    timestamp = int(time.time() * 1000) % 10000000
    random_suffix = random.randint(100, 999)
    return f"JITM-{timestamp}{random_suffix}"


def resolve_customer(db, request_data, is_walk_in):
    """Find or create customer based on request data. Returns (customer_id, customer_name)."""
    customer_phone = request_data.get('customer_phone', '')
    customer_name = request_data.get('customer_name', '')
    customer_id = request_data.get('customer_id')
    
    if is_walk_in:
        customer_name = 'Walk In'
        customer = db.execute('SELECT * FROM customers WHERE name=?', ('Walk In',)).fetchone()
        if customer:
            customer_id = customer['id']
        else:
            cursor = db.execute('INSERT INTO customers (name, phone) VALUES (?,?)', ('Walk In', ''))
            customer_id = cursor.lastrowid
    elif customer_phone:
        customer = db.execute('SELECT * FROM customers WHERE phone=?', (customer_phone,)).fetchone()
        if customer:
            customer_id = customer['id']
            customer_name = customer['name']
        elif customer_name:
            cursor = db.execute('INSERT INTO customers (name, phone) VALUES (?,?)', (customer_name, customer_phone))
            customer_id = cursor.lastrowid
    
    return customer_id, customer_name


def process_sale_items(db, items, is_return):
    """Validate items, calculate totals, and update stock. Returns (sale_items, subtotal, errors)."""
    errors = []
    sale_items = []
    subtotal = 0
    quantity_multiplier = -1 if is_return else 1
    
    for item in items:
        variant_id = item.get('variant_id') or item.get('vid')
        quantity = int(item['quantity']) * quantity_multiplier
        
        variant = db.execute('SELECT * FROM variants WHERE id=?', (variant_id,)).fetchone()
        if not variant:
            errors.append(f'Variant {variant_id} not found')
            continue
        
        product = db.execute('SELECT * FROM products WHERE id=?', (variant['product_id'],)).fetchone()
        price = float(item.get('price', variant['price'] or product['base_price']))
        line_total = round(price * quantity, 2)
        subtotal += line_total
        
        staff_id = item.get('staff')
        is_item_return = is_return
        
        sale_item = {
            'product_id': product['id'],
            'variant_id': variant_id,
            'product_name': product['name'],
            'variant_label': f'{variant["size"]} {variant["color"]}'.strip(),
            'sku': variant['sku'],
            'quantity': quantity,
            'price': price,
            'total': line_total,
            'is_return': 1 if is_item_return else 0,
            'staff_id': staff_id,
            'cost_price': product['cost_price'],
        }
        sale_items.append(sale_item)
        
        if quantity_multiplier < 0:
            db.execute('UPDATE variants SET stock = stock + ? WHERE id=?', (abs(sale_item['quantity']), sale_item['variant_id']))
        else:
            db.execute('UPDATE variants SET stock = stock - ? WHERE id=?', (sale_item['quantity'], sale_item['variant_id']))
    
    return sale_items, subtotal, errors


def reverse_sale_transactions(db, sale_id):
    """Reverse account balances and delete transaction rows for a sale."""
    transactions = db.execute(
        "SELECT * FROM transactions WHERE reference_type='sale' AND reference_id=?",
        (sale_id,)
    ).fetchall()
    
    for transaction in transactions:
        balance_change = -transaction['amount'] if transaction['type'] == 'receipt' else transaction['amount']
        db.execute('UPDATE accounts SET balance=balance+? WHERE id=?', (balance_change, transaction['account_id']))
    
    db.execute("DELETE FROM transactions WHERE reference_type='sale' AND reference_id=?", (sale_id,))


def record_payments(db, sale_id, payments, is_return, customer_id, receipt_number):
    """Record payment rows and update account balances for a completed sale.
    
    Each payment leg creates:
    - One row in payments table
    - One row in transactions table (if method maps to an account)
    
    Allocations link each transaction to the sale for proper tracking.
    """
    account_map = {
        'cash': ('POS Petty Cash', 'cash'),
        'jb': ('Jibraan', 'bank'),
        'ahd': ('Ahmed', 'bank'),
        'z': ('Zahid', 'bank')
    }
    
    total_recorded = 0
    
    for payment in payments:
        payment_amount = float(payment['amount'])
        
        # Record payment leg
        db.execute(
            'INSERT INTO payments (sale_id, method, amount) VALUES (?,?,?)',
            (sale_id, payment['method'], payment_amount)
        )
        
        # Only create account transactions for non-credit payment methods
        if payment['method'] in account_map:
            account_name, account_type = account_map[payment['method']]
            account = db.execute('SELECT * FROM accounts WHERE name=?', (account_name,)).fetchone()
            if not account:
                cursor = db.execute('INSERT INTO accounts (name, type, balance) VALUES (?,?,?)',
                                  (account_name, account_type, 0))
                account_id = cursor.lastrowid
            else:
                account_id = account['id']
            
            transaction_type = 'payment' if is_return else 'receipt'
            transaction_description = f'Sale return: {receipt_number}' if is_return else f'Sale receipt: {receipt_number}'
            
            # Create allocation linking this transaction to the sale
            allocation = [{'ref_type': 'sale', 'ref_id': sale_id, 'amount': abs(payment_amount)}]
            allocations_json = json.dumps(allocation)
            
            db.execute(
                "INSERT INTO transactions (account_id, type, amount, description, party_type, party_id, reference_type, reference_id, allocations, date) "
                "VALUES (?,?,?,?,?,?,?,?,?,date('now'))",
                (account_id, transaction_type, abs(payment_amount), transaction_description,
                 'customer', customer_id, 'sale', sale_id, allocations_json)
            )
            
            balance_change = -abs(payment_amount) if is_return else payment_amount
            db.execute('UPDATE accounts SET balance=balance+? WHERE id=?', (balance_change, account_id))
            
            total_recorded += abs(payment_amount)
    
    return total_recorded


@pos_bp.route('/sale', methods=['POST'])
@login_required
def complete_sale():
    """Process a POS sale or return. Handles split payments, credit, and stock updates."""
    request_data = request.get_json()
    items = request_data.get('items', [])
    if not items:
        return jsonify({'error': 'No items'}), 400
    
    is_return = request_data.get('is_return', False)
    discount_pct = float(request_data.get('discount_pct', 0))
    discount_amt = float(request_data.get('discount_amt', 0))
    payment_method = request_data.get('payment', 'cash')
    customer_phone = request_data.get('customer_phone', '')
    is_walk_in = request_data.get('walk_in', False)
    customer_id = request_data.get('customer_id')
    customer_name = request_data.get('customer_name', '')
    notes = request_data.get('notes', '')
    
    if not is_walk_in and not customer_phone and not customer_name and not customer_id:
        return jsonify({'error': 'Customer information required'}), 400
    
    cash_tendered = request_data.get('cash_tendered', 0) or 0
    change_given = request_data.get('change_given', 0) or 0
    
    with get_db() as db:
        db.execute('BEGIN IMMEDIATE')
        
        customer_id, customer_name = resolve_customer(db, request_data, is_walk_in)
        
        sale_items, subtotal, errors = process_sale_items(db, items, is_return)
        if errors:
            return jsonify({'error': '; '.join(errors)}), 400
        
        for sale_item in sale_items:
            if sale_item.get('staff_id'):
                emp = db.execute('SELECT nickname FROM employees WHERE id=?', (sale_item['staff_id'],)).fetchone()
                sale_item['employee_nickname'] = emp['nickname'] if emp else ''
            else:
                sale_item['employee_nickname'] = ''
        
        discount_amount = round(abs(subtotal) * discount_pct / 100 + discount_amt, 2)
        if subtotal < 0:
            total = round(subtotal + discount_amount, 2)
        else:
            total = round(subtotal - discount_amount, 2)
        tax = 0
        
        receipt_number = generate_receipt_number()
        
        payment_list = request_data.get('payments', [])
        if not payment_list:
            payment_list = [{'method': payment_method, 'amount': total}]
        
        has_credit = any(payment['method'] == 'credit' for payment in payment_list)
        
        if has_credit and customer_id:
            customer = db.execute('SELECT credit, credit_limit FROM customers WHERE id=?', (customer_id,)).fetchone()
            if customer and customer['credit_limit'] is not None:
                total_credit_after = customer['credit'] + sum(payment['amount'] for payment in payment_list if payment['method'] == 'credit')
                if total_credit_after > customer['credit_limit']:
                    return jsonify({'error': f'Credit limit of Rs {customer["credit_limit"]:.2f} would be exceeded'}), 400
        
        # Compute status dynamically based on payment amounts
        if is_return:
            status = 'returned'
        else:
            non_credit_paid = sum(payment['amount'] for payment in payment_list if payment['method'] != 'credit')
            status = compute_sale_status(non_credit_paid, total)
        
        due_date = request_data.get('due_date') if has_credit else None
        
        paid_amount = sum(payment['amount'] for payment in payment_list if payment['method'] != 'credit')
        
        sale_id = db.execute(
            'INSERT INTO sales (receipt, subtotal, discount, discount_type, tax, total, payment, status, customer_id, customer_name, staff_id, staff_name, notes, due_date, paid, cash_tendered, change_given) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (receipt_number, round(subtotal, 2), discount_amount, 'amount', tax, total,
             'split' if len(payment_list) > 1 else payment_method, status,
             customer_id, customer_name, session['user_id'], session['name'], notes, due_date,
             paid_amount, cash_tendered, change_given)
        ).lastrowid
        
        for sale_item in sale_items:
            sale_item['sale_id'] = sale_id
            commission_val = 0
            if sale_item['staff_id']:
                prod = db.execute('SELECT commission_class FROM products WHERE id=?', (sale_item['product_id'],)).fetchone()
                if prod and prod['commission_class']:
                    cc = db.execute('SELECT percentage FROM commission_classes WHERE name=?', (prod['commission_class'],)).fetchone()
                    if cc and cc['percentage']:
                        commission_val = abs(sale_item['total']) * cc['percentage'] / 100
            
            db.execute(
                'INSERT INTO sale_items (sale_id, product_id, variant_id, product_name, variant_label, sku, quantity, price, total, is_return, staff_id, cost_price, commission) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (sale_id, sale_item['product_id'], sale_item['variant_id'], sale_item['product_name'],
                 sale_item['variant_label'], sale_item['sku'], sale_item['quantity'], sale_item['price'],
                 sale_item['total'], sale_item['is_return'], sale_item['staff_id'], sale_item['cost_price'], commission_val)
            )
            
            if commission_val > 0:
                multiplier = -1 if is_return else 1
                db.execute('UPDATE employees SET commissions=commissions+? WHERE id=?',
                           (commission_val * multiplier, sale_item['staff_id']))
        
        recorded_amount = record_payments(db, sale_id, payment_list, is_return, customer_id, receipt_number)
        
        # Verify: sum of account transactions must equal sum of non-credit payment legs
        expected_recorded = sum(
            payment['amount'] for payment in payment_list
            if payment['method'] in ('cash', 'jb', 'ahd', 'z')
        )
        if abs(recorded_amount - expected_recorded) > 0.01:
            return jsonify({'error': f'Payment recording mismatch: expected Rs {expected_recorded:.2f}, recorded Rs {recorded_amount:.2f}'}), 500
        
        if customer_id:
            spent_change = -abs(total) if is_return else total
            db.execute('UPDATE customers SET total_spent=total_spent+?, visit_count=visit_count+1 WHERE id=?',
                       (spent_change, customer_id))
            for payment in payment_list:
                if payment['method'] == 'credit':
                    credit_change = -abs(payment['amount']) if is_return else payment['amount']
                    db.execute('UPDATE customers SET credit=credit+? WHERE id=?', (credit_change, customer_id))
        
        return jsonify({
            'ok': True,
            'sale_id': sale_id,
            'receipt': receipt_number,
            'items': sale_items,
            'subtotal': round(subtotal, 2),
            'discount': discount_amount,
            'tax': tax,
            'total': total,
            'payment': payment_method,
            'payments': payment_list,
            'customer_name': customer_name,
            'customer_phone': customer_phone,
            'staff_name': session['name'],
            'staff_nickname': session.get('nick_name', session['name']),
            'is_return': is_return,
            'status': status,
            'cash_tendered': cash_tendered,
            'change_given': change_given,
        })


@pos_bp.route('/sales-invoices', methods=['POST'])
@login_required
def create_sales_invoice():
    """Create a sales invoice from spreadsheet data. Validates stock, auto-links products, records sale."""
    request_data = request.get_json() or {}
    items = request_data.get('items', [])
    if not items:
        return jsonify({'error': 'No items'}), 400
    
    receipt_number = (request_data.get('receipt') or '').strip() or generate_receipt_number()
    customer_id = request_data.get('customer_id')
    payment_method = request_data.get('payment', 'cash')
    account_id = request_data.get('account_id')
    notes = request_data.get('notes', '')
    due_date = request_data.get('due_date') or None
    
    if payment_method != 'credit' and not account_id:
        return jsonify({'error': 'Receive to Account is required for this payment method'}), 400
    
    with get_db() as db:
        db.execute('BEGIN IMMEDIATE')
        
        for item in items:
            if not item.get('product_id') and item.get('item'):
                product_row = db.execute(
                    'SELECT id FROM products WHERE LOWER(TRIM(name)) = LOWER(?)',
                    (item['item'].strip(),)
                ).fetchone()
                if product_row:
                    item['product_id'] = product_row['id']
        
        sale_items = []
        subtotal = 0
        
        for item in items:
            product_id = item.get('product_id')
            quantity = int(item.get('qty', 0))
            if not product_id or quantity <= 0:
                continue
            
            product = db.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone()
            if not product:
                continue
            
            variant = db.execute(
                'SELECT * FROM variants WHERE product_id=? ORDER BY id LIMIT 1', (product_id,)
            ).fetchone()
            if not variant:
                continue
            
            price = float(item.get('unit_price', 0) or product['base_price'] or 0)
            if price <= 0:
                continue
            
            line_total = round(price * quantity, 2)
            subtotal += line_total
            
            sale_items.append({
                'product_id': product_id,
                'variant_id': variant['id'],
                'product_name': product['name'],
                'variant_label': '',
                'sku': variant['sku'],
                'quantity': quantity,
                'price': price,
                'total': line_total,
                'is_return': 0,
                'cost_price': product['cost_price'],
            })
        
        if not sale_items:
            return jsonify({'error': 'No valid items to sell'}), 400
        
        for sale_item in sale_items:
            db.execute('UPDATE variants SET stock = stock - ? WHERE id=?', (sale_item['quantity'], sale_item['variant_id']))
        
        customer_name = ''
        if customer_id:
            customer = db.execute('SELECT name FROM customers WHERE id=?', (customer_id,)).fetchone()
            if customer:
                customer_name = customer['name']
        
        total = round(subtotal, 2)
        paid_amount = total if payment_method != 'credit' else 0
        status = compute_sale_status(paid_amount, total)
        
        sale_id = db.execute(
            'INSERT INTO sales (receipt, subtotal, discount, discount_type, tax, total, payment, status, customer_id, customer_name, staff_id, staff_name, notes, due_date, paid) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (receipt_number, total, 0, 'percent', 0, total, payment_method, status,
             customer_id, customer_name, session['user_id'], session['name'], notes, due_date, paid_amount)
        ).lastrowid
        
        for sale_item in sale_items:
            sale_item['sale_id'] = sale_id
            db.execute(
                'INSERT INTO sale_items (sale_id, product_id, variant_id, product_name, variant_label, sku, quantity, price, total, is_return, staff_id, cost_price) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                (sale_id, sale_item['product_id'], sale_item['variant_id'], sale_item['product_name'],
                 sale_item['variant_label'], sale_item['sku'], sale_item['quantity'], sale_item['price'],
                 sale_item['total'], sale_item['is_return'], None, sale_item['cost_price'])
            )
        
        db.execute(
            'INSERT INTO payments (sale_id, method, amount) VALUES (?,?,?)',
            (sale_id, payment_method, total)
        )
        
        if account_id and payment_method != 'credit':
            account = db.execute('SELECT * FROM accounts WHERE id=?', (account_id,)).fetchone()
            if account:
                allocation = [{'ref_type': 'sale', 'ref_id': sale_id, 'amount': total}]
                allocations_json = json.dumps(allocation)
                db.execute(
                    "INSERT INTO transactions (account_id, type, amount, description, party_type, party_id, reference_type, reference_id, allocations, date) "
                    "VALUES (?,?,?,?,?,?,?,?,?,date('now'))",
                    (account_id, 'receipt', total, f'Sale receipt: {receipt_number}',
                     'customer', customer_id, 'sale', sale_id, allocations_json)
                )
                db.execute('UPDATE accounts SET balance=balance+? WHERE id=?', (total, account_id))
        
        if customer_id:
            db.execute('UPDATE customers SET total_spent=total_spent+?, visit_count=visit_count+1 WHERE id=?',
                       (total, customer_id))
            if payment_method == 'credit':
                db.execute('UPDATE customers SET credit=credit+? WHERE id=?', (total, customer_id))
        
        for sale_item in sale_items:
            sale_item['employee_nickname'] = ''
        
        return jsonify({
            'ok': True,
            'sale_id': sale_id,
            'receipt': receipt_number,
            'items': sale_items,
            'subtotal': total,
            'total': total,
            'payment': payment_method,
            'customer_name': customer_name,
            'staff_name': session.get('name', ''),
            'staff_nickname': session.get('nick_name', session.get('name', '')),
        })


@pos_bp.route('/sales-invoices/<int:sale_id>', methods=['PUT'])
@login_required
@manager_required
def update_sales_invoice(sale_id):
    """Update a sales invoice: reverse old stock, apply new items, update sale row."""
    request_data = request.get_json() or {}
    items = request_data.get('items', [])
    if not items:
        return jsonify({'error': 'No items'}), 400
    
    with get_db() as db:
        db.execute('BEGIN IMMEDIATE')
        old_sale = db.execute('SELECT * FROM sales WHERE id=?', (sale_id,)).fetchone()
        if not old_sale:
            return jsonify({'error': 'Sale not found'}), 404
        old_sale = dict(old_sale)
        
        if (request_data.get('payment') or old_sale.get('payment')) != 'credit' and not request_data.get('account_id'):
            return jsonify({'error': 'Receive to Account is required for this payment method'}), 400
        
        old_items = db.execute('SELECT * FROM sale_items WHERE sale_id=?', (sale_id,)).fetchall()
        
        for old_item in old_items:
            if old_item['variant_id'] and old_item['is_return'] == 0:
                db.execute('UPDATE variants SET stock = stock + ? WHERE id=?', (old_item['quantity'], old_item['variant_id']))
        
        for item in items:
            if not item.get('product_id') and item.get('item'):
                product_row = db.execute(
                    'SELECT id FROM products WHERE LOWER(TRIM(name)) = LOWER(?)',
                    (item['item'].strip(),)
                ).fetchone()
                if product_row:
                    item['product_id'] = product_row['id']
        
        sale_items = []
        subtotal = 0
        
        for item in items:
            product_id = item.get('product_id')
            quantity = int(item.get('qty', 0))
            if not product_id or quantity <= 0:
                continue
            
            product = db.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone()
            if not product:
                continue
            
            variant = db.execute(
                'SELECT * FROM variants WHERE product_id=? ORDER BY id LIMIT 1', (product_id,)
            ).fetchone()
            if not variant:
                continue
            
            price = float(item.get('unit_price', 0) or product['base_price'] or 0)
            if price <= 0:
                continue
            
            line_total = round(price * quantity, 2)
            subtotal += line_total
            
            sale_items.append({
                'product_id': product_id,
                'variant_id': variant['id'],
                'product_name': product['name'],
                'variant_label': '',
                'sku': variant['sku'],
                'quantity': quantity,
                'price': price,
                'total': line_total,
                'is_return': 0,
                'cost_price': product['cost_price'],
            })
        
        if not sale_items:
            for old_item in old_items:
                if old_item['variant_id'] and old_item['is_return'] == 0:
                    db.execute('UPDATE variants SET stock = stock - ? WHERE id=?', (old_item['quantity'], old_item['variant_id']))
            return jsonify({'error': 'No valid items to sell'}), 400
        
        for sale_item in sale_items:
            db.execute('UPDATE variants SET stock = stock - ? WHERE id=?', (sale_item['quantity'], sale_item['variant_id']))
        
        customer_id = request_data.get('customer_id') or old_sale.get('customer_id')
        payment_method = request_data.get('payment') or old_sale.get('payment')
        account_id = request_data.get('account_id')
        notes = request_data.get('notes', old_sale.get('notes', ''))
        customer_name = old_sale.get('customer_name', '')
        
        if payment_method == 'credit':
            due_date = request_data.get('due_date') or old_sale.get('due_date')
        else:
            due_date = None
        
        if customer_id:
            customer = db.execute('SELECT name FROM customers WHERE id=?', (customer_id,)).fetchone()
            if customer:
                customer_name = customer['name']
        
        total = round(subtotal, 2)
        
        if old_sale.get('customer_id'):
            db.execute('UPDATE customers SET total_spent = total_spent - ? WHERE id=?', (old_sale['total'], old_sale['customer_id']))
        if customer_id:
            db.execute('UPDATE customers SET total_spent = total_spent + ? WHERE id=?', (total, customer_id))
        
        if old_sale.get('payment') == 'credit' and old_sale.get('customer_id'):
            db.execute('UPDATE customers SET credit = credit - ? WHERE id=?', (old_sale['total'], old_sale['customer_id']))
        if payment_method == 'credit' and customer_id:
            db.execute('UPDATE customers SET credit = credit + ? WHERE id=?', (total, customer_id))
        
        if payment_method == 'credit':
            new_paid = old_sale.get('paid', 0) if old_sale.get('payment') == 'credit' else 0
        elif payment_method == 'split':
            new_paid = old_sale.get('paid', 0)
        else:
            new_paid = total
        status = compute_sale_status(new_paid, total)
        
        db.execute(
            'UPDATE sales SET subtotal=?, discount=?, discount_type=?, tax=?, total=?, payment=?, status=?, paid=?, customer_id=?, customer_name=?, notes=?, due_date=? WHERE id=?',
            (total, 0, 'percent', 0, total, payment_method, status, new_paid, customer_id, customer_name, notes, due_date, sale_id)
        )
        
        db.execute('DELETE FROM sale_items WHERE sale_id=? AND is_return=0', (sale_id,))
        for sale_item in sale_items:
            db.execute(
                'INSERT INTO sale_items (sale_id, product_id, variant_id, product_name, variant_label, sku, quantity, price, total, is_return, staff_id, cost_price) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                (sale_id, sale_item['product_id'], sale_item['variant_id'], sale_item['product_name'],
                 sale_item['variant_label'], sale_item['sku'], sale_item['quantity'], sale_item['price'],
                 sale_item['total'], sale_item['is_return'], None, sale_item['cost_price'])
            )
        
        reverse_sale_transactions(db, sale_id)
        
        if payment_method == 'credit':
            db.execute('DELETE FROM payments WHERE sale_id=?', (sale_id,))
            db.execute(
                'INSERT INTO payments (sale_id, method, amount) VALUES (?,?,?)',
                (sale_id, 'credit', total)
            )
        elif payment_method != 'split':
            db.execute('DELETE FROM payments WHERE sale_id=?', (sale_id,))
            db.execute(
                'INSERT INTO payments (sale_id, method, amount) VALUES (?,?,?)',
                (sale_id, payment_method, total)
            )
        
        if account_id and payment_method != 'credit':
            account = db.execute('SELECT * FROM accounts WHERE id=?', (account_id,)).fetchone()
            if account:
                allocation = [{'ref_type': 'sale', 'ref_id': sale_id, 'amount': total}]
                allocations_json = json.dumps(allocation)
                db.execute(
                    "INSERT INTO transactions (account_id, type, amount, description, party_type, party_id, reference_type, reference_id, allocations, date) "
                    "VALUES (?,?,?,?,?,?,?,?,?,date('now'))",
                    (account_id, 'receipt', total, f'Sale receipt: {old_sale["receipt"]}',
                     'customer', customer_id, 'sale', sale_id, allocations_json)
                )
                db.execute('UPDATE accounts SET balance=balance+? WHERE id=?', (total, account_id))
        
        for sale_item in sale_items:
            sale_item['employee_nickname'] = ''
        
        return jsonify({
            'ok': True,
            'sale_id': sale_id,
            'receipt': old_sale['receipt'],
            'items': sale_items,
            'subtotal': total,
            'total': total,
            'payment': payment_method,
            'customer_name': customer_name,
            'staff_name': session.get('name', ''),
            'staff_nickname': session.get('nick_name', session.get('name', '')),
        })


@pos_bp.route('/sales-invoices/<int:sale_id>', methods=['DELETE'])
@login_required
@manager_required
def delete_sales_invoice(sale_id):
    """Delete a sales invoice: restore stock, reverse customer effects, remove rows."""
    with get_db() as db:
        sale = db.execute('SELECT * FROM sales WHERE id=?', (sale_id,)).fetchone()
        if not sale:
            return jsonify({'error': 'Sale not found'}), 404
        sale = dict(sale)
        
        sale_items = db.execute('SELECT * FROM sale_items WHERE sale_id=?', (sale_id,)).fetchall()
        for item in sale_items:
            if item['variant_id'] and item['is_return'] == 0:
                db.execute('UPDATE variants SET stock = stock + ? WHERE id=?', (item['quantity'], item['variant_id']))
        
        if sale.get('customer_id'):
            is_return = sale.get('status') == 'returned'
            spent_change = -abs(sale['total']) if is_return else sale['total']
            db.execute('UPDATE customers SET total_spent = total_spent - ? WHERE id=?', (spent_change, sale['customer_id']))
            if sale.get('payment') == 'credit':
                credit_change = -abs(sale['total']) if is_return else sale['total']
                db.execute('UPDATE customers SET credit = credit - ? WHERE id=?', (credit_change, sale['customer_id']))
        
        reverse_sale_transactions(db, sale_id)
        
        db.execute('DELETE FROM sale_items WHERE sale_id=?', (sale_id,))
        db.execute('DELETE FROM payments WHERE sale_id=?', (sale_id,))
        db.execute('DELETE FROM sales WHERE id=?', (sale_id,))
        
        return jsonify({'ok': True})


@pos_bp.route('/sales')
@login_required
def sales_list():
    """List recent sales with optional search filter, date range, and pagination."""
    search_query = request.args.get('q', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    offset = (page - 1) * per_page
    
    with get_db() as db:
        where_clauses = []
        params = []
        
        if search_query:
            where_clauses.append('(receipt LIKE ? OR customer_name LIKE ?)')
            params.extend([f'%{search_query}%', f'%{search_query}%'])
        if date_from and date_to:
            where_clauses.append('date(created_at) BETWEEN ? AND ?')
            params.extend([date_from, date_to])
        elif date_from:
            where_clauses.append('date(created_at) >= ?')
            params.append(date_from)
        elif date_to:
            where_clauses.append('date(created_at) <= ?')
            params.append(date_to)
        
        where_sql = ' AND '.join(where_clauses)
        if where_sql:
            where_sql = 'WHERE ' + where_sql
        
        count_row = db.execute(
            'SELECT COUNT(*) as cnt FROM sales ' + where_sql, params
        ).fetchone()
        total = count_row['cnt']
        
        rows = db.execute(
            'SELECT * FROM sales ' + where_sql + ' ORDER BY id DESC LIMIT ? OFFSET ?',
            params + [per_page, offset]
        ).fetchall()
        
        result = []
        for row in rows:
            sale = dict(row)
            sale['status'] = compute_sale_status(sale['paid'], sale['total'])
            sale['items'] = [dict(item) for item in db.execute('SELECT * FROM sale_items WHERE sale_id=?', (sale['id'],)).fetchall()]
            result.append(sale)
        
        return jsonify({
            'items': result,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })


@pos_bp.route('/sales/<int:sale_id>')
@login_required
def sale_detail(sale_id):
    """Get detailed information for a specific sale."""
    with get_db() as db:
        sale = db.execute('SELECT * FROM sales WHERE id=?', (sale_id,)).fetchone()
        if not sale:
            return jsonify({'error': 'Not found'}), 404
        
        sale = dict(sale)
        # Compute status dynamically
        sale['status'] = compute_sale_status(sale['paid'], sale['total'])
        sale['items'] = [dict(item) for item in db.execute('SELECT * FROM sale_items WHERE sale_id=?', (sale_id,)).fetchall()]
        for item in sale['items']:
            if item.get('staff_id'):
                emp = db.execute('SELECT nickname FROM employees WHERE id=?', (item['staff_id'],)).fetchone()
                item['employee_nickname'] = emp['nickname'] if emp else ''
            else:
                item['employee_nickname'] = ''
        
        sale['payments'] = [dict(payment) for payment in db.execute('SELECT * FROM payments WHERE sale_id=?', (sale_id,)).fetchall()]
        
        if sale.get('customer_id'):
            customer = db.execute('SELECT phone FROM customers WHERE id=?', (sale['customer_id'],)).fetchone()
            sale['customer_phone'] = customer['phone'] if customer else ''
        else:
            sale['customer_phone'] = ''
        
        sale['is_return'] = 1 if sale.get('status') == 'returned' else 0
        
        account_transaction = db.execute(
            "SELECT account_id FROM transactions WHERE reference_type='sale' AND reference_id=? LIMIT 1",
            (sale_id,)
        ).fetchone()
        sale['account_id'] = account_transaction['account_id'] if account_transaction else None
        
        return jsonify(sale)
