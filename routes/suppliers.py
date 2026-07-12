import csv, io

import openpyxl
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
                'INSERT INTO suppliers (name, phone, email, address, contact_person, notes, company_phone, balance) VALUES (?,?,?,?,?,?,?,?)',
                (request_data['name'], request_data.get('phone', ''), request_data.get('email', ''), request_data.get('address', ''),
                 request_data.get('contact_person', ''), request_data.get('notes', ''), request_data.get('company_phone', ''),
                 float(request_data.get('balance', 0)))
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


@sup_bp.route('/suppliers/import-template')
@login_required
def supplier_import_template():
    """Return a sample CSV template for bulk supplier import."""
    header = 'name,phone,email,address,contact_person,notes,balance,company_phone'
    sample = 'ABC Supplies,021-1234567,info@abc.com,123 Industrial Area,Ali Khan,Net 30,0,021-7654321'
    output = io.StringIO()
    output.write(header + '\n' + sample + '\n')
    return output.getvalue(), 200, {'Content-Type': 'text/csv', 'Content-Disposition': 'attachment; filename=supplier_import_template.csv'}


@sup_bp.route('/suppliers/import', methods=['POST'])
@login_required
@manager_required
def supplier_import():
    """Bulk import suppliers from CSV or Excel file. Skips duplicate names, reports errors."""
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
            row['name'] for row in db.execute('SELECT name FROM suppliers').fetchall()
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
                balance = float(row.get('balance', 0) or 0)
            except (ValueError, TypeError):
                errors.append(f'Row {idx}: invalid balance "{row.get("balance")}"')
                continue

            try:
                db.execute(
                    'INSERT INTO suppliers (name, phone, email, address, contact_person, notes, balance, company_phone) VALUES (?,?,?,?,?,?,?,?)',
                    (name, row.get('phone', ''), row.get('email', ''), row.get('address', ''),
                     row.get('contact_person', ''), row.get('notes', ''), balance, row.get('company_phone', ''))
                )
                existing_names.add(name)
                created += 1
            except Exception as e:
                errors.append(f'Row {idx}: {str(e)}')

    return jsonify({'ok': True, 'created': created, 'skipped': skipped, 'errors': errors})


@sup_bp.route('/suppliers/ledger')
@login_required
def supplier_ledger():
    """List all suppliers with their balances for the ledger view."""
    with get_db() as db:
        rows = db.execute('SELECT id, name, phone, balance FROM suppliers ORDER BY name').fetchall()
        return jsonify([dict(row) for row in rows])
