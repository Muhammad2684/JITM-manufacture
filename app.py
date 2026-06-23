from flask import Flask, render_template, redirect, session
from database import init_db
from routes.auth import auth_bp, login_required
from routes.products import prod_bp
from routes.pos import pos_bp
from routes.customers import cust_bp
from routes.khata import khata_bp
from routes.dashboard import dash_bp

app = Flask(__name__)
app.secret_key = 'jitm-pos-secret'

app.register_blueprint(auth_bp)
app.register_blueprint(prod_bp)
app.register_blueprint(pos_bp)
app.register_blueprint(cust_bp)
app.register_blueprint(khata_bp)
app.register_blueprint(dash_bp)


def sidebar(active):
    name = session.get('name', '')
    role = session.get('role', '')
    items = [
        ('/', 'Dashboard', 'dashboard'),
        ('/pos', 'POS', 'pos'),
        ('/inventory', 'Inventory', 'inventory'),
        ('/billing', 'Billing', 'billing'),
        ('/customers', 'Customers', 'customers'),
        ('/khata', 'Khata', 'khata'),
        ('/staff', 'Staff', 'staff'),
    ]
    links = ''.join(
        f'<a href="{url}" class=' + ('"active"' if url == active else '""') + f'>{label}</a>'
        for url, label, _ in items
    )
    return f'''<div class="sidebar">
        <div class="brand">JITM <span>POS</span></div>
        <div class="sec">Main Menu</div>
        {links}
        <div class="spacer"></div>
        <div class="user"><span>{name}</span><span class="role">{role}</span></div>
    </div>'''


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


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
