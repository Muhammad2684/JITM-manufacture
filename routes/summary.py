from flask import Blueprint, jsonify
from database import get_db
from routes.auth import login_required

summary_bp = Blueprint('summary', __name__, url_prefix='/api')


@summary_bp.route('/summary')
@login_required
def summary():
    with get_db() as db:
        total_revenue = db.execute(
            "SELECT COALESCE(SUM(total),0) as total FROM sales WHERE status='completed'"
        ).fetchone()

        total_returns = db.execute(
            "SELECT COALESCE(SUM(ABS(total)),0) as total FROM sales WHERE status='returned'"
        ).fetchone()

        total_discounts = db.execute(
            "SELECT COALESCE(SUM(discount),0) as total FROM sales WHERE status='completed'"
        ).fetchone()

        inventory_value = db.execute(
            'SELECT COALESCE(SUM(v.stock * p.cost_price),0) as total '
            'FROM variants v JOIN products p ON p.id=v.product_id'
        ).fetchone()

        customer_credit = db.execute(
            'SELECT COALESCE(SUM(credit),0) as total FROM customers'
        ).fetchone()

        cogs_raw = db.execute(
            'SELECT COALESCE(SUM(si.quantity * p.cost_price),0) as total '
            'FROM sale_items si '
            'JOIN sales s ON s.id=si.sale_id '
            'JOIN variants v ON v.id=si.variant_id '
            'JOIN products p ON p.id=v.product_id '
            "WHERE s.status='completed' AND si.is_return=0"
        ).fetchone()

        supplier_balance = db.execute(
            'SELECT COALESCE(SUM(balance),0) as total FROM suppliers'
        ).fetchone()

        expense_rows = db.execute(
            "SELECT category, COALESCE(SUM(amount),0) as total FROM expenses GROUP BY category"
        ).fetchall()

        expense_map = {r['category']: r['total'] for r in expense_rows}

        cost_of_goods = cogs_raw['total']
        revenue = total_revenue['total']
        returns = total_returns['total']
        discounts = total_discounts['total']
        net_revenue = revenue - returns
        gross_profit = net_revenue - cost_of_goods

        expense_categories = ['Utility Expense', 'Staff Salaries', 'Staff Commissions', 'Maintenance Expense', 'Miscellaneous Expense']
        expenses_detail = [{'label': c, 'amount': round(expense_map.get(c, 0), 2)} for c in expense_categories]
        total_expenses = sum(e['amount'] for e in expenses_detail)
        net_profit = gross_profit - discounts - total_expenses

        total_assets = revenue + inventory_value['total'] + customer_credit['total']
        total_liabilities = supplier_balance['total']
        equity = total_assets - total_liabilities

        return jsonify({
            'balance_sheet': {
                'assets': [
                    {'label': 'Cash / Bank', 'amount': round(revenue, 2)},
                    {'label': 'Inventory Value', 'amount': round(inventory_value['total'], 2)},
                    {'label': 'Customer Receivables', 'amount': round(customer_credit['total'], 2)},
                ],
                'total_assets': round(total_assets, 2),
                'liabilities': [
                    {'label': 'Supplier Payables', 'amount': round(supplier_balance['total'], 2)},
                ],
                'total_liabilities': round(total_liabilities, 2),
                'equity': [
                    {'label': "Owner's Equity", 'amount': round(equity, 2)},
                ],
                'total_equity': round(equity, 2),
            },
            'pnl': {
                'income': [
                    {'label': 'Total Revenue', 'amount': round(revenue, 2)},
                    {'label': 'Less Returns', 'amount': round(returns, 2)},
                    {'label': 'Net Revenue', 'amount': round(net_revenue, 2)},
                ],
                'expenses': [
                    {'label': 'Cost of Goods Sold', 'amount': round(cost_of_goods, 2)},
                    {'label': 'Discounts Given', 'amount': round(discounts, 2)},
                ],
                'expenses_detail': expenses_detail,
                'total_expenses': round(total_expenses, 2),
                'net_profit': round(net_profit, 2),
                'uncategorized': 0,
            },
        })
