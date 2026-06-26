from flask import Blueprint, render_template, request, redirect, session, jsonify
from database import get_db
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    @wraps(f)
    def wrap(*a, **kw):
        if not session.get('user_id'):
            if request.is_json:
                return jsonify({'error': 'login_required'}), 401
            return redirect('/login')
        return f(*a, **kw)
    return wrap


def manager_required(f):
    @wraps(f)
    def wrap(*a, **kw):
        if session.get('role') != 'manager':
            return jsonify({'error': 'Manager access required'}), 403
        return f(*a, **kw)
    return wrap


def get_staff():
    with get_db() as db:
        return db.execute('SELECT id, username, role, name, active FROM users ORDER BY name').fetchall()


@auth_bp.route('/login', strict_slashes=False, methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.form
        with get_db() as db:
            user = db.execute(
                'SELECT * FROM users WHERE username=? AND active=1',
                (data['username'],)
            ).fetchone()
        if user and check_password_hash(user['password'], data['password']):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['name'] = user['name']
            return redirect('/')
        return '<h2>Invalid credentials</h2><a href="/login">Try again</a>'
    return render_template('login.html')


@auth_bp.route('/logout', strict_slashes=False)
def logout():
    session.clear()
    return redirect('/login')


@auth_bp.route('/api/staff')
@login_required
def api_staff():
    return jsonify([dict(r) for r in get_staff()])


@auth_bp.route('/api/staff', methods=['POST'])
@login_required
@manager_required
def api_add_staff():
    d = request.get_json()
    with get_db() as db:
        try:
            db.execute('INSERT INTO users (username, password, role, name) VALUES (?,?,?,?)',
                       (d['username'], generate_password_hash(d['password']), d.get('role', 'staff'), d['name']))
            return jsonify({'ok': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 400


@auth_bp.route('/api/staff/<int:sid>', methods=['PUT'])
@login_required
@manager_required
def api_update_staff(sid):
    d = request.get_json()
    with get_db() as db:
        if d.get('password'):
            db.execute('UPDATE users SET username=?, password=?, role=?, name=?, active=? WHERE id=?',
                       (d['username'], generate_password_hash(d['password']), d.get('role', 'staff'), d['name'], int(d.get('active', 1)), sid))
        else:
            db.execute('UPDATE users SET username=?, role=?, name=?, active=? WHERE id=?',
                       (d['username'], d.get('role', 'staff'), d['name'], int(d.get('active', 1)), sid))
        return jsonify({'ok': True})


@auth_bp.route('/api/staff/<int:sid>/analytics')
@login_required
@manager_required
def api_staff_analytics(sid):
    with get_db() as db:
        staff = db.execute('SELECT * FROM users WHERE id=?', (sid,)).fetchone()
        if not staff:
            return jsonify({'error': 'Not found'}), 404

        sales = db.execute(
            'SELECT COUNT(*) as count, COALESCE(SUM(total),0) as total FROM sales WHERE staff_id=? AND status="completed"',
            (sid,)
        ).fetchone()

        today = db.execute(
            "SELECT COUNT(*) as count, COALESCE(SUM(total),0) as total FROM sales WHERE staff_id=? AND status='completed' AND date(created_at)=date('now')",
            (sid,)
        ).fetchone()

        returns = db.execute(
            "SELECT COALESCE(SUM(ABS(total)),0) as total FROM sales WHERE staff_id=? AND status='returned'",
            (sid,)
        ).fetchone()

        recent = db.execute(
            'SELECT * FROM sales WHERE staff_id=? ORDER BY id DESC LIMIT 20',
            (sid,)
        ).fetchall()

        return jsonify({
            'staff': dict(staff),
            'total_sales': sales['count'],
            'total_revenue': sales['total'],
            'today_sales': today['count'],
            'today_revenue': today['total'],
            'total_returns': returns['total'],
            'recent_sales': [dict(r) for r in recent],
        })
