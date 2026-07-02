from flask import Blueprint, request, jsonify
from database import get_db
from routes.auth import login_required

payroll_bp = Blueprint('payroll', __name__, url_prefix='/api')


def fmt(v):
    return float(v or 0)


@payroll_bp.route('/employees')
@login_required
def list_employees():
    month = request.args.get('month')
    with get_db() as db:
        if month:
            rows = db.execute('''
                SELECT e.id, e.name, e.nickname, e.father_name, e.cnic, e.phone,
                       e.salary, e.leaves, e.absents, e.overtime, e.advance,
                       COALESCE((
                           SELECT SUM(si.commission)
                           FROM sale_items si
                           JOIN sales s ON s.id = si.sale_id
                           WHERE si.staff_id = e.id
                             AND strftime('%Y-%m', s.created_at) = ?
                       ), 0) as commissions
                FROM employees e
                WHERE e.active = 1
                ORDER BY e.name
            ''', (month,)).fetchall()
        else:
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
            '''INSERT INTO employees (name, nickname, father_name, cnic, phone, salary, commissions, leaves, absents, overtime, advance)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (d['name'], d.get('nickname', '') or '', d.get('father_name', '') or '',
             d.get('cnic', '') or '', d.get('phone', '') or '',
             fmt(d.get('salary')), fmt(d.get('commissions')),
             fmt(d.get('leaves')), fmt(d.get('absents')), fmt(d.get('overtime')), fmt(d.get('advance')))
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
            '''UPDATE employees SET name=?, nickname=?, father_name=?, cnic=?, phone=?,
               salary=?, commissions=?, leaves=?, absents=?, overtime=?, advance=? WHERE id=?''',
            (d['name'], d.get('nickname', '') or '', d.get('father_name', '') or '',
             d.get('cnic', '') or '', d.get('phone', '') or '',
             fmt(d.get('salary')), fmt(d.get('commissions')),
             fmt(d.get('leaves')), fmt(d.get('absents')), fmt(d.get('overtime')), fmt(d.get('advance')), eid)
        )
    return jsonify({'ok': True})


@payroll_bp.route('/employees/<int:eid>', methods=['DELETE'])
@login_required
def delete_employee(eid):
    with get_db() as db:
        db.execute('UPDATE employees SET active=0 WHERE id=?', (eid,))
    return jsonify({'ok': True})
