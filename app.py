import os
from flask import Flask, render_template, redirect, session
from database import init_db
from routes.auth import auth_bp, login_required
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


def sidebar(active):
    name = session.get('name', '')
    role = session.get('role', '')
    items = [
        ('/', 'Dashboard', 'dashboard'),
        ('/pos', 'POS', 'pos'),
        (None, 'Purchase', 'purchase', [
            ('/suppliers', 'Suppliers'),
            ('/purchase-invoices', 'Purchase Invoices'),
            ('/purchase-invoices/create', 'Create Invoice'),
        ]),
        (None, 'Sales', 'sales', [
            ('/customers', 'Customers'),
            ('/sales-invoices', 'Sale Invoices'),
            ('/sales-invoices/create', 'Create Invoice'),
        ]),
        (None, 'Inventory', 'inventory', [
            ('/inventory', 'All Products'),
            ('/inventory/categories', 'Categories'),
            ('/inventory/commission-classes', 'Commission Class'),
            ('/inventory/barcode', 'Barcode Generator'),
        ]),
        (None, 'Cash And Bank Accounts', 'accounts', [
            ('/accounts', 'All Accounts'),
            ('/accounts/payments', 'Payments'),
            ('/accounts/receipts', 'Receipts'),
            ('/accounts/transfers', 'Inter Account Transfers'),
        ]),
        ('/staff', 'Staff', 'staff'),
        ('/summary', 'Summary', 'summary'),
    ]
    links = ''
    for item in items:
        if len(item) == 4:
            url, label, key, subs = item
            sub_active = any(active == s[0] or active.startswith(s[0] + '/') for s in subs)
            is_open = 'true' if sub_active else 'false'
            arrow = '&#9660;' if is_open else '&#9654;'
            if url:
                prefix = url + '/'
                is_active = active == url or active.startswith(prefix)
                links += f'<div class="nav-group"><a href="{url}" class=' + ('"active"' if is_active else '""') + f'>{label} <span class="arrow">{arrow}</span></a>'
            else:
                links += f'<div class="nav-group"><span class="group-heading" style="display:flex;align-items:center;gap:4px;padding:10px 16px;font-size:13px;font-weight:600;color:#9ca3af;cursor:pointer">{label} <span class="arrow" style="margin-left:auto;font-size:10px">{arrow}</span></span>'
            links += f'<div class="sub-group {"show" if sub_active else ""}">'
            for sub_url, sub_label in subs:
                target = ' target="_blank"' if '/create' in sub_url else ''
                links += f'<a href="{sub_url}" class="sub {"active" if active == sub_url else ""}"{target}>{sub_label}</a>'
            links += '</div></div>'
        else:
            url, label, key = item
            target = ' target="_blank"' if url == '/pos' else ''
            links += f'<a href="{url}" class=' + ('"active"' if url == active else '""') + f'{target}>{label}</a>'
    sidebar_js = '''<script>
    document.querySelector('.sidebar').addEventListener('click',function(e){
        var heading = e.target.closest('.group-heading');
        if(heading){
            var g = heading.closest('.nav-group');var s = g.querySelector('.sub-group');var ar = g.querySelector('.arrow');
            s.classList.toggle('show');ar.innerHTML = s.classList.contains('show')?'&#9660;':'&#9654;';
        }else if(e.target.classList.contains('arrow')){
            var g = e.target.closest('.nav-group');var s = g.querySelector('.sub-group');var ar = g.querySelector('.arrow');
            s.classList.toggle('show');ar.innerHTML = s.classList.contains('show')?'&#9660;':'&#9654;';e.preventDefault();
        }
    });
    </script>'''
    return f'''<div class="sidebar">
        <div class="brand">JITM <span>POS</span></div>
        <div class="sec">Main Menu</div>
        {links}
        <div class="spacer"></div>
        <div class="user"><span>{name}</span><span class="role">{role}</span></div>
    </div>
    {sidebar_js}'''


def page(template, active='/'):
    return render_template(template, role=session.get('role'), name=session.get('name'), sidebar=sidebar(active))


@app.route('/', strict_slashes=False)
@login_required
def index():
    return page('dashboard.html', '/')


@app.route('/pos', strict_slashes=False)
@login_required
def pos():
    return page('pos.html', '/pos')


@app.route('/suppliers', strict_slashes=False)
@login_required
def suppliers():
    return page('suppliers.html', '/suppliers')


@app.route('/purchase-invoices', strict_slashes=False)
@login_required
def purchase_invoices():
    return page('purchase_invoices.html', '/purchase-invoices')


@app.route('/purchase-invoices/create', strict_slashes=False)
@login_required
def create_purchase_invoice():
    return page('create_purchase_invoice.html', '/purchase-invoices/create')


@app.route('/inventory', strict_slashes=False)
@login_required
def inventory():
    return page('inventory.html', '/inventory')


@app.route('/customers', strict_slashes=False)
@login_required
def customers():
    return page('customers.html', '/customers')


@app.route('/staff', strict_slashes=False)
@login_required
def staff():
    return page('staff.html', '/staff')


@app.route('/accounts', strict_slashes=False)
@login_required
def accounts():
    return page('accounts.html', '/accounts')


@app.route('/accounts/receipts', strict_slashes=False)
@login_required
def receipts():
    return page('receipts.html', '/accounts/receipts')


@app.route('/accounts/payments', strict_slashes=False)
@login_required
def payments():
    return page('payments.html', '/accounts/payments')


@app.route('/accounts/transfers', strict_slashes=False)
@login_required
def transfers():
    return page('transfers.html', '/accounts/transfers')


@app.route('/sales-invoices', strict_slashes=False)
@login_required
def sales_invoices():
    return page('sales_invoices.html', '/sales-invoices')


@app.route('/sales-invoices/create', strict_slashes=False)
@login_required
def create_sales_invoice_page():
    return page('create_sales_invoice.html', '/sales-invoices/create')


@app.route('/sales-invoices/<int:sid>', strict_slashes=False)
@login_required
def view_sales_invoice(sid):
    from database import get_db
    with get_db() as db:
        sale = db.execute('SELECT * FROM sales WHERE id=?', (sid,)).fetchone()
        if not sale:
            return 'Not found', 404
        sale = dict(sale)
        items = db.execute('SELECT * FROM sale_items WHERE sale_id=?', (sid,)).fetchall()
        payments = db.execute('SELECT * FROM payments WHERE sale_id=?', (sid,)).fetchall()
        customer_phone = ''
        if sale.get('customer_id'):
            cust = db.execute('SELECT phone FROM customers WHERE id=?', (sale['customer_id'],)).fetchone()
            customer_phone = cust['phone'] if cust else ''
        is_return = sale.get('status') == 'returned'
        fmt = lambda n: 'Rs {:,.2f}'.format(n or 0)
        dt = (sale.get('created_at') or '').split(' ')
        item_rows = []
        for i in items:
            desc = i['product_name']
            if i['variant_label']:
                desc += ' (' + i['variant_label'] + ')'
            if i['sku']:
                desc += '<br><span style="font-size:10px;color:#9ca3af">' + i['sku'] + '</span>'
            item_rows.append([desc, abs(i['quantity']), fmt(i['price']), fmt(i['total'])])
        totals = [
            ('Sub Total', fmt(sale['subtotal']), False),
            ('Adjustment', fmt(sale['discount']), False),
            ('Total', fmt(sale['total']), True),
        ]
        cr_amt = sum(p['amount'] for p in payments if p['method'] == 'credit')
        if cr_amt > 0:
            totals.append(('Credit', fmt(cr_amt), False))
        net_cash = (sale.get('cash_tendered') or 0) - (sale.get('change_given') or 0)
        if net_cash > 0:
            totals.append(('Cash', fmt(net_cash), False))
        if sale.get('change_given'):
            totals.append(('Change', fmt(sale['change_given']), False))
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
            paid_info = 'Paid: ' + fmt(sale['paid'])
        details = [
            ('Date', dt[0] if dt else ''),
            ('Time', (dt[1] + ' ' + dt[2]) if len(dt) > 2 and len(dt) > 1 else (dt[1] if len(dt) > 1 else '')),
            ('Receipt No', sale['receipt']),
            ('Payment', sale.get('payment', '')),
            ('Staff', sale.get('staff_name', '')),
        ]
        return render_template('view_invoice.html',
            role=session.get('role'), name=session.get('name'), sidebar=sidebar('/sales-invoices'),
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


@app.route('/purchase-invoices/<int:piid>', strict_slashes=False)
@login_required
def view_purchase_invoice(piid):
    from database import get_db
    with get_db() as db:
        inv = db.execute(
            'SELECT pi.*, s.name as supplier_name FROM purchase_invoices pi '
            'LEFT JOIN suppliers s ON s.id=pi.supplier_id WHERE pi.id=?', (piid,)
        ).fetchone()
        if not inv:
            return 'Not found', 404
        inv = dict(inv)
        items = db.execute(
            'SELECT * FROM purchase_invoice_items WHERE invoice_id=? ORDER BY line_number', (piid,)
        ).fetchall()
        fmt = lambda n: 'Rs {:,.2f}'.format(n or 0)
        item_rows = []
        for i in items:
            item_rows.append([i['item'] or '', i['qty'], fmt(i['unit_price']), fmt(i['total'])])
        totals = [
            ('Invoice Amount', fmt(inv['invoice_amount']), True),
        ]
        if inv.get('balance_due'):
            totals.append(('Balance Due', fmt(inv['balance_due']), False))
        status_class = ''
        status_label = inv.get('status', '')
        if status_label == 'Paid':
            status_class = 'paid'
        elif status_label == 'Unpaid':
            status_class = 'unpaid'
        elif status_label == 'Partial':
            status_class = 'partial'
        elif status_label == 'Overpaid':
            status_class = 'overpaid'
        paid_info = ''
        if inv.get('invoice_amount') and inv.get('balance_due') is not None:
            paid_amt = inv['invoice_amount'] - inv['balance_due']
            if paid_amt > 0:
                paid_info = 'Paid: ' + fmt(paid_amt)
        details = [
            ('Issue Date', inv.get('issue_date') or ''),
            ('Due Date', inv.get('due_date') or ''),
            ('Invoice No', inv['invoice_no']),
        ]
        return render_template('view_invoice.html',
            role=session.get('role'), name=session.get('name'), sidebar=sidebar('/purchase-invoices'),
            title='Purchase Invoice',
            head_sub='Purchase Invoice',
            inv_type_label='Purchase Invoice',
            inv_number=inv['invoice_no'],
            party_label='From Supplier',
            party_name=inv.get('supplier_name') or '-',
            party_phone='',
            party_extra='',
            details=details,
            item_cols=['Item', 'Qty', 'Unit Price', 'Total'],
            items=item_rows,
            totals=totals,
            notes=inv.get('description', ''),
            status_class=status_class,
            status_label=status_label,
            paid_info=paid_info,
            back_url='/purchase-invoices',
        )


@app.route('/summary', strict_slashes=False)
@login_required
def summary():
    return page('summary.html', '/summary')


@app.route('/inventory/categories', strict_slashes=False)
@login_required
def inventory_categories():
    return page('categories.html', '/inventory/categories')


@app.route('/inventory/commission-classes', strict_slashes=False)
@login_required
def inventory_commission_classes():
    return page('commission_classes.html', '/inventory/commission-classes')


@app.route('/inventory/barcode', strict_slashes=False)
@login_required
def inventory_barcode():
    return page('barcode.html', '/inventory/barcode')


@app.route('/ledger/<entity_type>/<int:entity_id>', strict_slashes=False)
@login_required
def ledger_page(entity_type, entity_id):
    return render_template('ledger.html', role=session.get('role'), name=session.get('name'),
                           sidebar=sidebar('/ledger/' + entity_type + '/' + str(entity_id)),
                           entity_type=entity_type, entity_id=entity_id)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
