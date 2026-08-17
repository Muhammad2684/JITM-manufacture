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


@mfg_bp.route('/bom')
@login_required
def list_bom():
    variant_id = request.args.get('variant_id', type=int)
    query = ('SELECT b.*, r.name as material_name, r.unit, r.cost_per_unit, r.stock as material_stock '
             'FROM bom b JOIN raw_materials r ON r.id=b.raw_material_id ')
    params = ()
    if variant_id:
        query += 'WHERE b.variant_id=? '
        params = (variant_id,)
    query += 'ORDER BY b.id'
    with get_db() as db:
        rows = db.execute(query, params).fetchall()
    items = []
    for r in rows:
        item = dict(r)
        item['line_cost'] = round((r['qty_per_unit'] or 0) * (r['cost_per_unit'] or 0), 2)
        items.append(item)
    return jsonify(items)


@mfg_bp.route('/bom', methods=['POST'])
@login_required
@manager_required
def add_bom():
    d = request.get_json() or {}
    variant_id = d.get('variant_id')
    raw_material_id = d.get('raw_material_id')
    if not variant_id or not raw_material_id:
        return jsonify({'error': 'Variant and raw material are required'}), 400
    try:
        qty_per_unit = float(d.get('qty_per_unit', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid quantity'}), 400
    with get_db() as db:
        v = db.execute('SELECT id FROM variants WHERE id=?', (variant_id,)).fetchone()
        rm = db.execute('SELECT id FROM raw_materials WHERE id=?', (raw_material_id,)).fetchone()
        if not v:
            return jsonify({'error': 'Variant not found'}), 400
        if not rm:
            return jsonify({'error': 'Raw material not found'}), 400
        try:
            cur = db.execute(
                'INSERT INTO bom (variant_id, raw_material_id, qty_per_unit) VALUES (?,?,?)',
                (variant_id, raw_material_id, qty_per_unit)
            )
            return jsonify({'ok': True, 'id': cur.lastrowid})
        except Exception as e:
            return jsonify({'error': str(e)}), 400


@mfg_bp.route('/bom/<int:bid>', methods=['PUT'])
@login_required
@manager_required
def update_bom(bid):
    d = request.get_json() or {}
    try:
        qty_per_unit = float(d.get('qty_per_unit', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid quantity'}), 400
    with get_db() as db:
        if d.get('raw_material_id'):
            db.execute('UPDATE bom SET raw_material_id=?, qty_per_unit=? WHERE id=?',
                       (d['raw_material_id'], qty_per_unit, bid))
        else:
            db.execute('UPDATE bom SET qty_per_unit=? WHERE id=?', (qty_per_unit, bid))
        return jsonify({'ok': True})


@mfg_bp.route('/bom/<int:bid>', methods=['DELETE'])
@login_required
@manager_required
def delete_bom(bid):
    with get_db() as db:
        db.execute('DELETE FROM bom WHERE id=?', (bid,))
        return jsonify({'ok': True})
