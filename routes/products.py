from flask import Blueprint, request, jsonify
from database import get_db
from routes.auth import login_required, manager_required

prod_bp = Blueprint('products', __name__, url_prefix='/api')


@prod_bp.route('/products')
@login_required
def list_products():
    with get_db() as db:
        rows = db.execute('SELECT * FROM products ORDER BY name').fetchall()
        products = []
        for p in rows:
            variants = db.execute('SELECT * FROM variants WHERE product_id=? ORDER BY size, color', (p['id'],)).fetchall()
            p = dict(p)
            p['variants'] = [dict(v) for v in variants]
            p['total_stock'] = sum(v['stock'] for v in variants)
            p['is_low'] = any(v['stock'] <= p['low_stock'] for v in variants) if variants else p['total_stock'] <= p['low_stock']
            products.append(p)
        return jsonify(products)


@prod_bp.route('/products/search')
@login_required
def search_products():
    q = request.args.get('q', '')
    with get_db() as db:
        rows = db.execute(
            'SELECT p.*, v.id as vid, v.size, v.color, v.sku as v_sku, v.barcode as v_barcode, v.price as v_price, v.stock '
            'FROM products p JOIN variants v ON v.product_id=p.id '
            'WHERE p.name LIKE ? OR p.sku LIKE ? OR v.sku LIKE ? OR v.barcode=? OR p.barcode=? '
            'ORDER BY p.name, v.size, v.color',
            (f'%{q}%', f'%{q}%', f'%{q}%', q, q)
        ).fetchall()
    results = []
    seen = set()
    for r in rows:
        key = (r['id'], r['vid'])
        if key in seen:
            continue
        seen.add(key)
        results.append({
            'pid': r['id'],
            'vid': r['vid'],
            'name': r['name'],
            'category': r['category'],
            'size': r['size'],
            'color': r['color'],
            'sku': r['v_sku'] or r['sku'],
            'barcode': r['v_barcode'] or r['barcode'],
            'price': r['v_price'] if r['v_price'] else r['base_price'],
            'base_price': r['base_price'],
            'stock': r['stock'],
            'low_stock': r['low_stock'],
        })
    return jsonify(results)


@prod_bp.route('/products', methods=['POST'])
@login_required
@manager_required
def add_product():
    d = request.get_json()
    with get_db() as db:
        try:
            cur = db.execute(
                'INSERT INTO products (name, category, base_price, cost_price, sku, barcode, has_variants, low_stock) VALUES (?,?,?,?,?,?,?,?)',
                (d['name'], d.get('category', ''), float(d.get('base_price', 0)), float(d.get('cost_price', 0)),
                 d['sku'], d.get('barcode'), int(d.get('has_variants', 0)), int(d.get('low_stock', 5)))
            )
            pid = cur.lastrowid
            if not d.get('has_variants'):
                db.execute('INSERT INTO variants (product_id, sku, stock) VALUES (?,?,?)',
                           (pid, d['sku'] + '-DEF', int(d.get('stock', 0))))
            return jsonify({'ok': True, 'id': pid})
        except Exception as e:
            return jsonify({'error': str(e)}), 400


@prod_bp.route('/products/<int:pid>', methods=['PUT'])
@login_required
@manager_required
def update_product(pid):
    d = request.get_json()
    with get_db() as db:
        db.execute(
            'UPDATE products SET name=?, category=?, base_price=?, cost_price=?, sku=?, barcode=?, low_stock=? WHERE id=?',
            (d['name'], d.get('category', ''), float(d['base_price']), float(d.get('cost_price', 0)),
             d['sku'], d.get('barcode'), int(d.get('low_stock', 5)), pid)
        )
        return jsonify({'ok': True})


@prod_bp.route('/variants', methods=['POST'])
@login_required
@manager_required
def add_variant():
    d = request.get_json()
    with get_db() as db:
        try:
            cur = db.execute(
                'INSERT INTO variants (product_id, size, color, sku, barcode, price, stock) VALUES (?,?,?,?,?,?,?)',
                (d['product_id'], d.get('size', ''), d.get('color', ''),
                 d['sku'], d.get('barcode'), float(d['price']) if d.get('price') else None,
                 int(d.get('stock', 0)))
            )
            pid = d['product_id']
            db.execute('UPDATE products SET has_variants=1 WHERE id=?', (pid,))
            return jsonify({'ok': True, 'id': cur.lastrowid})
        except Exception as e:
            return jsonify({'error': str(e)}), 400


@prod_bp.route('/variants/<int:vid>', methods=['PUT'])
@login_required
@manager_required
def update_variant(vid):
    d = request.get_json()
    with get_db() as db:
        db.execute(
            'UPDATE variants SET size=?, color=?, sku=?, barcode=?, price=?, stock=? WHERE id=?',
            (d.get('size', ''), d.get('color', ''), d['sku'], d.get('barcode'),
             float(d['price']) if d.get('price') else None, int(d.get('stock', 0)), vid)
        )
        return jsonify({'ok': True})


@prod_bp.route('/variants/<int:vid>/stock', methods=['PUT'])
@login_required
@manager_required
def update_stock(vid):
    d = request.get_json()
    with get_db() as db:
        old = db.execute('SELECT stock FROM variants WHERE id=?', (vid,)).fetchone()
        new_stock = int(d['stock'])
        qty = new_stock - old['stock']
        db.execute('UPDATE variants SET stock=? WHERE id=?', (new_stock, vid))
        if qty > 0:
            db.execute(
                'INSERT INTO restock_log (variant_id, old_stock, new_stock, qty_added, cost, note, staff_name) VALUES (?,?,?,?,?,?,?)',
                (vid, old['stock'], new_stock, qty, float(d.get('cost', 0)), d.get('note', ''),
                 session.get('name', ''))
            )
        return jsonify({'ok': True})


@prod_bp.route('/products/low-stock')
@login_required
def low_stock():
    with get_db() as db:
        products = db.execute('SELECT * FROM products ORDER BY name').fetchall()
        result = []
        for p in products:
            variants = db.execute('SELECT * FROM variants WHERE product_id=?', (p['id'],)).fetchall()
            low = [dict(v) for v in variants if v['stock'] <= p['low_stock']]
            if low:
                result.append({'product': dict(p), 'variants': low})
        return jsonify(result)


@prod_bp.route('/restock-log')
@login_required
def restock_log():
    with get_db() as db:
        rows = db.execute(
            'SELECT r.*, v.sku, v.size, v.color, p.name as product_name '
            'FROM restock_log r JOIN variants v ON v.id=r.variant_id '
            'JOIN products p ON p.id=v.product_id ORDER BY r.id DESC LIMIT 100'
        ).fetchall()
        return jsonify([dict(r) for r in rows])


@prod_bp.route('/barcodes')
@login_required
def list_barcodes():
    with get_db() as db:
        variants = db.execute(
            'SELECT v.id, v.sku, v.barcode, v.size, v.color, p.name as product_name, p.base_price, v.price '
            'FROM variants v JOIN products p ON p.id=v.product_id '
            'ORDER BY p.name'
        ).fetchall()
        return jsonify([dict(v) for v in variants])
