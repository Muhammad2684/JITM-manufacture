from flask import Blueprint, request, jsonify, session
from database import get_db
from routes.auth import login_required

khata_bp = Blueprint('khata', __name__, url_prefix='/api')


@khata_bp.route('/khata/<int:cid>')
@login_required
def get_khata(cid):
    with get_db() as db:
        customer = db.execute('SELECT id, name, credit FROM customers WHERE id=?', (cid,)).fetchone()
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        entries = db.execute(
            'SELECT * FROM khata WHERE customer_id=? ORDER BY id DESC LIMIT 100',
            (cid,)
        ).fetchall()
        return jsonify({
            'customer': dict(customer),
            'entries': [dict(r) for r in entries],
        })


@khata_bp.route('/khata', methods=['POST'])
@login_required
def add_khata_entry():
    d = request.get_json()
    cid = d['customer_id']
    typ = d['type']
    amount = float(d['amount'])
    note = d.get('note', '')
    sale_id = d.get('sale_id')

    with get_db() as db:
        customer = db.execute('SELECT * FROM customers WHERE id=?', (cid,)).fetchone()
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404

        current_balance = customer['credit']
        if typ == 'payment':
            new_balance = round(current_balance - amount, 2)
        elif typ == 'credit':
            new_balance = round(current_balance + amount, 2)
        else:
            new_balance = current_balance

        db.execute(
            'INSERT INTO khata (customer_id, type, amount, balance, sale_id, note, staff_name) VALUES (?,?,?,?,?,?,?)',
            (cid, typ, amount, new_balance, sale_id, note, session.get('name', ''))
        )
        db.execute('UPDATE customers SET credit=? WHERE id=?', (new_balance, cid))

        return jsonify({'ok': True, 'balance': new_balance})


@khata_bp.route('/khata/ledger')
@login_required
def ledger_all():
    with get_db() as db:
        customers = db.execute(
            'SELECT c.*, COALESCE((SELECT SUM(CASE WHEN k.type="credit" THEN k.amount ELSE -k.amount END) FROM khata k WHERE k.customer_id=c.id),0) as balance '
            'FROM customers c ORDER BY c.name'
        ).fetchall()
        return jsonify([dict(c) for c in customers])
