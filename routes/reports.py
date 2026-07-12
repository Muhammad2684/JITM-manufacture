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
                   COALESCE((SELECT COUNT(*) FROM products WHERE supplier_id = s.id), 0) as product_count
            FROM suppliers s
            ORDER BY s.balance DESC, product_count ASC
        ''').fetchall()
        return jsonify([dict(r) for r in rows])
