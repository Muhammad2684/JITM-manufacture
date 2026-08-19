from flask import Blueprint, request, jsonify, session
from database import get_db
from routes.auth import login_required, manager_required

pi_bp = Blueprint('purchase_invoices', __name__, url_prefix='/api')


def find_default_variant(db, product_id):
    """Find the default (first) variant for a product."""
    return db.execute(
        'SELECT id, stock FROM variants WHERE product_id=? ORDER BY id LIMIT 1',
        (product_id,)
    ).fetchone()


def update_weighted_avg_cost(db, product_id):
    """Recalculate and update the weighted average cost for a product based on restock history."""
    total_row = db.execute(
        'SELECT COALESCE(SUM(r.qty_added * r.cost),0) as total_cost, COALESCE(SUM(r.qty_added),0) as total_qty '
        'FROM restock_log r JOIN variants v ON v.id=r.variant_id '
        'WHERE v.product_id=? AND r.cost > 0',
        (product_id,)
    ).fetchone()
    if total_row and total_row['total_qty'] > 0:
        average_cost = round(total_row['total_cost'] / total_row['total_qty'], 2)
        db.execute('UPDATE products SET cost_price=? WHERE id=?', (average_cost, product_id))


def apply_stock_change(db, product_id, quantity, cost, reference_note, staff_name):
    """Apply a stock change for a product: update variant stock, log the change, and recalculate avg cost."""
    variant = find_default_variant(db, product_id)
    if not variant:
        return
    old_stock = variant['stock']
    new_stock = old_stock + quantity
    db.execute('UPDATE variants SET stock=? WHERE id=?', (new_stock, variant['id']))
    db.execute(
        'INSERT INTO restock_log (variant_id, old_stock, new_stock, qty_added, cost, note, staff_name) VALUES (?,?,?,?,?,?,?)',
        (variant['id'], old_stock, new_stock, quantity, cost, reference_note, staff_name)
    )
    update_weighted_avg_cost(db, product_id)


def auto_link_product(db, item):
    """Resolve product_id by exact name match (case-insensitive) when not explicitly set."""
    if item.get('product_id'):
        return item['product_id']
    product_name = (item.get('item') or '').strip()
    if not product_name:
        return None
    product_row = db.execute(
        'SELECT id FROM products WHERE LOWER(TRIM(name)) = LOWER(?)',
        (product_name,)
    ).fetchone()
    return product_row['id'] if product_row else None


def apply_raw_material_stock_change(db, raw_material_id, quantity, cost, reference_note, staff_name):
    """Apply a stock change for a raw material: update stock and weighted avg cost, and log."""
    material = db.execute(
        'SELECT stock, cost_per_unit FROM raw_materials WHERE id=?', (raw_material_id,)
    ).fetchone()
    if not material:
        return
    old_stock = float(material['stock'] or 0)
    old_cost = float(material['cost_per_unit'] or 0)
    new_stock = old_stock + quantity
    if new_stock > 0:
        if old_stock < 0:
            # Negative stock (owed/shortfall units): average over the absolute
            # quantity so the recorded cost of the shortfall is absorbed into
            # the new per-unit cost instead of dragging it down.
            new_cost = round((abs(old_stock) * old_cost + float(quantity) * float(cost)) / (abs(old_stock) + float(quantity)), 2)
        else:
            new_cost = round((old_stock * old_cost + float(quantity) * float(cost)) / new_stock, 2)
    else:
        new_cost = 0
    db.execute('UPDATE raw_materials SET stock=?, cost_per_unit=? WHERE id=?', (new_stock, new_cost, raw_material_id))
    db.execute(
        'INSERT INTO restock_log (variant_id, raw_material_id, old_stock, new_stock, qty_added, cost, note, staff_name) VALUES (?,?,?,?,?,?,?,?)',
        (None, raw_material_id, old_stock, new_stock, float(quantity), float(cost), reference_note, staff_name)
    )


def auto_link_raw_material(db, item):
    """Resolve raw_material_id by exact name match (case-insensitive) when not explicitly set."""
    if item.get('raw_material_id'):
        return item['raw_material_id']
    material_name = (item.get('item') or '').strip()
    if not material_name:
        return None
    material_row = db.execute(
        'SELECT id FROM raw_materials WHERE LOWER(TRIM(name)) = LOWER(?)',
        (material_name,)
    ).fetchone()
    return material_row['id'] if material_row else None


@pi_bp.route('/purchase-invoices')
@login_required
def list_purchase_invoices():
    """List all purchase invoices with supplier names, date range, and pagination."""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    offset = (page - 1) * per_page
    
    with get_db() as db:
        where_clauses = []
        params = []
        
        if date_from and date_to:
            where_clauses.append('date(pi.issue_date) BETWEEN ? AND ?')
            params.extend([date_from, date_to])
        elif date_from:
            where_clauses.append('date(pi.issue_date) >= ?')
            params.append(date_from)
        elif date_to:
            where_clauses.append('date(pi.issue_date) <= ?')
            params.append(date_to)
        
        where_sql = ' AND '.join(where_clauses)
        if where_sql:
            where_sql = 'WHERE ' + where_sql
        
        count_row = db.execute(
            'SELECT COUNT(*) as cnt FROM purchase_invoices pi ' + where_sql, params
        ).fetchone()
        total = count_row['cnt']
        
        rows = db.execute(
            'SELECT pi.*, s.name as supplier_name FROM purchase_invoices pi '
            'LEFT JOIN suppliers s ON s.id=pi.supplier_id ' + where_sql + ' ORDER BY pi.id DESC LIMIT ? OFFSET ?',
            params + [per_page, offset]
        ).fetchall()
        
        return jsonify({
            'items': [dict(row) for row in rows],
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })


@pi_bp.route('/purchase-invoices/<int:invoice_id>')
@login_required
def get_purchase_invoice(invoice_id):
    """Get a specific purchase invoice with its line items."""
    with get_db() as db:
        invoice = db.execute(
            'SELECT pi.*, s.name as supplier_name FROM purchase_invoices pi '
            'LEFT JOIN suppliers s ON s.id=pi.supplier_id WHERE pi.id=?', (invoice_id,)
        ).fetchone()
        if not invoice:
            return jsonify({'error': 'Not found'}), 404
        invoice_items = db.execute(
            'SELECT * FROM purchase_invoice_items WHERE invoice_id=? ORDER BY line_number', (invoice_id,)
        ).fetchall()
        result = dict(invoice)
        result['items'] = [dict(item) for item in invoice_items]
        return jsonify(result)


@pi_bp.route('/purchase-invoices', methods=['POST'])
@login_required
@manager_required
def create_purchase_invoice():
    """Create a new purchase invoice, add line items, update stock, and adjust supplier balance."""
    request_data = request.get_json()
    with get_db() as db:
        try:
            cursor = db.execute(
                'INSERT INTO purchase_invoices (invoice_no, issue_date, due_date, supplier_id, description, invoice_amount, balance_due, status) VALUES (?,?,?,?,?,?,?,?)',
                (request_data['invoice_no'], request_data.get('issue_date', ''), request_data.get('due_date', ''),
                 request_data.get('supplier_id'), request_data.get('description', ''),
                 float(request_data.get('invoice_amount', 0)), float(request_data.get('balance_due', 0)),
                 request_data.get('status', 'Unpaid'))
            )
            invoice_id = cursor.lastrowid
            staff_member = session.get('name', '')
            reference = 'PI #' + request_data['invoice_no']
            
            for item in request_data.get('items', []):
                item_type = item.get('item_type', 'product') or 'product'
                product_id = None
                raw_material_id = None
                if item_type == 'raw_material':
                    raw_material_id = auto_link_raw_material(db, item)
                else:
                    product_id = auto_link_product(db, item)
                db.execute(
                    'INSERT INTO purchase_invoice_items (invoice_id, line_number, item, product_id, raw_material_id, item_type, qty, unit_price, total) VALUES (?,?,?,?,?,?,?,?,?)',
                    (invoice_id, int(item.get('line_number', 0)), item.get('item', ''),
                     product_id, raw_material_id, item_type, float(item.get('qty', 1)),
                     float(item.get('unit_price', 0)), float(item.get('total', 0)))
                )
                if item_type == 'raw_material':
                    if raw_material_id:
                        quantity = float(item.get('qty', 1))
                        cost = float(item.get('unit_price', 0))
                        apply_raw_material_stock_change(db, raw_material_id, quantity, cost, reference, staff_member)
                elif product_id:
                    quantity = float(item.get('qty', 1))
                    cost = float(item.get('unit_price', 0))
                    apply_stock_change(db, product_id, int(quantity), cost, reference, staff_member)
            
            if request_data.get('supplier_id') and float(request_data.get('balance_due', 0)):
                db.execute('UPDATE suppliers SET balance = COALESCE(balance,0) + ? WHERE id=?',
                           (float(request_data['balance_due']), request_data['supplier_id']))
            
            return jsonify({'ok': True, 'id': invoice_id})
        except Exception as error:
            return jsonify({'error': str(error)}), 400


@pi_bp.route('/purchase-invoices/<int:invoice_id>', methods=['PUT'])
@login_required
@manager_required
def update_purchase_invoice(invoice_id):
    """Update a purchase invoice: apply stock deltas per item, adjust supplier balance."""
    request_data = request.get_json()
    with get_db() as db:
        try:
            old_invoice = db.execute(
                'SELECT * FROM purchase_invoices WHERE id=?', (invoice_id,)
            ).fetchone()
            if not old_invoice:
                return jsonify({'error': 'Invoice not found'}), 404
            old_invoice = dict(old_invoice)
            
            old_items = db.execute(
                'SELECT * FROM purchase_invoice_items WHERE invoice_id=?', (invoice_id,)
            ).fetchall()
            
            staff_member = session.get('name', '')
            reference = 'PI #' + (request_data.get('invoice_no') or old_invoice['invoice_no'])
            
            old_by_key = {}
            for item in old_items:
                item = dict(item)
                key = None
                if (item.get('item_type') or 'product') == 'raw_material':
                    if item.get('raw_material_id'):
                        key = 'r:' + str(item['raw_material_id'])
                elif item['product_id']:
                    key = 'p:' + str(item['product_id'])
                if key:
                    old_by_key[key] = dict(item)
            
            matched_keys = set()
            
            for item in request_data.get('items', []):
                item_type = item.get('item_type', 'product') or 'product'
                if item_type == 'raw_material':
                    raw_material_id = auto_link_raw_material(db, item)
                    if not raw_material_id:
                        continue
                    key = 'r:' + str(raw_material_id)
                    new_qty = float(item.get('qty', 1))
                    new_cost = float(item.get('unit_price', 0))
                    
                    if key in old_by_key:
                        matched_keys.add(key)
                        old_item = old_by_key[key]
                        old_qty = float(old_item['qty'])
                        old_cost = float(old_item['unit_price'] or 0)
                        
                        if old_qty != new_qty or old_cost != new_cost:
                            row = db.execute(
                                'SELECT id FROM restock_log WHERE raw_material_id=? AND note=? AND qty_added>0 ORDER BY id DESC LIMIT 1',
                                (raw_material_id, reference)
                            ).fetchone()
                            if row:
                                db.execute('UPDATE restock_log SET qty_added=?, cost=? WHERE id=?',
                                           (new_qty, new_cost, row['id']))
                            material = db.execute(
                                'SELECT stock, cost_per_unit FROM raw_materials WHERE id=?', (raw_material_id,)
                            ).fetchone()
                            if material:
                                old_stock = float(material['stock'] or 0)
                                cur_cost = float(material['cost_per_unit'] or 0)
                                delta = new_qty - old_qty
                                new_stock = old_stock + delta
                                if new_stock > 0:
                                    new_cost = round((old_stock * cur_cost - old_qty * old_cost + new_qty * new_cost) / new_stock, 2)
                                else:
                                    new_cost = 0
                                if delta != 0:
                                    db.execute('UPDATE raw_materials SET stock=? WHERE id=?', (new_stock, raw_material_id))
                                db.execute('UPDATE raw_materials SET cost_per_unit=? WHERE id=?', (new_cost, raw_material_id))
                    else:
                        apply_raw_material_stock_change(db, raw_material_id, new_qty, new_cost, reference, staff_member)
                else:
                    product_id = auto_link_product(db, item)
                    if not product_id:
                        continue
                    key = 'p:' + str(product_id)
                    new_qty = int(float(item.get('qty', 1)))
                    new_cost = float(item.get('unit_price', 0))
                    
                    if key in old_by_key:
                        matched_keys.add(key)
                        old_item = old_by_key[key]
                        old_qty = int(old_item['qty'])
                        old_cost = float(old_item['unit_price'] or 0)
                        
                        if old_qty != new_qty or old_cost != new_cost:
                            variant = find_default_variant(db, product_id)
                            if variant:
                                row = db.execute(
                                    'SELECT id FROM restock_log WHERE variant_id=? AND note=? AND qty_added>0 ORDER BY id DESC LIMIT 1',
                                    (variant['id'], reference)
                                ).fetchone()
                                if row:
                                    db.execute('UPDATE restock_log SET qty_added=?, cost=? WHERE id=?',
                                               (new_qty, new_cost, row['id']))
                                delta = new_qty - old_qty
                                if delta != 0:
                                    db.execute('UPDATE variants SET stock=stock+? WHERE id=?', (delta, variant['id']))
                                update_weighted_avg_cost(db, product_id)
                    else:
                        apply_stock_change(db, product_id, new_qty, new_cost, reference, staff_member)
            
            for old_item in old_items:
                old_item = dict(old_item)
                old_key = None
                if (old_item.get('item_type') or 'product') == 'raw_material':
                    if old_item.get('raw_material_id'):
                        old_key = 'r:' + str(old_item['raw_material_id'])
                        if old_key not in matched_keys:
                            apply_raw_material_stock_change(db, old_item['raw_material_id'], -float(old_item['qty']), float(old_item['unit_price'] or 0), reference + ' (removed)', staff_member)
                elif old_item['product_id']:
                    old_key = 'p:' + str(old_item['product_id'])
                    if old_key not in matched_keys:
                        apply_stock_change(db, old_item['product_id'], -int(old_item['qty']), float(old_item['unit_price'] or 0), reference + ' (removed)', staff_member)
            
            db.execute(
                'UPDATE purchase_invoices SET invoice_no=?, issue_date=?, due_date=?, supplier_id=?, description=?, invoice_amount=?, balance_due=?, status=? WHERE id=?',
                (request_data['invoice_no'], request_data.get('issue_date', ''), request_data.get('due_date', ''),
                 request_data.get('supplier_id'), request_data.get('description', ''),
                 float(request_data.get('invoice_amount', 0)), float(request_data.get('balance_due', 0)),
                 request_data.get('status', 'Unpaid'), invoice_id)
            )
            
            db.execute('DELETE FROM purchase_invoice_items WHERE invoice_id=?', (invoice_id,))
            
            for item in request_data.get('items', []):
                item_type = item.get('item_type', 'product') or 'product'
                product_id = None
                raw_material_id = None
                if item_type == 'raw_material':
                    raw_material_id = auto_link_raw_material(db, item)
                else:
                    product_id = auto_link_product(db, item)
                db.execute(
                    'INSERT INTO purchase_invoice_items (invoice_id, line_number, item, product_id, raw_material_id, item_type, qty, unit_price, total) VALUES (?,?,?,?,?,?,?,?,?)',
                    (invoice_id, int(item.get('line_number', 0)), item.get('item', ''),
                     product_id, raw_material_id, item_type, float(item.get('qty', 1)),
                     float(item.get('unit_price', 0)), float(item.get('total', 0)))
                )
            
            if old_invoice['supplier_id']:
                old_balance = float(old_invoice['balance_due'] or 0)
                new_balance = float(request_data.get('balance_due', 0))
                new_supplier_id = request_data.get('supplier_id')
                
                if old_invoice['supplier_id'] == new_supplier_id:
                    if old_balance != new_balance:
                        db.execute('UPDATE suppliers SET balance = COALESCE(balance,0) + ? WHERE id=?',
                                   (round(new_balance - old_balance, 2), old_invoice['supplier_id']))
                else:
                    if old_balance:
                        db.execute('UPDATE suppliers SET balance = COALESCE(balance,0) - ? WHERE id=?',
                                   (old_balance, old_invoice['supplier_id']))
                    if new_supplier_id and new_balance:
                        db.execute('UPDATE suppliers SET balance = COALESCE(balance,0) + ? WHERE id=?',
                                   (new_balance, new_supplier_id))
            
            return jsonify({'ok': True})
        except Exception as error:
            return jsonify({'error': str(error)}), 400


@pi_bp.route('/purchase-invoices/<int:invoice_id>', methods=['DELETE'])
@login_required
@manager_required
def delete_purchase_invoice(invoice_id):
    """Delete a purchase invoice: reverse stock changes, remove items, and adjust supplier balance."""
    with get_db() as db:
        invoice = db.execute('SELECT invoice_no, balance_due, supplier_id FROM purchase_invoices WHERE id=?', (invoice_id,)).fetchone()
        if invoice:
            invoice_items = db.execute(
                'SELECT product_id, raw_material_id, item_type, qty, unit_price FROM purchase_invoice_items WHERE invoice_id=?', (invoice_id,)
            ).fetchall()
            staff_member = session.get('name', '')
            reference = 'DEL #' + invoice['invoice_no']
            
            for item in invoice_items:
                if (item['item_type'] or 'product') == 'raw_material':
                    raw_material_id = item['raw_material_id']
                    if raw_material_id:
                        apply_raw_material_stock_change(db, raw_material_id, -float(item['qty']), float(item['unit_price'] or 0), reference, staff_member)
                elif item['product_id']:
                    apply_stock_change(db, item['product_id'], -int(item['qty']), float(item['unit_price'] or 0), reference, staff_member)
        
        db.execute('DELETE FROM purchase_invoice_items WHERE invoice_id=?', (invoice_id,))
        db.execute('DELETE FROM purchase_invoices WHERE id=?', (invoice_id,))
        
        if invoice and invoice['supplier_id'] and float(invoice['balance_due'] or 0):
            db.execute('UPDATE suppliers SET balance = COALESCE(balance,0) - ? WHERE id=?',
                       (float(invoice['balance_due']), invoice['supplier_id']))
        
        return jsonify({'ok': True})
