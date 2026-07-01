from flask import Blueprint, request, jsonify
from database import get_db
from routes.auth import login_required

cust_bp = Blueprint('customers', __name__, url_prefix='/api')


@cust_bp.route('/customers')
@login_required
def list_customers():
    """List all customers with optional search filter and pagination."""
    search_query = request.args.get('q', '')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    offset = (page - 1) * per_page
    
    with get_db() as db:
        if search_query:
            count_row = db.execute(
                'SELECT COUNT(*) as cnt FROM customers WHERE name LIKE ? OR phone LIKE ?',
                (f'%{search_query}%', f'%{search_query}%')
            ).fetchone()
            total = count_row['cnt']
            rows = db.execute(
                'SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? ORDER BY name LIMIT ? OFFSET ?',
                (f'%{search_query}%', f'%{search_query}%', per_page, offset)
            ).fetchall()
        else:
            count_row = db.execute('SELECT COUNT(*) as cnt FROM customers').fetchone()
            total = count_row['cnt']
            rows = db.execute('SELECT * FROM customers ORDER BY name LIMIT ? OFFSET ?', (per_page, offset)).fetchall()
        
        return jsonify({
            'items': [dict(row) for row in rows],
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })


@cust_bp.route('/customers', methods=['POST'])
@login_required
def add_customer():
    """Create a new customer."""
    request_data = request.get_json()
    with get_db() as db:
        try:
            cursor = db.execute(
                'INSERT INTO customers (name, phone, email, address, baby_name, baby_birth, notes, credit) VALUES (?,?,?,?,?,?,?,?)',
                (request_data['name'], request_data.get('phone', ''), request_data.get('email', ''), request_data.get('address', ''),
                 request_data.get('baby_name', ''), request_data.get('baby_birth', ''), request_data.get('notes', ''),
                 float(request_data.get('credit', 0)))
            )
            return jsonify({'ok': True, 'id': cursor.lastrowid})
        except Exception as error:
            return jsonify({'error': str(error)}), 400


@cust_bp.route('/customers/<int:customer_id>', methods=['PUT'])
@login_required
def update_customer(customer_id):
    """Update name, phone, email, address, baby info, notes, and credit for a customer."""
    request_data = request.get_json()
    with get_db() as db:
        db.execute(
            'UPDATE customers SET name=?, phone=?, email=?, address=?, baby_name=?, baby_birth=?, notes=?, credit=? WHERE id=?',
            (request_data['name'], request_data.get('phone', ''), request_data.get('email', ''), request_data.get('address', ''),
             request_data.get('baby_name', ''), request_data.get('baby_birth', ''), request_data.get('notes', ''),
             float(request_data.get('credit', 0)), customer_id)
        )
        return jsonify({'ok': True})


@cust_bp.route('/customers/<int:customer_id>', methods=['DELETE'])
@login_required
def delete_customer(customer_id):
    """Delete a customer and nullify their references in sales."""
    with get_db() as db:
        db.execute('UPDATE sales SET customer_id=NULL, customer_name="Deleted" WHERE customer_id=?', (customer_id,))
        db.execute('DELETE FROM customers WHERE id=?', (customer_id,))
        return jsonify({'ok': True})


@cust_bp.route('/customers/<int:customer_id>/history')
@login_required
def customer_history(customer_id):
    """Get recent sales history for a customer."""
    with get_db() as db:
        sales = db.execute(
            'SELECT * FROM sales WHERE customer_id=? ORDER BY id DESC LIMIT 50',
            (customer_id,)
        ).fetchall()
        return jsonify({
            'sales': [dict(row) for row in sales],
        })


@cust_bp.route('/customers/<int:customer_id>/invoices')
@login_required
def customer_invoices(customer_id):
    """Get outstanding (unpaid/partial) invoices for a customer."""
    with get_db() as db:
        rows = db.execute(
            "SELECT id, receipt, subtotal, total, paid, (total-paid) as outstanding, created_at "
            "FROM sales WHERE customer_id=? AND status IN ('Unpaid','Partial') AND total>paid "
            "ORDER BY created_at", (customer_id,)
        ).fetchall()
        return jsonify([dict(row) for row in rows])
