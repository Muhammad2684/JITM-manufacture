from flask import Blueprint, request, jsonify
from database import get_db
from routes.auth import login_required

payroll_bp = Blueprint('payroll', __name__, url_prefix='/api')


@payroll_bp.route('/employees')
@login_required
def list_employees():
    with get_db() as db:
        rows = db.execute(
            'SELECT * FROM employees WHERE active=1 ORDER BY name'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@payroll_bp.route('/employees', methods=['POST'])
@login_required
def add_employee():
    d = request.get_json()
    if not d or not d.get('name'):
        return jsonify({'error': 'Name is required'}), 400
    with get_db() as db:
        db.execute(
            'INSERT INTO employees (name, nickname, salary, commissions) VALUES (?,?,?,?)',
            (d['name'], d.get('nickname', '') or '', float(d.get('salary', 0) or 0), float(d.get('commissions', 0) or 0))
        )
    return jsonify({'ok': True})


@payroll_bp.route('/employees/<int:eid>', methods=['PUT'])
@login_required
def update_employee(eid):
    d = request.get_json()
    if not d:
        return jsonify({'error': 'No data'}), 400
    with get_db() as db:
        db.execute(
            'UPDATE employees SET name=?, nickname=?, salary=?, commissions=? WHERE id=?',
            (d['name'], d.get('nickname', '') or '', float(d.get('salary', 0) or 0), float(d.get('commissions', 0) or 0), eid)
        )
    return jsonify({'ok': True})


@payroll_bp.route('/employees/<int:eid>', methods=['DELETE'])
@login_required
def delete_employee(eid):
    with get_db() as db:
        db.execute('UPDATE employees SET active=0 WHERE id=?', (eid,))
    return jsonify({'ok': True})
