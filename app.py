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
                links += f'<a href="{sub_url}" class="sub {"active" if active == sub_url else ""}">{sub_label}</a>'
            links += '</div></div>'
        else:
            url, label, key = item
            links += f'<a href="{url}" class=' + ('"active"' if url == active else '""') + f'>{label}</a>'
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


@app.route('/ledger/<entity_type>/<int:entity_id>', strict_slashes=False)
@login_required
def ledger_page(entity_type, entity_id):
    return render_template('ledger.html', role=session.get('role'), name=session.get('name'),
                           sidebar=sidebar('/ledger/' + entity_type + '/' + str(entity_id)),
                           entity_type=entity_type, entity_id=entity_id)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
