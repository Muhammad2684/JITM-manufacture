from flask import Blueprint, request, jsonify
from database import get_db
from routes.auth import login_required, manager_required

pi_bp = Blueprint('purchase_invoices', __name__, url_prefix='/api')


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
            for item in d.get('items', []):
                db.execute(
                    'INSERT INTO purchase_invoice_items (invoice_id, line_number, item, product_id, qty, unit_price, total) VALUES (?,?,?,?,?,?,?)',
                    (piid, int(item.get('line_number', 0)), item.get('item', ''),
                     item.get('product_id'), float(item.get('qty', 1)),
                     float(item.get('unit_price', 0)), float(item.get('total', 0)))
                )
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
            db.execute(
                'UPDATE purchase_invoices SET invoice_no=?, issue_date=?, due_date=?, supplier_id=?, description=?, invoice_amount=?, balance_due=?, status=? WHERE id=?',
                (d['invoice_no'], d.get('issue_date', ''), d.get('due_date', ''),
                 d.get('supplier_id'), d.get('description', ''),
                 float(d.get('invoice_amount', 0)), float(d.get('balance_due', 0)),
                 d.get('status', 'Unpaid'), piid)
            )
            db.execute('DELETE FROM purchase_invoice_items WHERE invoice_id=?', (piid,))
            for item in d.get('items', []):
                db.execute(
                    'INSERT INTO purchase_invoice_items (invoice_id, line_number, item, product_id, qty, unit_price, total) VALUES (?,?,?,?,?,?,?)',
                    (piid, int(item.get('line_number', 0)), item.get('item', ''),
                     item.get('product_id'), float(item.get('qty', 1)),
                     float(item.get('unit_price', 0)), float(item.get('total', 0)))
                )
            return jsonify({'ok': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 400


@pi_bp.route('/purchase-invoices/<int:piid>', methods=['DELETE'])
@login_required
@manager_required
def delete_purchase_invoice(piid):
    with get_db() as db:
        db.execute('DELETE FROM purchase_invoice_items WHERE invoice_id=?', (piid,))
        db.execute('DELETE FROM purchase_invoices WHERE id=?', (piid,))
        return jsonify({'ok': True})
