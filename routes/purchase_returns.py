from flask import Blueprint, request, jsonify, session
from database import get_db
from routes.auth import login_required, manager_required
from routes.purchase_invoices import find_default_variant, update_weighted_avg_cost, apply_stock_change, auto_link_product

pr_bp = Blueprint('purchase_returns', __name__, url_prefix='/api')


@pr_bp.route('/purchase-returns')
@login_required
def list_purchase_returns():
    """List all purchase returns with pagination."""
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    offset = (page - 1) * per_page

    with get_db() as db:
        count_row = db.execute('SELECT COUNT(*) as cnt FROM purchase_returns').fetchone()
        total = count_row['cnt']

        rows = db.execute(
            'SELECT pr.*, s.name as supplier_name FROM purchase_returns pr '
            'LEFT JOIN suppliers s ON s.id=pr.supplier_id ORDER BY pr.id DESC LIMIT ? OFFSET ?',
            (per_page, offset)
        ).fetchall()

        return jsonify({
            'items': [dict(row) for row in rows],
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })


@pr_bp.route('/purchase-returns/<int:return_id>')
@login_required
def get_purchase_return(return_id):
    """Get a specific purchase return with its line items."""
    with get_db() as db:
        purchase_return = db.execute(
            'SELECT pr.*, s.name as supplier_name FROM purchase_returns pr '
            'LEFT JOIN suppliers s ON s.id=pr.supplier_id WHERE pr.id=?', (return_id,)
        ).fetchone()
        if not purchase_return:
            return jsonify({'error': 'Not found'}), 404
        items = db.execute(
            'SELECT * FROM purchase_return_items WHERE return_id=? ORDER BY line_number', (return_id,)
        ).fetchall()
        result = dict(purchase_return)
        result['items'] = [dict(item) for item in items]
        return jsonify(result)


@pr_bp.route('/purchase-returns', methods=['POST'])
@login_required
@manager_required
def create_purchase_return():
    """Create a purchase return: reduce stock, reduce supplier balance."""
    request_data = request.get_json()
    with get_db() as db:
        try:
            cursor = db.execute(
                'INSERT INTO purchase_returns (return_no, return_date, supplier_id, description, total_amount) VALUES (?,?,?,?,?)',
                (request_data['return_no'], request_data.get('return_date', ''),
                 request_data.get('supplier_id'), request_data.get('description', ''),
                 float(request_data.get('total_amount', 0)))
            )
            return_id = cursor.lastrowid
            staff_member = session.get('name', '')
            reference = 'PR #' + request_data['return_no']

            for item in request_data.get('items', []):
                product_id = auto_link_product(db, item)
                db.execute(
                    'INSERT INTO purchase_return_items (return_id, line_number, item, product_id, qty, unit_price, total) VALUES (?,?,?,?,?,?,?)',
                    (return_id, int(item.get('line_number', 0)), item.get('item', ''),
                     product_id, float(item.get('qty', 1)),
                     float(item.get('unit_price', 0)), float(item.get('total', 0)))
                )
                if product_id:
                    quantity = float(item.get('qty', 1))
                    cost = float(item.get('unit_price', 0))
                    apply_stock_change(db, product_id, -int(quantity), cost, reference, staff_member)

            if request_data.get('supplier_id') and float(request_data.get('total_amount', 0)):
                db.execute('UPDATE suppliers SET balance = COALESCE(balance,0) - ? WHERE id=?',
                           (float(request_data['total_amount']), request_data['supplier_id']))

            return jsonify({'ok': True, 'id': return_id})
        except Exception as error:
            return jsonify({'error': str(error)}), 400


@pr_bp.route('/purchase-returns/<int:return_id>', methods=['DELETE'])
@login_required
@manager_required
def delete_purchase_return(return_id):
    """Delete a purchase return: reverse stock and supplier balance changes."""
    with get_db() as db:
        purchase_return = db.execute(
            'SELECT return_no, total_amount, supplier_id FROM purchase_returns WHERE id=?', (return_id,)
        ).fetchone()
        if purchase_return:
            items = db.execute(
                'SELECT product_id, qty, unit_price FROM purchase_return_items WHERE return_id=?', (return_id,)
            ).fetchall()
            staff_member = session.get('name', '')
            reference = 'DEL PR #' + purchase_return['return_no']

            for item in items:
                product_id = item['product_id']
                if product_id:
                    apply_stock_change(db, product_id, int(item['qty']), float(item['unit_price'] or 0), reference, staff_member)

        db.execute('DELETE FROM purchase_return_items WHERE return_id=?', (return_id,))
        db.execute('DELETE FROM purchase_returns WHERE id=?', (return_id,))

        if purchase_return and purchase_return['supplier_id'] and float(purchase_return['total_amount'] or 0):
            db.execute('UPDATE suppliers SET balance = COALESCE(balance,0) + ? WHERE id=?',
                       (float(purchase_return['total_amount']), purchase_return['supplier_id']))

        return jsonify({'ok': True})
