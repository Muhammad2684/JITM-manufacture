import os
from flask import Flask, render_template, redirect, session
from database import init_db
from routes.auth import auth_bp, login_required
from routes.products import prod_bp
from routes.pos import pos_bp
from routes.customers import cust_bp
from routes.khata import khata_bp
from routes.dashboard import dash_bp
from routes.suppliers import sup_bp
from routes.settings import settings_bp
from routes.summary import summary_bp
from routes.categories import cat_bp
from routes.purchase_invoices import pi_bp

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-only-change-in-prod')

app.register_blueprint(auth_bp)
app.register_blueprint(prod_bp)
app.register_blueprint(pos_bp)
app.register_blueprint(cust_bp)
app.register_blueprint(khata_bp)
app.register_blueprint(dash_bp)
app.register_blueprint(sup_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(summary_bp)
app.register_blueprint(cat_bp)
app.register_blueprint(pi_bp)


def sidebar(active):
    name = session.get('name', '')
    role = session.get('role', '')
    items = [
        ('/', 'Dashboard', 'dashboard'),
        ('/pos', 'POS', 'pos'),
        ('/suppliers', 'Suppliers', 'suppliers'),
        ('/purchase-invoices', 'Purchase Invoice', 'purchase-invoices', [
            ('/purchase-invoices', 'All Invoices'),
            ('/purchase-invoices/create', 'Create Invoice'),
        ]),
        ('/inventory', 'Inventory', 'inventory', [
            ('/inventory/categories', 'Categories'),
            ('/inventory/commission-classes', 'Commission Class'),
        ]),
        ('/billing', 'Billing', 'billing'),
        ('/customers', 'Customers', 'customers'),
        ('/khata', 'Khata', 'khata'),
        ('/staff', 'Staff', 'staff'),
        ('/summary', 'Summary', 'summary'),
    ]
    links = ''
    for item in items:
        if len(item) == 4:
            url, label, key, subs = item
            prefix = url + '/'
            is_active = active == url or active.startswith(prefix)
            is_open = 'true' if active.startswith(prefix) else 'false'
            arrow = '&#9660;' if is_open else '&#9654;'
            links += f'<div class="nav-group"><a href="{url}" class=' + ('"active"' if is_active else '""') + f'>{label} <span class="arrow">{arrow}</span></a>'
            links += f'<div class="sub-group {"show" if active.startswith(prefix) else ""}">'
            for sub_url, sub_label in subs:
                links += f'<a href="{sub_url}" class="sub {"active" if active == sub_url else ""}">{sub_label}</a>'
            links += '</div></div>'
        else:
            url, label, key = item
            links += f'<a href="{url}" class=' + ('"active"' if url == active else '""') + f'>{label}</a>'
    return f'''<div class="sidebar">
        <div class="brand">JITM <span>POS</span></div>
        <div class="sec">Main Menu</div>
        {links}
        <div class="spacer"></div>
        <div class="user"><span>{name}</span><span class="role">{role}</span></div>
    </div>
    <script>
    document.querySelector('.sidebar').addEventListener('click',function(e){{
        if(e.target.classList.contains('arrow')){{
            var g=e.target.closest('.nav-group');var s=g.querySelector('.sub-group');var ar=g.querySelector('.arrow');
            s.classList.toggle('show');ar.innerHTML=s.classList.contains('show')?'&#9660;':'&#9654;';e.preventDefault();
        }}
    }});
    </script>'''


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


@app.route('/khata', strict_slashes=False)
@login_required
def khata():
    return page('khata.html', '/khata')


@app.route('/staff', strict_slashes=False)
@login_required
def staff():
    return page('staff.html', '/staff')


@app.route('/billing', strict_slashes=False)
@login_required
def billing():
    return page('billing.html', '/billing')


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


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
