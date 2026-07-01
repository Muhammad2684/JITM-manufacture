from flask import Blueprint, jsonify, request
from database import get_db
from routes.auth import login_required

summary_bp = Blueprint('summary', __name__, url_prefix='/api')


@summary_bp.route('/summary')
@login_required
def summary():
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    with get_db() as db:
        date_filter = ''
        date_params = []
        if date_from and date_to:
            date_filter = " AND date(created_at) BETWEEN ? AND ?"
            date_params = [date_from, date_to]
        elif date_from:
            date_filter = " AND date(created_at) >= ?"
            date_params = [date_from]
        elif date_to:
            date_filter = " AND date(created_at) <= ?"
            date_params = [date_to]
        
        total_revenue = db.execute(
            "SELECT COALESCE(SUM(total),0) as total FROM sales WHERE status NOT IN ('returned')" + date_filter,
            date_params
        ).fetchone()

        total_returns = db.execute(
            "SELECT COALESCE(SUM(ABS(total)),0) as total FROM sales WHERE status='returned'" + date_filter,
            date_params
        ).fetchone()

        total_discounts = db.execute(
            "SELECT COALESCE(SUM(discount),0) as total FROM sales WHERE status NOT IN ('returned')" + date_filter,
            date_params
        ).fetchone()

        inventory_value = db.execute(
            'SELECT COALESCE(SUM(v.stock * p.cost_price),0) as total '
            'FROM variants v JOIN products p ON p.id=v.product_id'
        ).fetchone()
        
        if date_to:
            stock_added = db.execute(
                'SELECT COALESCE(SUM(qty_added),0) as total FROM restock_log WHERE date(date) <= ?',
                [date_to]
            ).fetchone()
            stock_removed = db.execute(
                'SELECT COALESCE(SUM(si.quantity),0) as total FROM sale_items si '
                'JOIN sales s ON s.id=si.sale_id '
                "WHERE s.status NOT IN ('returned') AND si.is_return=0 AND date(s.created_at) <= ?",
                [date_to]
            ).fetchone()
            net_stock = stock_added['total'] - stock_removed['total']
            avg_cost = db.execute(
                'SELECT COALESCE(AVG(cost),0) as avg FROM restock_log WHERE cost > 0 AND date(date) <= ?',
                [date_to]
            ).fetchone()
            inventory_value = {'total': net_stock * avg_cost['avg']}

        customer_credit = db.execute(
            'SELECT COALESCE(SUM(credit),0) as total FROM customers'
        ).fetchone()
        
        if date_to:
            credit_sales = db.execute(
                "SELECT COALESCE(SUM(total),0) as total FROM sales WHERE payment='credit' AND date(created_at) <= ?",
                [date_to]
            ).fetchone()
            payments_received = db.execute(
                "SELECT COALESCE(SUM(amount),0) as total FROM transactions "
                "WHERE type='receipt' AND party_type='customer' AND date(date) <= ?",
                [date_to]
            ).fetchone()
            customer_credit = {'total': credit_sales['total'] - payments_received['total']}

        cogs_raw = db.execute(
            'SELECT COALESCE(SUM(si.quantity * si.cost_price),0) as total '
            'FROM sale_items si '
            'JOIN sales s ON s.id=si.sale_id '
            "WHERE s.status NOT IN ('returned') AND si.is_return=0" + date_filter,
            date_params
        ).fetchone()

        supplier_balance = db.execute(
            'SELECT COALESCE(SUM(balance),0) as total FROM suppliers'
        ).fetchone()
        
        if date_to:
            purchases = db.execute(
                'SELECT COALESCE(SUM(invoice_amount),0) as total FROM purchase_invoices WHERE date(issue_date) <= ?',
                [date_to]
            ).fetchone()
            supplier_payments = db.execute(
                "SELECT COALESCE(SUM(amount),0) as total FROM transactions "
                "WHERE type='payment' AND party_type='supplier' AND date(date) <= ?",
                [date_to]
            ).fetchone()
            supplier_balance = {'total': purchases['total'] - supplier_payments['total']}

        account_balance = db.execute(
            'SELECT COALESCE(SUM(balance),0) as total FROM accounts'
        ).fetchone()
        
        if date_to:
            account_txns = db.execute(
                "SELECT COALESCE(SUM(CASE WHEN type='receipt' THEN amount ELSE -amount END),0) as total "
                "FROM transactions WHERE date(date) <= ?",
                [date_to]
            ).fetchone()
            account_balance = {'total': account_txns['total']}

        expense_date_filter = ''
        expense_date_params = []
        if date_from and date_to:
            expense_date_filter = " WHERE date(created_at) BETWEEN ? AND ?"
            expense_date_params = [date_from, date_to]
        elif date_from:
            expense_date_filter = " WHERE date(created_at) >= ?"
            expense_date_params = [date_from]
        elif date_to:
            expense_date_filter = " WHERE date(created_at) <= ?"
            expense_date_params = [date_to]
        
        expense_rows = db.execute(
            "SELECT category, COALESCE(SUM(amount),0) as total FROM expenses" + expense_date_filter + " GROUP BY category",
            expense_date_params
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

        total_assets = account_balance['total'] + inventory_value['total'] + customer_credit['total']
        total_liabilities = supplier_balance['total']
        equity = total_assets - total_liabilities

        return jsonify({
            'balance_sheet': {
                'assets': [
                    {'label': 'Cash / Bank', 'amount': round(account_balance['total'], 2)},
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


@summary_bp.route('/summary/details/<detail_type>')
@login_required
def summary_details(detail_type):
    """Get transaction details for summary items."""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    with get_db() as db:
        date_filter = ''
        date_params = []
        if date_from and date_to:
            date_filter = " AND date(created_at) BETWEEN ? AND ?"
            date_params = [date_from, date_to]
        elif date_from:
            date_filter = " AND date(created_at) >= ?"
            date_params = [date_from]
        elif date_to:
            date_filter = " AND date(created_at) <= ?"
            date_params = [date_to]
        
        if detail_type == 'cash_bank':
            rows = db.execute(
                'SELECT a.name, a.type, a.balance FROM accounts a ORDER BY a.name'
            ).fetchall()
            return jsonify({
                'title': 'Cash / Bank Accounts',
                'columns': ['Account', 'Type', 'Balance'],
                'rows': [
                    [r['name'], r['type'].capitalize(), f"Rs {r['balance']:.2f}"]
                    for r in rows
                ]
            })
        
        elif detail_type == 'inventory':
            rows = db.execute(
                'SELECT p.name, p.sku, v.stock, p.cost_price, (v.stock * p.cost_price) as value '
                'FROM products p '
                'JOIN variants v ON v.product_id = p.id '
                'WHERE v.stock > 0 '
                'ORDER BY p.name'
            ).fetchall()
            return jsonify({
                'title': 'Inventory Value',
                'columns': ['Product', 'SKU', 'Stock', 'Cost', 'Value'],
                'rows': [
                    [r['name'], r['sku'], str(r['stock']), f"Rs {r['cost_price']:.2f}", f"Rs {r['value']:.2f}"]
                    for r in rows
                ]
            })
        
        elif detail_type == 'customer_receivables':
            rows = db.execute(
                'SELECT name, phone, credit FROM customers WHERE credit > 0 ORDER BY credit DESC'
            ).fetchall()
            return jsonify({
                'title': 'Customer Receivables',
                'columns': ['Customer', 'Phone', 'Outstanding'],
                'rows': [
                    [r['name'], r['phone'] or '-', f"Rs {r['credit']:.2f}"]
                    for r in rows
                ]
            })
        
        elif detail_type == 'supplier_payables':
            rows = db.execute(
                'SELECT name, phone, balance FROM suppliers WHERE balance > 0 ORDER BY balance DESC'
            ).fetchall()
            return jsonify({
                'title': 'Supplier Payables',
                'columns': ['Supplier', 'Phone', 'Payable'],
                'rows': [
                    [r['name'], r['phone'] or '-', f"Rs {r['balance']:.2f}"]
                    for r in rows
                ]
            })
        
        elif detail_type == 'total_revenue':
            rows = db.execute(
                "SELECT receipt, customer_name, total, created_at FROM sales "
                "WHERE status NOT IN ('returned')" + date_filter + " "
                "ORDER BY created_at DESC LIMIT 50",
                date_params
            ).fetchall()
            return jsonify({
                'title': 'Total Revenue (Last 50 Sales)',
                'columns': ['Receipt', 'Customer', 'Total', 'Date'],
                'rows': [
                    [r['receipt'], r['customer_name'] or 'Walk-in', f"Rs {r['total']:.2f}", (r['created_at'] or '')[:10]]
                    for r in rows
                ]
            })
        
        elif detail_type == 'returns':
            rows = db.execute(
                "SELECT receipt, customer_name, ABS(total) as amount, created_at FROM sales "
                "WHERE status='returned'" + date_filter + " "
                "ORDER BY created_at DESC LIMIT 50",
                date_params
            ).fetchall()
            return jsonify({
                'title': 'Sales Returns (Last 50)',
                'columns': ['Receipt', 'Customer', 'Amount', 'Date'],
                'rows': [
                    [r['receipt'], r['customer_name'] or 'Walk-in', f"Rs {r['amount']:.2f}", (r['created_at'] or '')[:10]]
                    for r in rows
                ]
            })
        
        elif detail_type == 'discounts':
            rows = db.execute(
                "SELECT receipt, customer_name, discount, created_at FROM sales "
                "WHERE discount > 0 AND status NOT IN ('returned')" + date_filter + " "
                "ORDER BY created_at DESC LIMIT 50",
                date_params
            ).fetchall()
            return jsonify({
                'title': 'Discounts Given (Last 50)',
                'columns': ['Receipt', 'Customer', 'Discount', 'Date'],
                'rows': [
                    [r['receipt'], r['customer_name'] or 'Walk-in', f"Rs {r['discount']:.2f}", (r['created_at'] or '')[:10]]
                    for r in rows
                ]
            })
        
        elif detail_type == 'cogs':
            cogs_date_filter = ''
            cogs_date_params = []
            if date_from and date_to:
                cogs_date_filter = " AND date(s.created_at) BETWEEN ? AND ?"
                cogs_date_params = [date_from, date_to]
            elif date_from:
                cogs_date_filter = " AND date(s.created_at) >= ?"
                cogs_date_params = [date_from]
            elif date_to:
                cogs_date_filter = " AND date(s.created_at) <= ?"
                cogs_date_params = [date_to]
            
            rows = db.execute(
                'SELECT p.name, si.quantity, si.cost_price, (si.quantity * si.cost_price) as total_cost, s.receipt '
                'FROM sale_items si '
                'JOIN sales s ON s.id=si.sale_id '
                'JOIN products p ON p.id=si.product_id '
                "WHERE s.status NOT IN ('returned') AND si.is_return=0" + cogs_date_filter + " "
                'ORDER BY s.created_at DESC LIMIT 50',
                cogs_date_params
            ).fetchall()
            return jsonify({
                'title': 'Cost of Goods Sold (Last 50 Items)',
                'columns': ['Product', 'Qty', 'Cost', 'Total Cost', 'Receipt'],
                'rows': [
                    [r['name'], str(r['quantity']), f"Rs {r['cost_price']:.2f}", f"Rs {r['total_cost']:.2f}", r['receipt']]
                    for r in rows
                ]
            })
        
        elif detail_type.startswith('expense_'):
            category = detail_type.replace('expense_', '').replace('_', ' ').title()
            expense_sql = 'SELECT category, amount, note, created_at FROM expenses WHERE category=?'
            expense_params = [category]
            if date_from and date_to:
                expense_sql += " AND date(created_at) BETWEEN ? AND ?"
                expense_params.extend([date_from, date_to])
            elif date_from:
                expense_sql += " AND date(created_at) >= ?"
                expense_params.append(date_from)
            elif date_to:
                expense_sql += " AND date(created_at) <= ?"
                expense_params.append(date_to)
            expense_sql += " ORDER BY created_at DESC LIMIT 50"
            
            rows = db.execute(expense_sql, expense_params).fetchall()
            return jsonify({
                'title': f'{category} Expenses',
                'columns': ['Category', 'Amount', 'Note', 'Date'],
                'rows': [
                    [r['category'], f"Rs {r['amount']:.2f}", r['note'] or '-', (r['created_at'] or '')[:10]]
                    for r in rows
                ]
            })
        
        elif detail_type == 'total_expenses':
            expense_total_filter = ''
            expense_total_params = []
            if date_from and date_to:
                expense_total_filter = " WHERE date(created_at) BETWEEN ? AND ?"
                expense_total_params = [date_from, date_to]
            elif date_from:
                expense_total_filter = " WHERE date(created_at) >= ?"
                expense_total_params = [date_from]
            elif date_to:
                expense_total_filter = " WHERE date(created_at) <= ?"
                expense_total_params = [date_to]
            
            rows = db.execute(
                'SELECT category, SUM(amount) as total FROM expenses' + expense_total_filter + ' GROUP BY category ORDER BY total DESC',
                expense_total_params
            ).fetchall()
            return jsonify({
                'title': 'Total Expenses by Category',
                'columns': ['Category', 'Total'],
                'rows': [
                    [r['category'], f"Rs {r['total']:.2f}"]
                    for r in rows
                ]
            })
        
        return jsonify({'error': 'Invalid detail type'}), 400
