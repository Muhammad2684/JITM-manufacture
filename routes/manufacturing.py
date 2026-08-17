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


@mfg_bp.route('/recipe-profiles')
@login_required
def list_recipe_profiles():
    q = request.args.get('q', '')
    with get_db() as db:
        base = ('SELECT rp.*, (SELECT COUNT(*) FROM recipe_profile_items rpi WHERE rpi.profile_id=rp.id) as material_count '
                'FROM recipe_profiles rp ')
        if q:
            rows = db.execute(
                base + 'WHERE rp.name LIKE ? OR rp.description LIKE ? ORDER BY rp.name',
                (f'%{q}%', f'%{q}%')
            ).fetchall()
        else:
            rows = db.execute(base + 'ORDER BY rp.name').fetchall()
        return jsonify([dict(r) for r in rows])


@mfg_bp.route('/recipe-profiles', methods=['POST'])
@login_required
@manager_required
def add_recipe_profile():
    d = request.get_json() or {}
    name = (d.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    with get_db() as db:
        cur = db.execute(
            'INSERT INTO recipe_profiles (name, description) VALUES (?,?)',
            (name, (d.get('description') or '').strip())
        )
        return jsonify({'ok': True, 'id': cur.lastrowid})


@mfg_bp.route('/recipe-profiles/<int:pid>', methods=['PUT'])
@login_required
@manager_required
def update_recipe_profile(pid):
    d = request.get_json() or {}
    name = (d.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    with get_db() as db:
        db.execute('UPDATE recipe_profiles SET name=?, description=? WHERE id=?',
                   (name, (d.get('description') or '').strip(), pid))
        return jsonify({'ok': True})


@mfg_bp.route('/recipe-profiles/<int:pid>', methods=['DELETE'])
@login_required
@manager_required
def delete_recipe_profile(pid):
    with get_db() as db:
        db.execute('DELETE FROM recipe_profiles WHERE id=?', (pid,))
        return jsonify({'ok': True})


@mfg_bp.route('/recipe-profiles/<int:pid>/items')
@login_required
def list_recipe_profile_items(pid):
    with get_db() as db:
        rows = db.execute(
            'SELECT rpi.*, r.name as material_name, r.unit, r.cost_per_unit, r.stock as material_stock '
            'FROM recipe_profile_items rpi JOIN raw_materials r ON r.id=rpi.raw_material_id '
            'WHERE rpi.profile_id=? ORDER BY rpi.id', (pid,)
        ).fetchall()
    items = []
    for r in rows:
        item = dict(r)
        item['line_cost'] = round((r['qty_required'] or 0) * (r['cost_per_unit'] or 0), 2)
        items.append(item)
    return jsonify(items)


@mfg_bp.route('/recipe-profiles/<int:pid>/items', methods=['POST'])
@login_required
@manager_required
def add_recipe_profile_item(pid):
    d = request.get_json() or {}
    raw_material_id = d.get('raw_material_id')
    if not raw_material_id:
        return jsonify({'error': 'Raw material is required'}), 400
    try:
        qty_required = float(d.get('qty_required', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid quantity'}), 400
    with get_db() as db:
        rm = db.execute('SELECT id FROM raw_materials WHERE id=?', (raw_material_id,)).fetchone()
        if not rm:
            return jsonify({'error': 'Raw material not found'}), 400
        cur = db.execute(
            'INSERT INTO recipe_profile_items (profile_id, raw_material_id, qty_required) VALUES (?,?,?)',
            (pid, raw_material_id, qty_required)
        )
        return jsonify({'ok': True, 'id': cur.lastrowid})


@mfg_bp.route('/recipe-profiles/<int:pid>/items/<int:item_id>', methods=['PUT'])
@login_required
@manager_required
def update_recipe_profile_item(pid, item_id):
    d = request.get_json() or {}
    try:
        qty_required = float(d.get('qty_required', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid quantity'}), 400
    with get_db() as db:
        db.execute('UPDATE recipe_profile_items SET qty_required=? WHERE id=? AND profile_id=?',
                   (qty_required, item_id, pid))
        return jsonify({'ok': True})


@mfg_bp.route('/recipe-profiles/<int:pid>/items/<int:item_id>', methods=['DELETE'])
@login_required
@manager_required
def delete_recipe_profile_item(pid, item_id):
    with get_db() as db:
        db.execute('DELETE FROM recipe_profile_items WHERE id=? AND profile_id=?', (item_id, pid))
        return jsonify({'ok': True})


@mfg_bp.route('/recipe-profiles/<int:pid>/apply', methods=['POST'])
@login_required
@manager_required
def apply_recipe_profile(pid):
    """Copy profile items into bom for each variant. Existing bom rows for the
    same material are overwritten (idempotent apply)."""
    d = request.get_json() or {}
    variant_ids = d.get('variant_ids') or []
    if not variant_ids:
        return jsonify({'error': 'Select at least one product'}), 400
    with get_db() as db:
        profile = db.execute('SELECT * FROM recipe_profiles WHERE id=?', (pid,)).fetchone()
        if not profile:
            return jsonify({'error': 'Profile not found'}), 404
        items = db.execute(
            'SELECT * FROM recipe_profile_items WHERE profile_id=?', (pid,)
        ).fetchall()
        if not items:
            return jsonify({'error': 'Profile has no materials'}), 400
        applied = 0
        for vid in variant_ids:
            v = db.execute('SELECT id FROM variants WHERE id=?', (vid,)).fetchone()
            if not v:
                return jsonify({'error': 'Variant not found: ' + str(vid)}), 400
            for it in items:
                existing = db.execute(
                    'SELECT id FROM bom WHERE variant_id=? AND raw_material_id=?',
                    (vid, it['raw_material_id'])
                ).fetchone()
                if existing:
                    db.execute('UPDATE bom SET qty_per_unit=? WHERE id=?',
                               (it['qty_required'], existing['id']))
                else:
                    db.execute(
                        'INSERT INTO bom (variant_id, raw_material_id, qty_per_unit) VALUES (?,?,?)',
                        (vid, it['raw_material_id'], it['qty_required'])
                    )
            applied += 1
        return jsonify({'ok': True, 'applied_variants': applied})


def material_cost_per_unit(db, variant_id):
    """Estimated raw material cost to make 1 unit, from the current BOM."""
    row = db.execute(
        'SELECT COALESCE(SUM(b.qty_per_unit * r.cost_per_unit), 0) as cost '
        'FROM bom b JOIN raw_materials r ON r.id=b.raw_material_id WHERE b.variant_id=?',
        (variant_id,)
    ).fetchone()
    return round(row['cost'] or 0, 2)


def next_order_no(db):
    row = db.execute('SELECT COALESCE(MAX(id), 0) + 1 as n FROM production_orders').fetchone()
    return f'PO-{row["n"]:05d}'


@mfg_bp.route('/production-orders')
@login_required
def list_production_orders():
    q = request.args.get('q', '')
    with get_db() as db:
        base = ('SELECT po.*, '
                '(SELECT COALESCE(SUM(i.quantity),0) FROM production_order_items i WHERE i.production_order_id=po.id) as total_qty, '
                '(SELECT COUNT(*) FROM production_order_items i WHERE i.production_order_id=po.id) as line_count '
                'FROM production_orders po ')
        if q:
            rows = db.execute(
                base + 'WHERE po.order_no LIKE ? OR po.status LIKE ? OR po.notes LIKE ? OR EXISTS ('
                'SELECT 1 FROM production_order_items i JOIN products p ON p.id=i.product_id '
                'WHERE i.production_order_id=po.id AND p.name LIKE ?) ORDER BY po.id DESC',
                (f'%{q}%', f'%{q}%', f'%{q}%', f'%{q}%')
            ).fetchall()
        else:
            rows = db.execute(base + 'ORDER BY po.id DESC').fetchall()
        result = []
        for r in rows:
            item = dict(r)
            item['items'] = [dict(x) for x in db.execute(
                'SELECT i.*, p.name as product_name, v.sku as variant_sku, v.size, v.color '
                'FROM production_order_items i JOIN products p ON p.id=i.product_id '
                'LEFT JOIN variants v ON v.id=i.variant_id '
                'WHERE i.production_order_id=? ORDER BY i.id', (r['id'],)
            ).fetchall()]
            result.append(item)
        return jsonify(result)


@mfg_bp.route('/production-orders', methods=['POST'])
@login_required
@manager_required
def create_production_order():
    d = request.get_json() or {}
    items = d.get('items') or []
    if not items:
        return jsonify({'error': 'Add at least one product line'}), 400
    with get_db() as db:
        order_no = next_order_no(db)
        cur = db.execute(
            'INSERT INTO production_orders (order_no, status, notes, created_by) VALUES (?,?,?,?)',
            (order_no, 'pending', (d.get('notes') or '').strip(), session.get('user_id'))
        )
        oid = cur.lastrowid
        total_cost = 0
        for it in items:
            vid = it.get('variant_id')
            try:
                qty = float(it.get('quantity', 0))
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid quantity'}), 400
            if not vid or qty <= 0:
                return jsonify({'error': 'Each line needs a product and quantity'}), 400
            v = db.execute('SELECT id, product_id FROM variants WHERE id=?', (vid,)).fetchone()
            if not v:
                return jsonify({'error': 'Variant not found: ' + str(vid)}), 400
            unit_cost = material_cost_per_unit(db, vid)
            line_total = round(unit_cost * qty, 2)
            total_cost += line_total
            db.execute(
                'INSERT INTO production_order_items (production_order_id, product_id, variant_id, quantity, unit_cost, total) VALUES (?,?,?,?,?,?)',
                (oid, v['product_id'], vid, qty, unit_cost, line_total)
            )
        db.execute('UPDATE production_orders SET total_cost=? WHERE id=?', (round(total_cost, 2), oid))
        return jsonify({'ok': True, 'id': oid, 'order_no': order_no})


@mfg_bp.route('/production-orders/<int:oid>', methods=['PUT'])
@login_required
@manager_required
def update_production_order(oid):
    d = request.get_json() or {}
    status = d.get('status', '')
    if status != 'cancelled':
        return jsonify({'error': 'Invalid status'}), 400
    with get_db() as db:
        po = db.execute('SELECT * FROM production_orders WHERE id=?', (oid,)).fetchone()
        if not po:
            return jsonify({'error': 'Order not found'}), 404
        if po['status'] != 'pending':
            return jsonify({'error': 'Only pending orders can be cancelled'}), 400
        db.execute('UPDATE production_orders SET status=? WHERE id=?', (status, oid))
        return jsonify({'ok': True})


@mfg_bp.route('/production-orders/<int:oid>/complete', methods=['PUT'])
@login_required
@manager_required
def complete_production_order(oid):
    """Complete an order: validate BOM x qty, deduct raw material stock,
    add finished goods to variant stock, record actual costs. All in one transaction."""
    with get_db() as db:
        po = db.execute('SELECT * FROM production_orders WHERE id=?', (oid,)).fetchone()
        if not po:
            return jsonify({'error': 'Order not found'}), 404
        if po['status'] != 'pending':
            return jsonify({'error': f'Order is already {po["status"]}'}), 400
        items = db.execute(
            'SELECT * FROM production_order_items WHERE production_order_id=?', (oid,)
        ).fetchall()
        if not items:
            return jsonify({'error': 'Order has no items'}), 400

        # Validate material availability for every line; report all shortages
        allow_negative = bool((request.get_json(silent=True) or {}).get('allow_negative'))
        needs = {}
        mat_names = {}
        for it in items:
            qty = it['quantity'] or 0
            for b in db.execute(
                'SELECT b.*, r.name as name FROM bom b JOIN raw_materials r ON r.id=b.raw_material_id '
                'WHERE b.variant_id=?', (it['variant_id'],)
            ).fetchall():
                req = round((b['qty_per_unit'] or 0) * qty, 4)
                needs[b['raw_material_id']] = needs.get(b['raw_material_id'], 0) + req
                mat_names[b['raw_material_id']] = b['name']
        shortages = []
        for rmid, req in needs.items():
            rm = db.execute('SELECT stock FROM raw_materials WHERE id=?', (rmid,)).fetchone()
            have = (rm['stock'] or 0) if rm else 0
            if have < req:
                shortages.append({
                    'name': mat_names.get(rmid, 'material'),
                    'need': round(req, 4),
                    'have': round(have, 4),
                    'short': round(req - have, 4)
                })
        if shortages and not allow_negative:
            return jsonify({
                'error': 'Not enough raw materials in stock',
                'shortages': shortages,
                'confirm_required': True
            }), 400

        try:
            db.execute('BEGIN IMMEDIATE')
            actual_total = 0
            for it in items:
                vid = it['variant_id']
                qty = it['quantity'] or 0
                unit_cost = 0
                for b in db.execute('SELECT * FROM bom WHERE variant_id=?', (vid,)).fetchall():
                    rm = db.execute('SELECT * FROM raw_materials WHERE id=?', (b['raw_material_id'],)).fetchone()
                    req = round((b['qty_per_unit'] or 0) * qty, 4)
                    new_stock = round((rm['stock'] or 0) - req, 4)
                    db.execute('UPDATE raw_materials SET stock=? WHERE id=?', (new_stock, rm['id']))
                    db.execute(
                        'INSERT INTO restock_log (variant_id, raw_material_id, old_stock, new_stock, qty_added, cost, note, staff_name) VALUES (?,?,?,?,?,?,?,?)',
                        (None, rm['id'], rm['stock'] or 0, new_stock, -req, rm['cost_per_unit'] or 0,
                         f'Production Order #{po["order_no"]}', session.get('name', ''))
                    )
                    unit_cost += (b['qty_per_unit'] or 0) * (rm['cost_per_unit'] or 0)
                unit_cost = round(unit_cost, 2)
                v = db.execute('SELECT stock, product_id FROM variants WHERE id=?', (vid,)).fetchone()
                new_stock = (v['stock'] or 0) + qty
                db.execute('UPDATE variants SET stock=? WHERE id=?', (new_stock, vid))
                db.execute(
                    'INSERT INTO restock_log (variant_id, old_stock, new_stock, qty_added, cost, note, staff_name) VALUES (?,?,?,?,?,?,?)',
                    (vid, v['stock'], new_stock, qty, unit_cost,
                     f'Production Order #{po["order_no"]}', session.get('name', ''))
                )
                line_total = round(unit_cost * qty, 2)
                actual_total += line_total
                db.execute(
                    'UPDATE production_order_items SET unit_cost=?, total=? WHERE id=?',
                    (unit_cost, line_total, it['id'])
                )
                # Keep product average cost consistent with restock_log
                total_row = db.execute(
                    'SELECT COALESCE(SUM(r.qty_added * r.cost),0) as total_cost, COALESCE(SUM(r.qty_added),0) as total_qty '
                    'FROM restock_log r JOIN variants v2 ON v2.id=r.variant_id '
                    'WHERE v2.product_id=? AND r.cost > 0', (v['product_id'],)
                ).fetchone()
                if total_row and total_row['total_qty'] > 0:
                    avg = round(total_row['total_cost'] / total_row['total_qty'], 2)
                    db.execute('UPDATE products SET cost_price=? WHERE id=?', (avg, v['product_id']))
            db.execute(
                'UPDATE production_orders SET status=?, total_cost=?, completed_at=datetime(\'now\',\'localtime\') WHERE id=?',
                ('completed', round(actual_total, 2), oid)
            )
            db.execute('COMMIT')
        except Exception as e:
            db.execute('ROLLBACK')
            return jsonify({'error': str(e)}), 400
        return jsonify({'ok': True, 'total_cost': round(actual_total, 2)})
