from flask import Blueprint, request, jsonify, session
from database import get_db
from routes.auth import login_required, manager_required

mfg_bp = Blueprint('manufacturing', __name__, url_prefix='/api')


@mfg_bp.route('/raw-materials')
@login_required
def list_raw_materials():
    q = request.args.get('q', '')
    with get_db() as db:
        if q:
            rows = db.execute(
                'SELECT * FROM raw_materials WHERE name LIKE ? OR unit LIKE ? ORDER BY name',
                (f'%{q}%', f'%{q}%')
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM raw_materials ORDER BY name').fetchall()
    items = []
    for r in rows:
        item = dict(r)
        item['stock_value'] = round((item['stock'] or 0) * (item['cost_per_unit'] or 0), 2)
        item['is_low'] = item['stock'] <= item['low_stock']
        items.append(item)
    return jsonify(items)


@mfg_bp.route('/raw-materials', methods=['POST'])
@login_required
@manager_required
def add_raw_material():
    d = request.get_json() or {}
    name = (d.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    try:
        stock = float(d.get('stock', 0))
        cost_per_unit = float(d.get('cost_per_unit', 0))
        low_stock = float(d.get('low_stock', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid numeric value'}), 400
    with get_db() as db:
        try:
            cur = db.execute(
                'INSERT INTO raw_materials (name, unit, stock, cost_per_unit, low_stock) VALUES (?,?,?,?,?)',
                (name, (d.get('unit') or '').strip(), stock, cost_per_unit, low_stock)
            )
            return jsonify({'ok': True, 'id': cur.lastrowid})
        except Exception as e:
            return jsonify({'error': str(e)}), 400


@mfg_bp.route('/raw-materials/<int:rmid>', methods=['PUT'])
@login_required
@manager_required
def update_raw_material(rmid):
    d = request.get_json() or {}
    name = (d.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    try:
        stock = float(d.get('stock', 0))
        cost_per_unit = float(d.get('cost_per_unit', 0))
        low_stock = float(d.get('low_stock', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid numeric value'}), 400
    with get_db() as db:
        db.execute(
            'UPDATE raw_materials SET name=?, unit=?, stock=?, cost_per_unit=?, low_stock=? WHERE id=?',
            (name, (d.get('unit') or '').strip(), stock, cost_per_unit, low_stock, rmid)
        )
        return jsonify({'ok': True})


@mfg_bp.route('/raw-materials/<int:rmid>', methods=['DELETE'])
@login_required
@manager_required
def delete_raw_material(rmid):
    with get_db() as db:
        refs = db.execute(
            'SELECT COUNT(*) as cnt FROM bom WHERE raw_material_id=?', (rmid,)
        ).fetchone()['cnt']
        if refs:
            return jsonify({'error': 'Cannot delete: material is used in a Bill of Materials'}), 400
        db.execute('DELETE FROM raw_materials WHERE id=?', (rmid,))
        return jsonify({'ok': True})
