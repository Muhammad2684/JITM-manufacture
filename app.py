import os
from flask import Flask, render_template, redirect, session
from markupsafe import escape
from database import init_db
from routes.auth import auth_bp, login_required, permission_required
from routes.products import prod_bp
from routes.pos import pos_bp
from routes.customers import cust_bp
from routes.dashboard import dash_bp
from routes.suppliers import sup_bp
from routes.settings import settings_bp
from routes.summary import summary_bp
from routes.categories import cat_bp
from routes.sizes import sizes_bp
from routes.purchase_invoices import pi_bp
from routes.accounts import acc_bp
from routes.transactions import txn_bp
from routes.ledger import ledger_bp

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-only-change-in-prod')

app.register_blueprint(auth_bp)
app.register_blueprint(prod_bp)
app.register_blueprint(pos_bp)
app.register_blueprint(cust_bp)
app.register_blueprint(dash_bp)
app.register_blueprint(sup_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(summary_bp)
app.register_blueprint(cat_bp)
app.register_blueprint(sizes_bp)
app.register_blueprint(pi_bp)
app.register_blueprint(acc_bp)
app.register_blueprint(txn_bp)
app.register_blueprint(ledger_bp)


def render_sidebar(active_page):
    """Render the sidebar navigation with the active page highlighted."""
    user_name = session.get('name', '')
    user_role = session.get('role', '')
    user_id = session.get('user_id')
    
    # Get user permissions
    user_permissions = []
    if user_role == 'manager':
        # Managers have all permissions
        user_permissions = ['dashboard', 'pos', 'purchase', 'sales', 'inventory', 'accounts', 'staff', 'summary']
    elif user_id:
        from database import get_db
        import json
        with get_db() as db:
            user = db.execute('SELECT permissions FROM users WHERE id=?', (user_id,)).fetchone()
            if user and user['permissions']:
                try:
                    user_permissions = json.loads(user['permissions'])
                except:
                    user_permissions = []
    
    menu_items = [
        {'url': '/', 'label': 'Dashboard', 'permission': 'dashboard'},
        {'url': '/pos', 'label': 'POS', 'permission': 'pos'},
        {'label': 'Purchase', 'permission': 'purchase', 'subs': [
            {'url': '/suppliers', 'label': 'Suppliers'},
            {'url': '/purchase-invoices', 'label': 'Purchase Invoices'},
            {'url': '/purchase-invoices/create', 'label': 'Create Invoice'},
        ]},
        {'label': 'Sales', 'permission': 'sales', 'subs': [
            {'url': '/customers', 'label': 'Customers'},
            {'url': '/sales-invoices', 'label': 'Sale Invoices'},
            {'url': '/sales-invoices/create', 'label': 'Create Invoice'},
        ]},
        {'label': 'Inventory', 'permission': 'inventory', 'subs': [
            {'url': '/inventory', 'label': 'All Products'},
            {'url': '/inventory/categories', 'label': 'Categories'},
            {'url': '/inventory/commission-classes', 'label': 'Commission Class'},
            {'url': '/inventory/barcode', 'label': 'Barcode Generator'},
        ]},
        {'label': 'Cash And Bank Accounts', 'permission': 'accounts', 'subs': [
            {'url': '/accounts', 'label': 'All Accounts'},
            {'url': '/accounts/payments', 'label': 'Payments'},
            {'url': '/accounts/receipts', 'label': 'Receipts'},
            {'url': '/accounts/transfers', 'label': 'Inter Account Transfers'},
        ]},
        {'url': '/staff', 'label': 'Accounts', 'permission': 'staff'},
        {'url': '/summary', 'label': 'Summary', 'permission': 'summary'},
    ]
    
    # Filter menu items based on permissions
    filtered_items = [item for item in menu_items if item.get('permission') in user_permissions]
    
    return render_template('sidebar.html', items=filtered_items, active=active_page, name=user_name, role=user_role)


def render_page(template_name, active_page='/'):
    """Render a page template with sidebar and user context."""
    return render_template(
        template_name,
        role=session.get('role'),
        name=session.get('name'),
        sidebar=render_sidebar(active_page)
    )


@app.route('/', strict_slashes=False)
@login_required
@permission_required('dashboard')
def dashboard():
    """Display the main dashboard."""
    return render_page('dashboard.html', '/')


@app.route('/pos', strict_slashes=False)
@login_required
@permission_required('pos')
def pos():
    """Display the point-of-sale terminal."""
    return render_page('pos.html', '/pos')


@app.route('/suppliers', strict_slashes=False)
@login_required
@permission_required('purchase')
def suppliers():
    """Display the suppliers list."""
    return render_page('suppliers.html', '/suppliers')


@app.route('/purchase-invoices', strict_slashes=False)
@login_required
@permission_required('purchase')
def purchase_invoices():
    """Display the purchase invoices list."""
    return render_page('purchase_invoices.html', '/purchase-invoices')


@app.route('/purchase-invoices/create', strict_slashes=False)
@login_required
@permission_required('purchase')
def create_purchase_invoice():
    """Display the create purchase invoice form."""
    return render_page('create_purchase_invoice.html', '/purchase-invoices/create')


@app.route('/inventory', strict_slashes=False)
@login_required
@permission_required('inventory')
def inventory():
    """Display the inventory product list."""
    return render_page('inventory.html', '/inventory')


@app.route('/customers', strict_slashes=False)
@login_required
@permission_required('sales')
def customers():
    """Display the customers list."""
    return render_page('customers.html', '/customers')


@app.route('/staff', strict_slashes=False)
@login_required
@permission_required('staff')
def staff():
    """Display the staff management page."""
    return render_page('staff.html', '/staff')


@app.route('/accounts', strict_slashes=False)
@login_required
@permission_required('accounts')
def accounts():
    """Display the accounts list."""
    return render_page('accounts.html', '/accounts')


@app.route('/accounts/receipts', strict_slashes=False)
@login_required
@permission_required('accounts')
def receipts():
    """Display the account receipts page."""
    return render_page('receipts.html', '/accounts/receipts')


@app.route('/accounts/payments', strict_slashes=False)
@login_required
@permission_required('accounts')
def payments():
    """Display the account payments page."""
    return render_page('payments.html', '/accounts/payments')


@app.route('/accounts/transfers', strict_slashes=False)
@login_required
@permission_required('accounts')
def transfers():
    """Display the inter-account transfers page."""
    return render_page('transfers.html', '/accounts/transfers')


@app.route('/sales-invoices', strict_slashes=False)
@login_required
@permission_required('sales')
def sales_invoices():
    """Display the sales invoices list."""
    return render_page('sales_invoices.html', '/sales-invoices')


@app.route('/sales-invoices/create', strict_slashes=False)
@login_required
@permission_required('sales')
def create_sales_invoice_page():
    """Display the create sales invoice form."""
    return render_page('create_sales_invoice.html', '/sales-invoices/create')


@app.route('/sales-invoices/<int:sale_id>', strict_slashes=False)
@login_required
@permission_required('sales')
def view_sales_invoice(sale_id):
    """Display a detailed view of a sales invoice."""
    from database import get_db
    with get_db() as db:
        sale = db.execute('SELECT * FROM sales WHERE id=?', (sale_id,)).fetchone()
        if not sale:
            return 'Not found', 404
        sale = dict(sale)
        
        sale_items = db.execute('SELECT * FROM sale_items WHERE sale_id=?', (sale_id,)).fetchall()
        sale_payments = db.execute('SELECT * FROM payments WHERE sale_id=?', (sale_id,)).fetchall()
        
        customer_phone = ''
        if sale.get('customer_id'):
            customer = db.execute('SELECT phone FROM customers WHERE id=?', (sale['customer_id'],)).fetchone()
            customer_phone = customer['phone'] if customer else ''
        
        is_return = sale.get('status') == 'returned'
        format_amount = lambda n: 'Rs {:,.2f}'.format(n or 0)
        datetime_parts = (sale.get('created_at') or '').split(' ')
        
        item_rows = []
        for item in sale_items:
            description = str(escape(item['product_name']))
            if item['variant_label']:
                description += ' (' + str(escape(item['variant_label'])) + ')'
            if item['sku']:
                description += '<br><span style="font-size:10px;color:#9ca3af">' + str(escape(item['sku'])) + '</span>'
            item_rows.append([description, abs(item['quantity']), format_amount(item['price']), format_amount(item['total'])])
        
        totals = [
            ('Sub Total', format_amount(sale['subtotal']), False),
            ('Adjustment', format_amount(sale['discount']), False),
            ('Total', format_amount(sale['total']), True),
        ]
        
        credit_amount = sum(payment['amount'] for payment in sale_payments if payment['method'] == 'credit')
        if credit_amount > 0:
            totals.append(('Credit', format_amount(credit_amount), False))
        
        net_cash = (sale.get('cash_tendered') or 0) - (sale.get('change_given') or 0)
        if net_cash > 0:
            totals.append(('Cash', format_amount(net_cash), False))
        if sale.get('change_given'):
            totals.append(('Change', format_amount(sale['change_given']), False))
        
        status_class = ''
        status_label = sale.get('status', '')
        if status_label == 'Paid':
            status_class = 'paid'
        elif status_label == 'Unpaid':
            status_class = 'unpaid'
        elif status_label == 'Partial':
            status_class = 'partial'
        elif status_label == 'Overpaid':
            status_class = 'overpaid'
        elif status_label == 'returned':
            status_class = 'unpaid'
            status_label = 'Returned'
        
        paid_info = ''
        if sale.get('paid') and sale['paid'] > 0:
            paid_info = 'Paid: ' + format_amount(sale['paid'])
        
        details = [
            ('Date', datetime_parts[0] if datetime_parts else ''),
            ('Time', (datetime_parts[1] + ' ' + datetime_parts[2]) if len(datetime_parts) > 2 and len(datetime_parts) > 1 else (datetime_parts[1] if len(datetime_parts) > 1 else '')),
            ('Receipt No', sale['receipt']),
            ('Payment', sale.get('payment', '')),
            ('Staff', sale.get('staff_name', '')),
        ]
        
        return render_template('view_invoice.html',
            role=session.get('role'), name=session.get('name'), sidebar=render_sidebar('/sales-invoices'),
            title='Sale Invoice',
            head_sub='Sale Invoice',
            inv_type_label='Sale Invoice',
            inv_number=sale['receipt'],
            party_label='Bill To',
            party_name=sale.get('customer_name') or 'Walk In Customer',
            party_phone=customer_phone,
            party_extra='',
            details=details,
            item_cols=['Description', 'Qty', 'Unit Price', 'Total'],
            items=item_rows,
            totals=totals,
            notes=sale.get('notes', ''),
            status_class=status_class,
            status_label=status_label,
            paid_info=paid_info,
            back_url='/sales-invoices',
        )


@app.route('/purchase-invoices/<int:invoice_id>', strict_slashes=False)
@login_required
@permission_required('purchase')
def view_purchase_invoice(invoice_id):
    """Display a detailed view of a purchase invoice."""
    from database import get_db
    with get_db() as db:
        invoice = db.execute(
            'SELECT pi.*, s.name as supplier_name FROM purchase_invoices pi '
            'LEFT JOIN suppliers s ON s.id=pi.supplier_id WHERE pi.id=?', (invoice_id,)
        ).fetchone()
        if not invoice:
            return 'Not found', 404
        invoice = dict(invoice)
        
        invoice_items = db.execute(
            'SELECT * FROM purchase_invoice_items WHERE invoice_id=? ORDER BY line_number', (invoice_id,)
        ).fetchall()
        
        format_amount = lambda n: 'Rs {:,.2f}'.format(n or 0)
        
        item_rows = []
        for item in invoice_items:
            item_rows.append([str(escape(item['item'] or '')), item['qty'], format_amount(item['unit_price']), format_amount(item['total'])])
        
        totals = [
            ('Invoice Amount', format_amount(invoice['invoice_amount']), True),
        ]
        if invoice.get('balance_due'):
            totals.append(('Balance Due', format_amount(invoice['balance_due']), False))
        
        status_class = ''
        status_label = invoice.get('status', '')
        if status_label == 'Paid':
            status_class = 'paid'
        elif status_label == 'Unpaid':
            status_class = 'unpaid'
        elif status_label == 'Partial':
            status_class = 'partial'
        elif status_label == 'Overpaid':
            status_class = 'overpaid'
        
        paid_info = ''
        if invoice.get('invoice_amount') and invoice.get('balance_due') is not None:
            paid_amount = invoice['invoice_amount'] - invoice['balance_due']
            if paid_amount > 0:
                paid_info = 'Paid: ' + format_amount(paid_amount)
        
        details = [
            ('Issue Date', invoice.get('issue_date') or ''),
            ('Due Date', invoice.get('due_date') or ''),
            ('Invoice No', invoice['invoice_no']),
        ]
        
        return render_template('view_invoice.html',
            role=session.get('role'), name=session.get('name'), sidebar=render_sidebar('/purchase-invoices'),
            title='Purchase Invoice',
            head_sub='Purchase Invoice',
            inv_type_label='Purchase Invoice',
            inv_number=invoice['invoice_no'],
            party_label='From Supplier',
            party_name=invoice.get('supplier_name') or '-',
            party_phone='',
            party_extra='',
            details=details,
            item_cols=['Item', 'Qty', 'Unit Price', 'Total'],
            items=item_rows,
            totals=totals,
            notes=invoice.get('description', ''),
            status_class=status_class,
            status_label=status_label,
            paid_info=paid_info,
            back_url='/purchase-invoices',
        )


@app.route('/summary', strict_slashes=False)
@login_required
@permission_required('summary')
def summary():
    """Display the business summary page."""
    return render_page('summary.html', '/summary')


@app.route('/inventory/categories', strict_slashes=False)
@login_required
@permission_required('inventory')
def inventory_categories():
    """Display the product categories management page."""
    return render_page('categories.html', '/inventory/categories')


@app.route('/inventory/commission-classes', strict_slashes=False)
@login_required
@permission_required('inventory')
def inventory_commission_classes():
    """Display the commission classes management page."""
    return render_page('commission_classes.html', '/inventory/commission-classes')


@app.route('/inventory/barcode', strict_slashes=False)
@login_required
@permission_required('inventory')
def inventory_barcode():
    """Display the barcode generator page."""
    return render_page('barcode.html', '/inventory/barcode')


@app.route('/ledger/<entity_type>/<int:entity_id>', strict_slashes=False)
@login_required
def ledger_page(entity_type, entity_id):
    """Display the ledger for a specific entity (customer or supplier)."""
    # Map entity type to permission
    permission_map = {
        'customer': 'sales',
        'supplier': 'purchase',
        'account': 'accounts',
        'product': 'inventory'
    }
    required_permission = permission_map.get(entity_type, 'dashboard')
    
    # Check permission manually for ledger
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    has_permission = False
    if user_role == 'manager':
        has_permission = True
    elif user_id:
        from database import get_db
        import json
        with get_db() as db:
            user = db.execute('SELECT permissions FROM users WHERE id=?', (user_id,)).fetchone()
            if user and user['permissions']:
                try:
                    user_permissions = json.loads(user['permissions'])
                    if required_permission in user_permissions:
                        has_permission = True
                except:
                    pass
    
    if not has_permission:
        return render_template('403.html', sidebar=render_sidebar('/'), role=user_role, name=session.get('name', '')), 403
    
    return render_template('ledger.html', role=session.get('role'), name=session.get('name'),
                           sidebar=render_sidebar('/ledger/' + entity_type + '/' + str(entity_id)),
                           entity_type=entity_type, entity_id=entity_id)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
