from flask import Blueprint, request, jsonify
from database import get_db
from routes.auth import login_required, manager_required

sizes_bp = Blueprint('sizes', __name__, url_prefix='/api')


@sizes_bp.route('/sizes')
@login_required
def list_sizes():
    with get_db() as db:
        rows = db.execute('SELECT * FROM sizes ORDER BY name').fetchall()
        return jsonify([dict(r) for r in rows])


@sizes_bp.route('/sizes', methods=['POST'])
@login_required
@manager_required
def add_size():
    d = request.get_json()
    name = d.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    with get_db() as db:
        try:
            cur = db.execute('INSERT INTO sizes (name) VALUES (?)', (name,))
            return jsonify({'ok': True, 'id': cur.lastrowid})
        except Exception as e:
            return jsonify({'error': str(e)}), 400


@sizes_bp.route('/sizes/<int:sid>', methods=['DELETE'])
@login_required
@manager_required
def delete_size(sid):
    with get_db() as db:
        db.execute('DELETE FROM sizes WHERE id=?', (sid,))
        return jsonify({'ok': True})
