from flask import Blueprint, jsonify, request
from database import get_db
from routes.auth import login_required

ledger_bp = Blueprint('ledger', __name__)


@ledger_bp.route('/api/ledger')
@login_required
def get_ledger():
    entity_type = request.args.get('type')
    entity_id = request.args.get('id', type=int)
    if not entity_type or not entity_id:
        return jsonify({'error': 'type and id required'}), 400

    with get_db() as db:
        if entity_type == 'customer':
            entity = db.execute('SELECT * FROM customers WHERE id=?', (entity_id,)).fetchone()
            if not entity:
                return jsonify({'error': 'not found'}), 404
            entity = dict(entity)
            entries = get_customer_entries(db, entity_id, entity)
        elif entity_type == 'supplier':
            entity = db.execute('SELECT * FROM suppliers WHERE id=?', (entity_id,)).fetchone()
            if not entity:
                return jsonify({'error': 'not found'}), 404
            entity = dict(entity)
            entries = get_supplier_entries(db, entity_id, entity)
        elif entity_type == 'account':
            entity = db.execute('SELECT * FROM accounts WHERE id=?', (entity_id,)).fetchone()
            if not entity:
                return jsonify({'error': 'not found'}), 404
            entity = dict(entity)
            entries = get_account_entries(db, entity_id, entity)
        elif entity_type == 'product':
            entity = db.execute('SELECT * FROM products WHERE id=?', (entity_id,)).fetchone()
            if not entity:
                return jsonify({'error': 'not found'}), 404
            entity = dict(entity)
            variants = db.execute('SELECT stock FROM variants WHERE product_id=?', (entity_id,)).fetchall()
            entity['total_stock'] = sum(v['stock'] for v in variants)
            entries = get_product_entries(db, entity_id, entity)
        else:
            return jsonify({'error': 'invalid type, use customer/supplier/account/product'}), 400

    return jsonify({'entity': entity, 'entries': entries})


def get_customer_entries(db, customer_id, entity):
    entries = []

    sales = db.execute(
        'SELECT id, receipt, total, created_at, due_date, status FROM sales WHERE customer_id=? ORDER BY created_at',
        (customer_id,)
    ).fetchall()
    for s in sales:
        s = dict(s)
        if s['status'] == 'returned':
            entries.append({
                'date': (s['created_at'] or '')[:10],
                'description': 'Sale Return',
                'reference': s['receipt'] or '',
                'debit': 0,
                'credit': abs(s['total']),
                'type': 'sale_return'
            })
        else:
            entries.append({
                'date': (s['created_at'] or '')[:10],
                'description': 'Sale',
                'reference': s['receipt'] or '',
                'debit': s['total'],
                'credit': 0,
                'type': 'sale'
            })

    receipts = db.execute(
        "SELECT * FROM transactions WHERE party_type='customer' AND party_id=? AND type='receipt' ORDER BY date, id",
        (customer_id,)
    ).fetchall()
    for r in receipts:
        r = dict(r)
        label = ''
        if r['reference_type'] == 'sale' and r['reference_id']:
            sl = db.execute('SELECT receipt FROM sales WHERE id=?', (r['reference_id'],)).fetchone()
            label = sl['receipt'] if sl else ''
        entries.append({
            'date': r['date'] or (r['created_at'] or '')[:10],
            'description': r['description'] or 'Receipt',
            'reference': label,
            'debit': 0,
            'credit': r['amount'],
            'type': 'receipt'
        })

    refunds = db.execute(
        "SELECT * FROM transactions WHERE party_type='customer' AND party_id=? AND type='payment' AND description LIKE '%Sale return%' ORDER BY date, id",
        (customer_id,)
    ).fetchall()
    for r in refunds:
        r = dict(r)
        label = ''
        if r['reference_type'] == 'sale' and r['reference_id']:
            sl = db.execute('SELECT receipt FROM sales WHERE id=?', (r['reference_id'],)).fetchone()
            label = sl['receipt'] if sl else ''
        entries.append({
            'date': r['date'] or (r['created_at'] or '')[:10],
            'description': 'Refund Payment',
            'reference': label,
            'debit': r['amount'],
            'credit': 0,
            'type': 'payment'
        })

    entries.sort(key=lambda e: e['date'])
    balance = 0
    for e in entries:
        balance += e['debit'] - e['credit']
        e['balance'] = round(balance, 2)

    # If there's a credit but no entries, show opening balance
    if not entries and entity['credit']:
        entity_credit = entity.get('credit', 0)
        entries.append({
            'date': '',
            'description': 'Opening Balance',
            'reference': '',
            'debit': entity_credit,
            'credit': 0,
            'balance': entity_credit,
            'type': 'opening'
        })

    return entries


def get_supplier_entries(db, supplier_id, entity):
    entries = []

    invoices = db.execute(
        'SELECT id, invoice_no, invoice_amount, issue_date, created_at FROM purchase_invoices WHERE supplier_id=? ORDER BY created_at',
        (supplier_id,)
    ).fetchall()
    for inv in invoices:
        inv = dict(inv)
        entries.append({
            'date': inv['issue_date'] or (inv['created_at'] or '')[:10],
            'description': 'Purchase Invoice',
            'reference': inv['invoice_no'] or '',
            'debit': inv['invoice_amount'],
            'credit': 0,
            'type': 'purchase'
        })

    payments = db.execute(
        "SELECT * FROM transactions WHERE party_type='supplier' AND party_id=? AND type='payment' ORDER BY date, id",
        (supplier_id,)
    ).fetchall()
    for p in payments:
        p = dict(p)
        label = ''
        if p['reference_type'] == 'purchase' and p['reference_id']:
            pi = db.execute('SELECT invoice_no FROM purchase_invoices WHERE id=?', (p['reference_id'],)).fetchone()
            label = pi['invoice_no'] if pi else ''
        entries.append({
            'date': p['date'] or (p['created_at'] or '')[:10],
            'description': p['description'] or 'Payment',
            'reference': label,
            'debit': 0,
            'credit': p['amount'],
            'type': 'payment'
        })

    receipts_back = db.execute(
        "SELECT * FROM transactions WHERE party_type='supplier' AND party_id=? AND type='receipt' ORDER BY date, id",
        (supplier_id,)
    ).fetchall()
    for r in receipts_back:
        r = dict(r)
        entries.append({
            'date': r['date'] or '',
            'description': r['description'] or 'Receipt from Supplier',
            'reference': '',
            'debit': r['amount'],
            'credit': 0,
            'type': 'receipt'
        })

    entries.sort(key=lambda e: e['date'])
    balance = 0
    for e in entries:
        balance += e['debit'] - e['credit']
        e['balance'] = round(balance, 2)

    if not entries and entity.get('balance', 0):
        bal = entity.get('balance', 0)
        entries.append({
            'date': '',
            'description': 'Opening Balance',
            'reference': '',
            'debit': bal,
            'credit': 0,
            'balance': bal,
            'type': 'opening'
        })

    return entries


def get_account_entries(db, account_id, entity):
    entries = []

    receipts = db.execute(
        "SELECT t.* FROM transactions t WHERE t.account_id=? AND t.type='receipt' ORDER BY t.date, t.id",
        (account_id,)
    ).fetchall()
    for r in receipts:
        r = dict(r)
        pname = ''
        if r['party_type'] == 'customer' and r['party_id']:
            c = db.execute('SELECT name FROM customers WHERE id=?', (r['party_id'],)).fetchone()
            pname = c['name'] if c else ''
        elif r['party_type'] == 'supplier' and r['party_id']:
            s = db.execute('SELECT name FROM suppliers WHERE id=?', (r['party_id'],)).fetchone()
            pname = s['name'] if s else ''

        label = ''
        if r['reference_type'] == 'sale' and r['reference_id']:
            sl = db.execute('SELECT receipt FROM sales WHERE id=?', (r['reference_id'],)).fetchone()
            label = sl['receipt'] if sl else ''

        desc = r['description'] or 'Receipt'
        if pname:
            desc = f"Receipt from {pname}"
        if label:
            desc += f" ({label})"

        entries.append({
            'date': r['date'] or '',
            'description': desc,
            'reference': label,
            'debit': r['amount'],
            'credit': 0,
            'type': 'receipt'
        })

    payments = db.execute(
        "SELECT t.* FROM transactions t WHERE t.account_id=? AND t.type='payment' ORDER BY t.date, t.id",
        (account_id,)
    ).fetchall()
    for p in payments:
        p = dict(p)
        pname = ''
        if p['party_type'] == 'customer' and p['party_id']:
            c = db.execute('SELECT name FROM customers WHERE id=?', (p['party_id'],)).fetchone()
            pname = c['name'] if c else ''
        elif p['party_type'] == 'supplier' and p['party_id']:
            s = db.execute('SELECT name FROM suppliers WHERE id=?', (p['party_id'],)).fetchone()
            pname = s['name'] if s else ''

        label = ''
        if p['reference_type'] == 'purchase' and p['reference_id']:
            pi = db.execute('SELECT invoice_no FROM purchase_invoices WHERE id=?', (p['reference_id'],)).fetchone()
            label = pi['invoice_no'] if pi else ''
        elif p['reference_type'] == 'sale' and p['reference_id']:
            sl = db.execute('SELECT receipt FROM sales WHERE id=?', (p['reference_id'],)).fetchone()
            label = sl['receipt'] if sl else ''

        # Check if this is a sale return
        if p['reference_type'] == 'sale' and p['description'] and 'Sale return' in p['description']:
            desc = f"Sale Return Refund"
            if pname:
                desc += f" to {pname}"
            if label:
                desc += f" ({label})"
            entries.append({
                'date': p['date'] or '',
                'description': desc,
                'reference': label,
                'debit': 0,
                'credit': p['amount'],
                'type': 'sale_return'
            })
        else:
            desc = p['description'] or 'Payment'
            if pname:
                desc = f"Payment to {pname}"
            if label:
                desc += f" ({label})"

            entries.append({
                'date': p['date'] or '',
                'description': desc,
                'reference': label,
                'debit': 0,
                'credit': p['amount'],
                'type': 'payment'
            })

    transfers_in = db.execute(
        'SELECT t.*, a.name as from_name FROM account_transfers t JOIN accounts a ON a.id=t.from_account_id WHERE t.to_account_id=? ORDER BY t.date, t.id',
        (account_id,)
    ).fetchall()
    for t in transfers_in:
        t = dict(t)
        entries.append({
            'date': t['date'] or '',
            'description': f"Transfer from {t['from_name']}",
            'reference': '',
            'debit': t['amount'],
            'credit': 0,
            'type': 'transfer_in'
        })

    transfers_out = db.execute(
        'SELECT t.*, a.name as to_name FROM account_transfers t JOIN accounts a ON a.id=t.to_account_id WHERE t.from_account_id=? ORDER BY t.date, t.id',
        (account_id,)
    ).fetchall()
    for t in transfers_out:
        t = dict(t)
        entries.append({
            'date': t['date'] or '',
            'description': f"Transfer to {t['to_name']}",
            'reference': '',
            'debit': 0,
            'credit': t['amount'],
            'type': 'transfer_out'
        })

    entries.sort(key=lambda e: e['date'])
    balance = entity.get('balance', 0)
    # Reverse compute: subtract all entries from current balance to get starting balance
    total_change = sum(e['debit'] - e['credit'] for e in entries)
    opening = round(balance - total_change, 2)
    if opening != 0 or entries:
        entries.insert(0, {
            'date': '',
            'description': 'Opening Balance',
            'reference': '',
            'debit': opening if opening > 0 else 0,
            'credit': -opening if opening < 0 else 0,
            'balance': opening,
            'type': 'opening'
        })

    balance = 0
    for e in entries:
        balance += e['debit'] - e['credit']
        e['balance'] = round(balance, 2)

    return entries


def get_product_entries(db, product_id, entity):
    entries = []

    sales = db.execute(
        'SELECT si.id, si.quantity, si.price, si.total, si.is_return, si.sku, '
        's.receipt, s.created_at, s.customer_name '
        'FROM sale_items si JOIN sales s ON s.id=si.sale_id '
        'WHERE si.product_id=? ORDER BY s.created_at',
        (product_id,)
    ).fetchall()
    for s in sales:
        s = dict(s)
        desc = 'Sale'
        if s['is_return']:
            desc = 'Sale Return'
        ref = s['receipt'] or ''
        if s['customer_name']:
            desc += ' - ' + s['customer_name']
        entries.append({
            'date': (s['created_at'] or '')[:10],
            'description': desc,
            'reference': ref,
            'qty': abs(s['quantity']),
            'debit': abs(s['total']) if s['is_return'] else 0,
            'credit': 0 if s['is_return'] else s['total'],
            'type': 'sale_return' if s['is_return'] else 'sale'
        })

    restocks = db.execute(
        'SELECT rl.id, rl.qty_added, rl.cost, rl.note, rl.staff_name, rl.created_at, '
        'v.sku '
        'FROM restock_log rl JOIN variants v ON v.id=rl.variant_id '
        'WHERE v.product_id=? ORDER BY rl.created_at',
        (product_id,)
    ).fetchall()
    for r in restocks:
        r = dict(r)
        total_cost = r['qty_added'] * r['cost']
        desc = 'Restock'
        if r['note']:
            desc += ' - ' + r['note']
        entries.append({
            'date': (r['created_at'] or '')[:10],
            'description': desc,
            'reference': r['sku'] or '',
            'qty': abs(r['qty_added']),
            'debit': total_cost,
            'credit': 0,
            'type': 'restock'
        })

    purchases = db.execute(
        'SELECT pii.id, pii.qty, pii.unit_price, pii.total, pii.item, '
        'pi.invoice_no, pi.issue_date, pi.created_at '
        'FROM purchase_invoice_items pii JOIN purchase_invoices pi ON pi.id=pii.invoice_id '
        'WHERE pii.product_id=? ORDER BY pi.created_at',
        (product_id,)
    ).fetchall()
    for p in purchases:
        p = dict(p)
        desc = 'Purchase'
        if p['item']:
            desc += ' - ' + p['item']
        entries.append({
            'date': p['issue_date'] or (p['created_at'] or '')[:10],
            'description': desc,
            'reference': p['invoice_no'] or '',
            'qty': abs(p['qty']),
            'debit': p['total'],
            'credit': 0,
            'type': 'purchase'
        })

    entries.sort(key=lambda e: e['date'])
    balance = 0
    for e in entries:
        balance += e['debit'] - e['credit']
        e['balance'] = round(balance, 2)

    return entries
