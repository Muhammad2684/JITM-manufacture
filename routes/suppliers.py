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


@sup_bp.route('/suppliers/ledger')
@login_required
def supplier_ledger():
    with get_db() as db:
        rows = db.execute('SELECT id, name, phone, balance FROM suppliers ORDER BY name').fetchall()
        return jsonify([dict(r) for r in rows])


@sup_bp.route('/suppliers/<int:sid>/khata')
@login_required
def get_supplier_khata(sid):
    with get_db() as db:
        supplier = db.execute('SELECT id, name, balance FROM suppliers WHERE id=?', (sid,)).fetchone()
        if not supplier:
            return jsonify({'error': 'Supplier not found'}), 404
        entries = db.execute(
            'SELECT * FROM supplier_khata WHERE supplier_id=? ORDER BY id DESC LIMIT 100',
            (sid,)
        ).fetchall()
        return jsonify({
            'customer': dict(supplier),
            'entries': [dict(r) for r in entries],
        })


@sup_bp.route('/suppliers/khata', methods=['POST'])
@login_required
def add_supplier_khata_entry():
    d = request.get_json()
    sid = d['customer_id']
    typ = d['type']
    amount = float(d['amount'])
    note = d.get('note', '')

    with get_db() as db:
        supplier = db.execute('SELECT * FROM suppliers WHERE id=?', (sid,)).fetchone()
        if not supplier:
            return jsonify({'error': 'Supplier not found'}), 404

        current_balance = supplier['balance']
        if typ == 'payment':
            new_balance = round(current_balance - amount, 2)
        elif typ == 'credit':
            new_balance = round(current_balance + amount, 2)
        else:
            new_balance = current_balance

        db.execute(
            'INSERT INTO supplier_khata (supplier_id, type, amount, balance, note, staff_name) VALUES (?,?,?,?,?,?)',
            (sid, typ, amount, new_balance, note, session.get('name', ''))
        )
        db.execute('UPDATE suppliers SET balance=? WHERE id=?', (new_balance, sid))

        return jsonify({'ok': True, 'balance': new_balance})
