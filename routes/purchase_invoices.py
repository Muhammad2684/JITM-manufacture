from flask import Blueprint, request, jsonify, session
from database import get_db
from routes.auth import login_required, manager_required

pi_bp = Blueprint('purchase_invoices', __name__, url_prefix='/api')


def find_default_variant(db, product_id):
    return db.execute(
        'SELECT id, stock FROM variants WHERE product_id=? ORDER BY id LIMIT 1',
        (product_id,)
    ).fetchone()


def update_weighted_avg_cost(db, product_id):
    total_row = db.execute(
        'SELECT COALESCE(SUM(r.qty_added * r.cost),0) as total_cost, COALESCE(SUM(r.qty_added),0) as total_qty '
        'FROM restock_log r JOIN variants v ON v.id=r.variant_id '
        'WHERE v.product_id=? AND r.cost > 0',
        (product_id,)
    ).fetchone()
    if total_row and total_row['total_qty'] > 0:
        avg = round(total_row['total_cost'] / total_row['total_qty'], 2)
        db.execute('UPDATE products SET cost_price=? WHERE id=?', (avg, product_id))


def apply_stock_change(db, product_id, qty, cost, ref, staff_name):
    variant = find_default_variant(db, product_id)
    if not variant:
        return
    old_stock = variant['stock']
    new_stock = old_stock + qty
    db.execute('UPDATE variants SET stock=? WHERE id=?', (new_stock, variant['id']))
    db.execute(
        'INSERT INTO restock_log (variant_id, old_stock, new_stock, qty_added, cost, note, staff_name) VALUES (?,?,?,?,?,?,?)',
        (variant['id'], old_stock, new_stock, qty, cost, ref, staff_name)
    )
    update_weighted_avg_cost(db, product_id)


def auto_link_product(db, item):
    """Resolve product_id by exact name match (case-insensitive) when not explicitly set."""
    if item.get('product_id'):
        return item['product_id']
    name = (item.get('item') or '').strip()
    if not name:
        return None
    row = db.execute(
        'SELECT id FROM products WHERE LOWER(TRIM(name)) = LOWER(?)',
        (name,)
    ).fetchone()
    return row['id'] if row else None


@pi_bp.route('/purchase-invoices')
@login_required
def list_purchase_invoices():
    with get_db() as db:
        rows = db.execute(
            'SELECT pi.*, s.name as supplier_name FROM purchase_invoices pi '
            'LEFT JOIN suppliers s ON s.id=pi.supplier_id ORDER BY pi.id DESC'
        ).fetchall()
        return jsonify([dict(r) for r in rows])


@pi_bp.route('/purchase-invoices/<int:piid>')
@login_required
def get_purchase_invoice(piid):
    with get_db() as db:
        inv = db.execute(
            'SELECT pi.*, s.name as supplier_name FROM purchase_invoices pi '
            'LEFT JOIN suppliers s ON s.id=pi.supplier_id WHERE pi.id=?', (piid,)
        ).fetchone()
        if not inv:
            return jsonify({'error': 'Not found'}), 404
        items = db.execute(
            'SELECT * FROM purchase_invoice_items WHERE invoice_id=? ORDER BY line_number', (piid,)
        ).fetchall()
        result = dict(inv)
        result['items'] = [dict(i) for i in items]
        return jsonify(result)


@pi_bp.route('/purchase-invoices', methods=['POST'])
@login_required
@manager_required
def create_purchase_invoice():
    d = request.get_json()
    with get_db() as db:
        try:
            cur = db.execute(
                'INSERT INTO purchase_invoices (invoice_no, issue_date, due_date, supplier_id, description, invoice_amount, balance_due, status) VALUES (?,?,?,?,?,?,?,?)',
                (d['invoice_no'], d.get('issue_date', ''), d.get('due_date', ''),
                 d.get('supplier_id'), d.get('description', ''),
                 float(d.get('invoice_amount', 0)), float(d.get('balance_due', 0)),
                 d.get('status', 'Unpaid'))
            )
            piid = cur.lastrowid
            staff = session.get('name', '')
            ref = 'PI #' + d['invoice_no']
            for item in d.get('items', []):
                pid = auto_link_product(db, item)
                db.execute(
                    'INSERT INTO purchase_invoice_items (invoice_id, line_number, item, product_id, qty, unit_price, total) VALUES (?,?,?,?,?,?,?)',
                    (piid, int(item.get('line_number', 0)), item.get('item', ''),
                     pid, float(item.get('qty', 1)),
                     float(item.get('unit_price', 0)), float(item.get('total', 0)))
                )
                if pid:
                    qty = float(item.get('qty', 1))
                    cost = float(item.get('unit_price', 0))
                    apply_stock_change(db, pid, int(qty), cost, ref, staff)
            if d.get('supplier_id') and float(d.get('balance_due', 0)):
                db.execute('UPDATE suppliers SET balance = COALESCE(balance,0) + ? WHERE id=?',
                           (float(d['balance_due']), d['supplier_id']))
            return jsonify({'ok': True, 'id': piid})
        except Exception as e:
            return jsonify({'error': str(e)}), 400


@pi_bp.route('/purchase-invoices/<int:piid>', methods=['PUT'])
@login_required
@manager_required
def update_purchase_invoice(piid):
    d = request.get_json()
    with get_db() as db:
        try:
            old = db.execute('SELECT balance_due, supplier_id FROM purchase_invoices WHERE id=?', (piid,)).fetchone()
            db.execute(
                'UPDATE purchase_invoices SET invoice_no=?, issue_date=?, due_date=?, supplier_id=?, description=?, invoice_amount=?, balance_due=?, status=? WHERE id=?',
                (d['invoice_no'], d.get('issue_date', ''), d.get('due_date', ''),
                 d.get('supplier_id'), d.get('description', ''),
                 float(d.get('invoice_amount', 0)), float(d.get('balance_due', 0)),
                 d.get('status', 'Unpaid'), piid)
            )
            if old and old['supplier_id']:
                old_bal = float(old['balance_due'] or 0)
                new_bal = float(d.get('balance_due', 0))
                new_sid = d.get('supplier_id')
                if old['supplier_id'] == new_sid:
                    if old_bal != new_bal:
                        db.execute('UPDATE suppliers SET balance = COALESCE(balance,0) + ? WHERE id=?',
                                   (round(new_bal - old_bal, 2), old['supplier_id']))
                else:
                    if old_bal:
                        db.execute('UPDATE suppliers SET balance = COALESCE(balance,0) - ? WHERE id=?',
                                   (old_bal, old['supplier_id']))
                    if new_sid and new_bal:
                        db.execute('UPDATE suppliers SET balance = COALESCE(balance,0) + ? WHERE id=?',
                                   (new_bal, new_sid))
            return jsonify({'ok': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 400


@pi_bp.route('/purchase-invoices/<int:piid>', methods=['DELETE'])
@login_required
@manager_required
def delete_purchase_invoice(piid):
    with get_db() as db:
        inv = db.execute('SELECT invoice_no, balance_due, supplier_id FROM purchase_invoices WHERE id=?', (piid,)).fetchone()
        if inv:
            items = db.execute(
                'SELECT product_id, qty, unit_price FROM purchase_invoice_items WHERE invoice_id=?', (piid,)
            ).fetchall()
            staff = session.get('name', '')
            ref = 'DEL #' + inv['invoice_no']
            for item in items:
                pid = item['product_id']
                if pid:
                    apply_stock_change(db, pid, -int(item['qty']), float(item['unit_price'] or 0), ref, staff)
        db.execute('DELETE FROM purchase_invoice_items WHERE invoice_id=?', (piid,))
        db.execute('DELETE FROM purchase_invoices WHERE id=?', (piid,))
        if inv and inv['supplier_id'] and float(inv['balance_due'] or 0):
            db.execute('UPDATE suppliers SET balance = COALESCE(balance,0) - ? WHERE id=?',
                       (float(inv['balance_due']), inv['supplier_id']))
        return jsonify({'ok': True})
