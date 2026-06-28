from flask import Blueprint, request, jsonify
from database import get_db
from routes.auth import login_required

cust_bp = Blueprint('customers', __name__, url_prefix='/api')


@cust_bp.route('/customers')
@login_required
def list_customers():
    q = request.args.get('q', '')
    with get_db() as db:
        if q:
            rows = db.execute(
                'SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? ORDER BY name',
                (f'%{q}%', f'%{q}%')
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM customers ORDER BY name').fetchall()
        return jsonify([dict(r) for r in rows])


@cust_bp.route('/customers', methods=['POST'])
@login_required
def add_customer():
    d = request.get_json()
    with get_db() as db:
        try:
            cur = db.execute(
                'INSERT INTO customers (name, phone, email, address, baby_name, baby_birth, notes, credit) VALUES (?,?,?,?,?,?,?,?)',
                (d['name'], d.get('phone', ''), d.get('email', ''), d.get('address', ''),
                 d.get('baby_name', ''), d.get('baby_birth', ''), d.get('notes', ''),
                 float(d.get('credit', 0)))
            )
            return jsonify({'ok': True, 'id': cur.lastrowid})
        except Exception as e:
            return jsonify({'error': str(e)}), 400


@cust_bp.route('/customers/<int:cid>', methods=['PUT'])
@login_required
def update_customer(cid):
    d = request.get_json()
    with get_db() as db:
        db.execute(
            'UPDATE customers SET name=?, phone=?, email=?, address=?, baby_name=?, baby_birth=?, notes=?, credit=? WHERE id=?',
            (d['name'], d.get('phone', ''), d.get('email', ''), d.get('address', ''),
             d.get('baby_name', ''), d.get('baby_birth', ''), d.get('notes', ''),
             float(d.get('credit', 0)), cid)
        )
        return jsonify({'ok': True})


@cust_bp.route('/customers/<int:cid>', methods=['DELETE'])
@login_required
def delete_customer(cid):
    with get_db() as db:
        db.execute('UPDATE sales SET customer_id=NULL, customer_name="Deleted" WHERE customer_id=?', (cid,))
        db.execute('DELETE FROM customers WHERE id=?', (cid,))
        return jsonify({'ok': True})


@cust_bp.route('/customers/<int:cid>/history')
@login_required
def customer_history(cid):
    with get_db() as db:
        sales = db.execute(
            'SELECT * FROM sales WHERE customer_id=? ORDER BY id DESC LIMIT 50',
            (cid,)
        ).fetchall()
        return jsonify({
            'sales': [dict(r) for r in sales],
        })


@cust_bp.route('/customers/<int:cid>/invoices')
@login_required
def customer_invoices(cid):
    with get_db() as db:
        rows = db.execute(
            "SELECT id, receipt, subtotal, total, paid, (total-paid) as outstanding, created_at "
            "FROM sales WHERE customer_id=? AND status IN ('Unpaid','Partial') AND total>paid "
            "ORDER BY created_at", (cid,)
        ).fetchall()
        return jsonify([dict(r) for r in rows])
