from flask import Blueprint, jsonify
from database import get_db
from routes.auth import login_required

reports_bp = Blueprint('reports', __name__, url_prefix='/api')


@reports_bp.route('/reports/supplier-balances')
@login_required
def supplier_balances():
    with get_db() as db:
        rows = db.execute('''
            SELECT s.id, s.name, s.phone, s.balance,
                   COALESCE((SELECT SUM(v.stock * p.cost_price) FROM products p JOIN variants v ON v.product_id = p.id WHERE p.supplier_id = s.id), 0) as stock_cost
            FROM suppliers s
            ORDER BY s.balance DESC, stock_cost ASC
        ''').fetchall()
        return jsonify([dict(r) for r in rows])
