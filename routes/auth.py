from flask import Blueprint, render_template, request, redirect, session, jsonify
from database import get_db
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
import json

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


def permission_required(permission):
    """Decorator to check if user has a specific permission."""
    def decorator(f):
        @wraps(f)
        def wrap(*a, **kw):
            user_role = session.get('role')
            user_id = session.get('user_id')
            
            # Managers have all permissions
            if user_role == 'manager':
                return f(*a, **kw)
            
            # Check user permissions
            if user_id:
                with get_db() as db:
                    user = db.execute('SELECT permissions FROM users WHERE id=?', (user_id,)).fetchone()
                    if user and user['permissions']:
                        try:
                            user_permissions = json.loads(user['permissions'])
                            if permission in user_permissions:
                                return f(*a, **kw)
                        except:
                            pass
            
            # No permission - return 403 page
            from app import render_sidebar as _rs
            return render_template('403.html', sidebar=_rs('/'), role=user_role, name=session.get('name', '')), 403
        return wrap
    return decorator


def get_staff():
    with get_db() as db:
        return db.execute('SELECT id, username, role, name, nick_name, permissions, active FROM users ORDER BY name').fetchall()


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
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    offset = (page - 1) * per_page
    
    with get_db() as db:
        total = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        staff = db.execute(
            'SELECT id, username, role, name, nick_name, permissions, active FROM users ORDER BY name LIMIT ? OFFSET ?',
            (per_page, offset)
        ).fetchall()
        
        return jsonify({
            'items': [dict(r) for r in staff],
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })


@auth_bp.route('/api/staff', methods=['POST'])
@login_required
@manager_required
def api_add_staff():
    d = request.get_json()
    with get_db() as db:
        try:
            db.execute('INSERT INTO users (username, password, role, name, nick_name, permissions) VALUES (?,?,?,?,?,?)',
                       (d['username'], generate_password_hash(d['password']), d.get('role', 'staff'), d['name'],
                        d.get('nick_name', ''), d.get('permissions', '[]')))
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
            db.execute('UPDATE users SET username=?, password=?, role=?, name=?, nick_name=?, permissions=?, active=? WHERE id=?',
                       (d['username'], generate_password_hash(d['password']), d.get('role', 'staff'), d['name'],
                        d.get('nick_name', ''), d.get('permissions', '[]'), int(d.get('active', 1)), sid))
        else:
            db.execute('UPDATE users SET username=?, role=?, name=?, nick_name=?, permissions=?, active=? WHERE id=?',
                       (d['username'], d.get('role', 'staff'), d['name'],
                        d.get('nick_name', ''), d.get('permissions', '[]'), int(d.get('active', 1)), sid))
        return jsonify({'ok': True})


@auth_bp.route('/api/staff/<int:sid>', methods=['DELETE'])
@login_required
@manager_required
def api_delete_staff(sid):
    """Delete a staff account."""
    current_user_id = session.get('user_id')
    
    if sid == current_user_id:
        return jsonify({'error': 'Cannot delete your own account'}), 400
    
    with get_db() as db:
        user = db.execute('SELECT role FROM users WHERE id=?', (sid,)).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if user['role'] == 'manager':
            manager_count = db.execute('SELECT COUNT(*) as count FROM users WHERE role=?', ('manager',)).fetchone()['count']
            if manager_count <= 1:
                return jsonify({'error': 'Cannot delete the last manager'}), 400
        
        db.execute('DELETE FROM users WHERE id=?', (sid,))
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
            "SELECT COUNT(*) as count, COALESCE(SUM(total),0) as total FROM sales WHERE staff_id=? AND status NOT IN ('returned')",
            (sid,)
        ).fetchone()

        today = db.execute(
            "SELECT COUNT(*) as count, COALESCE(SUM(total),0) as total FROM sales WHERE staff_id=? AND status NOT IN ('returned') AND date(created_at)=date('now')",
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
