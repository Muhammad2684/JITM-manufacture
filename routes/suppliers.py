from flask import Blueprint, request, jsonify, session
from database import get_db
from routes.auth import login_required, manager_required

sup_bp = Blueprint('suppliers', __name__, url_prefix='/api')


@sup_bp.route('/suppliers')
@login_required
def list_suppliers():
    """List all suppliers ordered by name with pagination."""
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    offset = (page - 1) * per_page
    
    with get_db() as db:
        count_row = db.execute('SELECT COUNT(*) as cnt FROM suppliers').fetchone()
        total = count_row['cnt']
        
        rows = db.execute('SELECT * FROM suppliers ORDER BY name LIMIT ? OFFSET ?', (per_page, offset)).fetchall()
        return jsonify({
            'items': [dict(row) for row in rows],
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })


@sup_bp.route('/suppliers', methods=['POST'])
@login_required
@manager_required
def add_supplier():
    """Create a new supplier."""
    request_data = request.get_json()
    with get_db() as db:
        try:
            cursor = db.execute(
                'INSERT INTO suppliers (name, phone, email, address, contact_person, notes, company_phone) VALUES (?,?,?,?,?,?,?)',
                (request_data['name'], request_data.get('phone', ''), request_data.get('email', ''), request_data.get('address', ''),
                 request_data.get('contact_person', ''), request_data.get('notes', ''), request_data.get('company_phone', ''))
            )
            return jsonify({'ok': True, 'id': cursor.lastrowid})
        except Exception as error:
            return jsonify({'error': str(error)}), 400


@sup_bp.route('/suppliers/<int:supplier_id>', methods=['PUT'])
@login_required
@manager_required
def update_supplier(supplier_id):
    """Update a supplier's details."""
    request_data = request.get_json()
    with get_db() as db:
        db.execute(
            'UPDATE suppliers SET name=?, phone=?, email=?, address=?, contact_person=?, notes=?, company_phone=? WHERE id=?',
            (request_data['name'], request_data.get('phone', ''), request_data.get('email', ''), request_data.get('address', ''),
             request_data.get('contact_person', ''), request_data.get('notes', ''), request_data.get('company_phone', ''), supplier_id)
        )
        return jsonify({'ok': True})


@sup_bp.route('/suppliers/<int:supplier_id>', methods=['DELETE'])
@login_required
@manager_required
def delete_supplier(supplier_id):
    """Delete a supplier."""
    with get_db() as db:
        db.execute('DELETE FROM suppliers WHERE id=?', (supplier_id,))
        return jsonify({'ok': True})


@sup_bp.route('/suppliers/<int:supplier_id>/invoices')
@login_required
def supplier_invoices(supplier_id):
    """Get outstanding purchase invoices for a supplier."""
    with get_db() as db:
        rows = db.execute(
            'SELECT id, invoice_no, issue_date, invoice_amount, balance_due, status '
            "FROM purchase_invoices WHERE supplier_id=? AND balance_due>0 ORDER BY created_at", (supplier_id,)
        ).fetchall()
        return jsonify([dict(row) for row in rows])


@sup_bp.route('/suppliers/ledger')
@login_required
def supplier_ledger():
    """List all suppliers with their balances for the ledger view."""
    with get_db() as db:
        rows = db.execute('SELECT id, name, phone, balance FROM suppliers ORDER BY name').fetchall()
        return jsonify([dict(row) for row in rows])
