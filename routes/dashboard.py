from flask import Blueprint, jsonify
from database import get_db
from routes.auth import login_required

dash_bp = Blueprint('dashboard', __name__, url_prefix='/api')


@dash_bp.route('/dashboard')
@login_required
def dashboard():
    with get_db() as db:
        today_sales = db.execute(
            "SELECT COUNT(*) as count, COALESCE(SUM(total),0) as total FROM sales WHERE date(created_at)=date('now') AND status NOT IN ('returned')"
        ).fetchone()

        today_returns = db.execute(
            "SELECT COALESCE(SUM(ABS(total)),0) as total FROM sales WHERE date(created_at)=date('now') AND status='returned'"
        ).fetchone()

        month_sales = db.execute(
            "SELECT COUNT(*) as count, COALESCE(SUM(total),0) as total FROM sales WHERE strftime('%Y-%m',created_at)=strftime('%Y-%m','now') AND status NOT IN ('returned')"
        ).fetchone()

        low_stock = db.execute(
            'SELECT COUNT(DISTINCT v.id) as count FROM variants v JOIN products p ON p.id=v.product_id WHERE v.stock <= p.low_stock'
        ).fetchone()

        total_customers = db.execute('SELECT COUNT(*) as count FROM customers').fetchone()
        total_products = db.execute('SELECT COUNT(*) as count FROM products').fetchone()
        total_staff = db.execute('SELECT COUNT(*) as count FROM users WHERE active=1').fetchone()

        top_products = db.execute(
            'SELECT si.product_name, SUM(si.quantity) as qty, SUM(si.total) as revenue '
            'FROM sale_items si JOIN sales s ON s.id=si.sale_id '
            "WHERE strftime('%Y-%m',s.created_at)=strftime('%Y-%m','now') AND si.is_return=0 "
            'GROUP BY si.product_name ORDER BY qty DESC LIMIT 5'
        ).fetchall()

        recent_sales = db.execute(
            'SELECT * FROM sales ORDER BY id DESC LIMIT 10'
        ).fetchall()

        sales_by_day = db.execute(
            "SELECT date(created_at) as day, COALESCE(SUM(total),0) as total, COUNT(*) as count "
            "FROM sales WHERE created_at >= datetime('now', '-7 days') AND status NOT IN ('returned') "
            'GROUP BY date(created_at) ORDER BY day'
        ).fetchall()

        return jsonify({
            'today': {'sales': today_sales['count'], 'revenue': today_sales['total'],
                      'returns': today_returns['total']},
            'month': {'sales': month_sales['count'], 'revenue': month_sales['total']},
            'low_stock': low_stock['count'],
            'customers': total_customers['count'],
            'products': total_products['count'],
            'staff': total_staff['count'],
            'top_products': [dict(r) for r in top_products],
            'recent_sales': [dict(r) for r in recent_sales],
            'sales_by_day': [dict(r) for r in sales_by_day],
        })
