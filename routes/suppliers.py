from flask import Blueprint, request, jsonify, session
from database import get_db
from routes.auth import login_required, manager_required

sup_bp = Blueprint('suppliers', __name__, url_prefix='/api')


@sup_bp.route('/suppliers')
@login_required
def list_suppliers():
    with get_db() as db:
        rows = db.execute('SELECT * FROM suppliers ORDER BY name').fetchall()
        return jsonify([dict(r) for r in rows])


@sup_bp.route('/suppliers', methods=['POST'])
@login_required
@manager_required
def add_supplier():
    d = request.get_json()
    with get_db() as db:
        try:
            cur = db.execute(
                'INSERT INTO suppliers (name, phone, email, address, contact_person, notes, company_phone) VALUES (?,?,?,?,?,?,?)',
                (d['name'], d.get('phone', ''), d.get('email', ''), d.get('address', ''),
                 d.get('contact_person', ''), d.get('notes', ''), d.get('company_phone', ''))
            )
            return jsonify({'ok': True, 'id': cur.lastrowid})
        except Exception as e:
            return jsonify({'error': str(e)}), 400


@sup_bp.route('/suppliers/<int:sid>', methods=['PUT'])
@login_required
@manager_required
def update_supplier(sid):
    d = request.get_json()
    with get_db() as db:
        db.execute(
            'UPDATE suppliers SET name=?, phone=?, email=?, address=?, contact_person=?, notes=?, company_phone=? WHERE id=?',
            (d['name'], d.get('phone', ''), d.get('email', ''), d.get('address', ''),
             d.get('contact_person', ''), d.get('notes', ''), d.get('company_phone', ''), sid)
        )
        return jsonify({'ok': True})


@sup_bp.route('/suppliers/<int:sid>', methods=['DELETE'])
@login_required
@manager_required
def delete_supplier(sid):
    with get_db() as db:
        db.execute('DELETE FROM suppliers WHERE id=?', (sid,))
        return jsonify({'ok': True})


@sup_bp.route('/suppliers/<int:sid>/invoices')
@login_required
def supplier_invoices(sid):
    with get_db() as db:
        rows = db.execute(
            'SELECT id, invoice_no, issue_date, invoice_amount, balance_due, status '
            "FROM purchase_invoices WHERE supplier_id=? AND balance_due>0 ORDER BY created_at", (sid,)
        ).fetchall()
        return jsonify([dict(r) for r in rows])


@sup_bp.route('/suppliers/ledger')
@login_required
def supplier_ledger():
    with get_db() as db:
        rows = db.execute('SELECT id, name, phone, balance FROM suppliers ORDER BY name').fetchall()
        return jsonify([dict(r) for r in rows])


