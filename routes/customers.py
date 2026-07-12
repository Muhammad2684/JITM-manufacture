import csv, io

import openpyxl
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


@cust_bp.route('/customers/import-template')
@login_required
def customer_import_template():
    """Return a sample CSV template for bulk customer import."""
    header = 'name,phone,email,address,baby_name,baby_birth,notes,credit,credit_limit'
    sample = 'John Doe,03001234567,john@example.com,123 Main St,Jane,2026-01,Regular customer,0,50000'
    output = io.StringIO()
    output.write(header + '\n' + sample + '\n')
    return output.getvalue(), 200, {'Content-Type': 'text/csv', 'Content-Disposition': 'attachment; filename=customer_import_template.csv'}


@cust_bp.route('/customers/import', methods=['POST'])
@login_required
def customer_import():
    """Bulk import customers from CSV or Excel file. Skips duplicate names, reports errors."""
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'No file uploaded'}), 400

    filename = file.filename.lower() if file.filename else ''
    rows = []

    if filename.endswith('.xlsx'):
        wb = openpyxl.load_workbook(file, read_only=True)
        ws = wb.active
        data_rows = list(ws.iter_rows(values_only=True))
        if not data_rows:
            return jsonify({'error': 'Empty file'}), 400
        headers = [str(h).strip().lower() if h else '' for h in data_rows[0]]
        for row in data_rows[1:]:
            d = {}
            for i, h in enumerate(headers):
                val = row[i] if i < len(row) else None
                d[h] = str(val).strip() if val is not None else ''
            rows.append(d)
    elif filename.endswith('.csv'):
        content = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames:
            return jsonify({'error': 'Empty or invalid CSV'}), 400
        reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]
        for row in reader:
            d = {}
            for k, v in row.items():
                d[k.strip().lower()] = v.strip() if v else ''
            rows.append(d)
    else:
        return jsonify({'error': 'Unsupported file format. Use .csv or .xlsx'}), 400

    if not rows:
        return jsonify({'error': 'No data rows found'}), 400

    header_cols = set(rows[0].keys())
    if 'name' not in header_cols:
        return jsonify({'error': 'Missing required column: name'}), 400

    created = 0
    skipped = 0
    errors = []

    with get_db() as db:
        existing_names = set(
            row['name'] for row in db.execute('SELECT name FROM customers').fetchall()
        )

        db.execute('BEGIN IMMEDIATE')
        for idx, row in enumerate(rows, start=2):
            name = (row.get('name') or '').strip()
            if not name:
                errors.append(f'Row {idx}: name is required')
                continue
            if name.lower() in {n.lower() for n in existing_names}:
                skipped += 1
                continue

            try:
                credit = float(row.get('credit', 0) or 0)
            except (ValueError, TypeError):
                errors.append(f'Row {idx}: invalid credit "{row.get("credit")}"')
                continue
            try:
                credit_limit = float(row.get('credit_limit', 0) or 0) or None
            except (ValueError, TypeError):
                errors.append(f'Row {idx}: invalid credit_limit "{row.get("credit_limit")}"')
                continue

            try:
                db.execute(
                    'INSERT INTO customers (name, phone, email, address, baby_name, baby_birth, notes, credit, credit_limit) VALUES (?,?,?,?,?,?,?,?,?)',
                    (name, row.get('phone', ''), row.get('email', ''), row.get('address', ''),
                     row.get('baby_name', ''), row.get('baby_birth', ''), row.get('notes', ''),
                     credit, credit_limit)
                )
                existing_names.add(name)
                created += 1
            except Exception as e:
                errors.append(f'Row {idx}: {str(e)}')

    return jsonify({'ok': True, 'created': created, 'skipped': skipped, 'errors': errors})


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
