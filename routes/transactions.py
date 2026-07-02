from flask import Blueprint, request, jsonify
import json
from database import get_db
from routes.auth import login_required, manager_required

txn_bp = Blueprint('transactions', __name__, url_prefix='/api')


def get_balance_effect(txn_type):
    return 1 if txn_type == 'receipt' else -1


def get_customer_sale_effect(txn_type):
    """Receipt from customer reduces credit, payment to customer increases credit."""
    return -1 if txn_type == 'receipt' else 1


def get_supplier_balance_effect(txn_type):
    """Receipt from supplier reduces balance (refund), payment to supplier reduces balance (bill payment)."""
    return -1


def get_invoice_sign(txn_type, party_type):
    """Returns +1 or -1 for how amount affects the invoice balance field.
    receipt+customer: +paid   payment+customer: -paid
    payment+supplier: -due    receipt+supplier: +due"""
    if party_type == 'customer':
        return 1 if txn_type == 'receipt' else -1
    return -1 if txn_type == 'payment' else 1


def update_sale_paid(db, sale_id, amount, is_receipt):
    sale = db.execute('SELECT total,paid FROM sales WHERE id=?', (sale_id,)).fetchone()
    if not sale:
        return
    sign = 1 if is_receipt else -1
    new_paid = max(sale['paid'] + sign * amount, 0)
    db.execute('UPDATE sales SET paid=? WHERE id=?', (new_paid, sale_id))
    update_sale_due(db, sale_id)


def update_sale_due(db, sale_id):
    sale = db.execute('SELECT total,paid FROM sales WHERE id=?', (sale_id,)).fetchone()
    if not sale:
        return
    if sale['paid'] > sale['total']:
        db.execute("UPDATE sales SET status='Overpaid' WHERE id=?", (sale_id,))
    elif sale['paid'] == sale['total']:
        db.execute("UPDATE sales SET status='Paid' WHERE id=?", (sale_id,))
    elif sale['paid'] > 0:
        db.execute("UPDATE sales SET status='Partial' WHERE id=?", (sale_id,))
    else:
        db.execute("UPDATE sales SET status='Unpaid' WHERE id=?", (sale_id,))


def update_purchase_due(db, inv_id, amount, is_payment):
    inv = db.execute('SELECT balance_due,invoice_amount FROM purchase_invoices WHERE id=?', (inv_id,)).fetchone()
    if not inv:
        return
    sign = -1 if is_payment else 1
    new_due = min(inv['balance_due'] + sign * amount, inv['invoice_amount'])
    db.execute('UPDATE purchase_invoices SET balance_due=? WHERE id=?', (new_due, inv_id))
    if new_due < 0:
        db.execute("UPDATE purchase_invoices SET status='Overpaid' WHERE id=?", (inv_id,))
    elif new_due == 0:
        db.execute("UPDATE purchase_invoices SET status='Paid' WHERE id=?", (inv_id,))
    elif new_due < inv['invoice_amount']:
        db.execute("UPDATE purchase_invoices SET status='Partial' WHERE id=?", (inv_id,))
    else:
        db.execute("UPDATE purchase_invoices SET status='Unpaid' WHERE id=?", (inv_id,))


def apply_to_invoice(db, txn_type, party_type, party_id, amount, reference_type, reference_id):
    """Apply transaction to invoice(s) with cascading. Returns (ref_type, ref_id, allocations).
    allocations is a list of {ref_type, ref_id, amount} tuples for all invoices touched."""
    if not party_id:
        return reference_type, reference_id, []
    is_receipt = txn_type == 'receipt'
    is_payment = txn_type == 'payment'
    allocations = []

    if party_type == 'customer':
        if reference_type == 'sale' and reference_id:
            update_sale_paid(db, reference_id, amount, is_receipt)
            allocations.append({'ref_type': 'sale', 'ref_id': reference_id, 'amount': amount})
            return 'sale', reference_id, allocations
        # Cascade across all open sales for this customer
        remaining = amount
        while remaining > 0:
            oldest = db.execute(
                "SELECT id,total,paid FROM sales WHERE customer_id=? AND status IN ('Unpaid','Partial') AND paid<total ORDER BY created_at LIMIT 1",
                (party_id,)
            ).fetchone()
            if not oldest:
                break
            apply_amt = min(remaining, oldest['total'] - oldest['paid'])
            if apply_amt <= 0:
                break
            update_sale_paid(db, oldest['id'], apply_amt, is_receipt)
            allocations.append({'ref_type': 'sale', 'ref_id': oldest['id'], 'amount': apply_amt})
            remaining -= apply_amt
        if allocations:
            first = allocations[0]
            return first['ref_type'], first['ref_id'], allocations
    elif party_type == 'supplier':
        if reference_type == 'purchase' and reference_id:
            update_purchase_due(db, reference_id, amount, is_payment)
            allocations.append({'ref_type': 'purchase', 'ref_id': reference_id, 'amount': amount})
            return 'purchase', reference_id, allocations
        # Cascade across all open purchase invoices for this supplier
        remaining = amount
        while remaining > 0:
            oldest = db.execute(
                'SELECT id,balance_due FROM purchase_invoices WHERE supplier_id=? AND balance_due>0 ORDER BY created_at LIMIT 1',
                (party_id,)
            ).fetchone()
            if not oldest:
                break
            apply_amt = min(remaining, oldest['balance_due'])
            if apply_amt <= 0:
                break
            update_purchase_due(db, oldest['id'], apply_amt, is_payment)
            allocations.append({'ref_type': 'purchase', 'ref_id': oldest['id'], 'amount': apply_amt})
            remaining -= apply_amt
        if allocations:
            first = allocations[0]
            return first['ref_type'], first['ref_id'], allocations
    return None, None, allocations


def reverse_allocations(db, txn_type, allocations_json):
    """Reverse all allocations recorded on a transaction."""
    if not allocations_json:
        return
    try:
        allocations = json.loads(allocations_json) if isinstance(allocations_json, str) else allocations_json
    except Exception:
        return
    if not allocations:
        return
    is_receipt = txn_type == 'receipt'
    is_payment = txn_type == 'payment'
    # Reverse in reverse order so balances end up correct
    for alloc in reversed(allocations):
        if alloc['ref_type'] == 'sale':
            update_sale_paid(db, alloc['ref_id'], alloc['amount'], not is_receipt)
        elif alloc['ref_type'] == 'purchase':
            update_purchase_due(db, alloc['ref_id'], alloc['amount'], not is_payment)


def reverse_invoice_effect(db, txn_type, amount, reference_type, reference_id, allocations_json=None):
    """Backwards-compat shim. Uses allocations if provided, else falls back to single-invoice reverse."""
    if allocations_json:
        reverse_allocations(db, txn_type, allocations_json)
        return
    if not reference_id:
        return
    is_receipt = txn_type == 'receipt'
    is_payment = txn_type == 'payment'
    if reference_type == 'sale':
        update_sale_paid(db, reference_id, amount, not is_receipt)
    elif reference_type == 'purchase':
        update_purchase_due(db, reference_id, amount, not is_payment)


@txn_bp.route('/transactions')
@login_required
def list_transactions():
    t = request.args.get('type', 'receipt')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    offset = (page - 1) * per_page
    
    with get_db() as db:
        # Get total count
        count_row = db.execute(
            'SELECT COUNT(*) as cnt FROM transactions WHERE type=?', (t,)
        ).fetchone()
        total = count_row['cnt']
        
        # Get paginated results
        rows = db.execute(
            'SELECT t.*, a.name as account_name FROM transactions t '
            'JOIN accounts a ON a.id=t.account_id '
            'WHERE t.type=? ORDER BY t.date DESC, t.id DESC LIMIT ? OFFSET ?', 
            (t, per_page, offset)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d['party_type'] == 'customer' and d['party_id']:
                c = db.execute('SELECT name FROM customers WHERE id=?', (d['party_id'],)).fetchone()
                d['party_name'] = c['name'] if c else ''
            elif d['party_type'] == 'supplier' and d['party_id']:
                s = db.execute('SELECT name FROM suppliers WHERE id=?', (d['party_id'],)).fetchone()
                d['party_name'] = s['name'] if s else ''
            elif d['party_type'] == 'expense':
                d['party_name'] = d.get('expense_category') or 'Expense'
            else:
                d['party_name'] = ''
            if d['reference_type'] == 'sale' and d['reference_id']:
                sl = db.execute('SELECT receipt FROM sales WHERE id=?', (d['reference_id'],)).fetchone()
                d['reference_label'] = sl['receipt'] if sl else ''
            elif d['reference_type'] == 'purchase' and d['reference_id']:
                pi = db.execute('SELECT invoice_no FROM purchase_invoices WHERE id=?', (d['reference_id'],)).fetchone()
                d['reference_label'] = pi['invoice_no'] if pi else ''
            else:
                d['reference_label'] = ''
            # Add allocation labels for cascade display
            try:
                allocs = json.loads(d.get('allocations') or '[]')
            except Exception:
                allocs = []
            if allocs:
                labels = []
                for a in allocs:
                    if a['ref_type'] == 'sale':
                        sl2 = db.execute('SELECT receipt FROM sales WHERE id=?', (a['ref_id'],)).fetchone()
                        lbl = sl2['receipt'] if sl2 else '#' + str(a['ref_id'])
                    elif a['ref_type'] == 'purchase':
                        pi2 = db.execute('SELECT invoice_no FROM purchase_invoices WHERE id=?', (a['ref_id'],)).fetchone()
                        lbl = pi2['invoice_no'] if pi2 else '#' + str(a['ref_id'])
                    else:
                        lbl = '#' + str(a['ref_id'])
                    labels.append(f"{lbl} (Rs {a['amount']:.2f})")
                d['allocation_labels'] = ' + '.join(labels) if len(labels) > 1 else labels[0] if labels else ''
            else:
                d['allocation_labels'] = ''
            result.append(d)
        return jsonify({
            'items': result,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })


@txn_bp.route('/transactions', methods=['POST'])
@login_required
@manager_required
def add_transaction():
    d = request.get_json() or {}
    t = d.get('type', 'receipt')
    sign = get_balance_effect(t)
    account_id = int(d.get('account_id', 0) or 0)
    amount = float(d.get('amount', 0) or 0)
    party_type = d.get('party_type', 'other')
    party_id = int(d['party_id']) if d.get('party_id') else None
    reference_type = d.get('reference_type') or None
    reference_id = int(d['reference_id']) if d.get('reference_id') else None
    expense_category = (d.get('expense_category') or '').strip() or None
    with get_db() as db:
        try:
            ref_type, ref_id, allocations = apply_to_invoice(db, t, party_type, party_id, amount, reference_type, reference_id)
            if reference_type and reference_id:
                ref_type, ref_id = reference_type, reference_id
                allocations = [{'ref_type': reference_type, 'ref_id': reference_id, 'amount': amount}]
            allocations_json = json.dumps(allocations)
            cur = db.execute(
                'INSERT INTO transactions (account_id, type, amount, description, party_type, party_id, reference_type, reference_id, allocations, expense_category, date) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (account_id, t, amount, d.get('description', '') or '', party_type, party_id, ref_type, ref_id, allocations_json, expense_category, d.get('date', '') or '')
            )
            db.execute('UPDATE accounts SET balance=balance+? WHERE id=?', (sign * amount, account_id))
            if party_type == 'customer' and party_id:
                effect = get_customer_sale_effect(t)
                db.execute('UPDATE customers SET credit=credit+? WHERE id=?', (effect * amount, party_id))
            elif party_type == 'supplier' and party_id:
                effect = get_supplier_balance_effect(t)
                db.execute('UPDATE suppliers SET balance=balance+? WHERE id=?', (effect * amount, party_id))
            elif party_type == 'expense' and expense_category and t == 'payment':
                db.execute('INSERT INTO expenses (category, amount, note) VALUES (?,?,?)',
                           (expense_category, amount, d.get('description', '') or ''))
            return jsonify({'ok': True, 'id': cur.lastrowid, 'allocations': allocations})
        except Exception as e:
            return jsonify({'error': str(e)}), 400


@txn_bp.route('/transactions/<int:tid>', methods=['PUT'])
@login_required
@manager_required
def update_transaction(tid):
    d = request.get_json() or {}
    t = d.get('type', 'receipt')
    account_id = int(d.get('account_id', 0) or 0)
    amount = float(d.get('amount', 0) or 0)
    party_type = d.get('party_type', 'other')
    party_id = int(d['party_id']) if d.get('party_id') else None
    reference_type = d.get('reference_type') or None
    reference_id = int(d['reference_id']) if d.get('reference_id') else None
    expense_category = (d.get('expense_category') or '').strip() or None
    with get_db() as db:
        try:
            old_row = db.execute('SELECT * FROM transactions WHERE id=?', (tid,)).fetchone()
            if not old_row:
                return jsonify({'error': 'not found'}), 404
            old = dict(old_row)

            reverse_allocations(db, old['type'], old['allocations'])

            old_sign = get_balance_effect(old['type'])
            old_effect = old_sign * old['amount']
            if old['party_type'] == 'customer' and old['party_id']:
                old_cust_effect = get_customer_sale_effect(old['type']) * old['amount']
                db.execute('UPDATE customers SET credit=credit-? WHERE id=?', (old_cust_effect, old['party_id']))
            elif old['party_type'] == 'supplier' and old['party_id']:
                old_sup_effect = get_supplier_balance_effect(old['type']) * old['amount']
                db.execute('UPDATE suppliers SET balance=balance-? WHERE id=?', (old_sup_effect, old['party_id']))
            elif old['party_type'] == 'expense' and old['expense_category'] and old['type'] == 'payment':
                db.execute('DELETE FROM expenses WHERE rowid IN (SELECT rowid FROM expenses WHERE category=? ORDER BY id DESC LIMIT 1) AND amount=?',
                           (old['expense_category'], old['amount']))

            ref_type, ref_id, allocations = apply_to_invoice(db, t, party_type, party_id, amount, reference_type, reference_id)
            if reference_type and reference_id:
                ref_type, ref_id = reference_type, reference_id
                allocations = [{'ref_type': reference_type, 'ref_id': reference_id, 'amount': amount}]
            allocations_json = json.dumps(allocations)

            new_sign = get_balance_effect(t)
            new_effect = new_sign * amount
            diff = new_effect - old_effect
            db.execute(
                'UPDATE transactions SET account_id=?, type=?, amount=?, description=?, party_type=?, party_id=?, reference_type=?, reference_id=?, allocations=?, expense_category=?, date=? WHERE id=?',
                (account_id, t, amount, d.get('description', '') or '', party_type, party_id, ref_type, ref_id, allocations_json, expense_category, d.get('date', '') or '', tid)
            )
            db.execute('UPDATE accounts SET balance=balance+? WHERE id=?', (diff, old['account_id']))
            if old['account_id'] != account_id:
                db.execute('UPDATE accounts SET balance=balance-? WHERE id=?', (new_effect, account_id))

            if party_type == 'customer' and party_id:
                effect = get_customer_sale_effect(t)
                db.execute('UPDATE customers SET credit=credit+? WHERE id=?', (effect * amount, party_id))
            elif party_type == 'supplier' and party_id:
                effect = get_supplier_balance_effect(t)
                db.execute('UPDATE suppliers SET balance=balance+? WHERE id=?', (effect * amount, party_id))
            elif party_type == 'expense' and expense_category and t == 'payment':
                db.execute('INSERT INTO expenses (category, amount, note) VALUES (?,?,?)',
                           (expense_category, amount, d.get('description', '') or ''))

            return jsonify({'ok': True, 'allocations': allocations})
        except Exception as e:
            return jsonify({'error': str(e)}), 400


@txn_bp.route('/transactions/<int:tid>', methods=['DELETE'])
@login_required
@manager_required
def delete_transaction(tid):
    with get_db() as db:
        txn_row = db.execute('SELECT * FROM transactions WHERE id=?', (tid,)).fetchone()
        if not txn_row:
            return jsonify({'error': 'not found'}), 404
        txn = dict(txn_row)

        reverse_allocations(db, txn['type'], txn['allocations'])

        sign = get_balance_effect(txn['type'])
        db.execute('UPDATE accounts SET balance=balance-? WHERE id=?', (sign * txn['amount'], txn['account_id']))

        if txn['party_type'] == 'customer' and txn['party_id']:
            effect = get_customer_sale_effect(txn['type'])
            db.execute('UPDATE customers SET credit=credit-? WHERE id=?', (effect * txn['amount'], txn['party_id']))
        elif txn['party_type'] == 'supplier' and txn['party_id']:
            effect = get_supplier_balance_effect(txn['type'])
            db.execute('UPDATE suppliers SET balance=balance-? WHERE id=?', (effect * txn['amount'], txn['party_id']))
        elif txn['party_type'] == 'expense' and txn['expense_category'] and txn['type'] == 'payment':
            db.execute('DELETE FROM expenses WHERE rowid IN (SELECT rowid FROM expenses WHERE category=? ORDER BY id DESC LIMIT 1) AND amount=?',
                       (txn['expense_category'], txn['amount']))

        db.execute('DELETE FROM transactions WHERE id=?', (tid,))
        return jsonify({'ok': True})


@txn_bp.route('/expense-categories')
@login_required
def list_expense_categories():
    """Return the standard expense categories used in the summary, with current totals."""
    cats = ['Utility Expense', 'Staff Salaries', 'Staff Commissions', 'Maintenance Expense', 'Miscellaneous Expense', 'P1', 'P2']
    with get_db() as db:
        rows = db.execute(
            "SELECT category, COALESCE(SUM(amount),0) as total FROM expenses GROUP BY category"
        ).fetchall()
        totals = {r['category']: r['total'] for r in rows}
    return jsonify([
        {'name': c, 'total': round(totals.get(c, 0), 2)} for c in cats
    ])
