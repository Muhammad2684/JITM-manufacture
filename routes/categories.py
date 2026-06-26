from flask import Blueprint, request, jsonify
from database import get_db
from routes.auth import login_required, manager_required

cat_bp = Blueprint('categories', __name__, url_prefix='/api')


@cat_bp.route('/categories')
@login_required
def list_categories():
    with get_db() as db:
        rows = db.execute('SELECT * FROM categories ORDER BY name').fetchall()
        return jsonify([dict(r) for r in rows])


@cat_bp.route('/categories', methods=['POST'])
@login_required
@manager_required
def add_category():
    d = request.get_json()
    name = d.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    with get_db() as db:
        try:
            cur = db.execute('INSERT INTO categories (name) VALUES (?)', (name,))
            return jsonify({'ok': True, 'id': cur.lastrowid})
        except Exception as e:
            return jsonify({'error': str(e)}), 400


@cat_bp.route('/categories/<int:cid>', methods=['DELETE'])
@login_required
@manager_required
def delete_category(cid):
    with get_db() as db:
        db.execute('DELETE FROM categories WHERE id=?', (cid,))
        return jsonify({'ok': True})
