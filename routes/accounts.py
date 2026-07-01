from flask import Blueprint, request, jsonify
from database import get_db
from routes.auth import login_required, manager_required

acc_bp = Blueprint('accounts', __name__, url_prefix='/api')


@acc_bp.route('/accounts')
@login_required
def list_accounts():
    """List all accounts ordered by name."""
    with get_db() as db:
        rows = db.execute('SELECT * FROM accounts ORDER BY name').fetchall()
        return jsonify([dict(row) for row in rows])


@acc_bp.route('/accounts', methods=['POST'])
@login_required
@manager_required
def add_account():
    """Create a new account."""
    request_data = request.get_json()
    with get_db() as db:
        try:
            cursor = db.execute(
                'INSERT INTO accounts (name, type, balance) VALUES (?,?,?)',
                (request_data['name'], request_data.get('type', 'cash'), float(request_data.get('balance', 0)))
            )
            return jsonify({'ok': True, 'id': cursor.lastrowid})
        except Exception as error:
            return jsonify({'error': str(error)}), 400


@acc_bp.route('/accounts/<int:account_id>', methods=['PUT'])
@login_required
@manager_required
def update_account(account_id):
    """Update an account's name, type, or balance."""
    request_data = request.get_json()
    with get_db() as db:
        try:
            db.execute(
                'UPDATE accounts SET name=?, type=?, balance=? WHERE id=?',
                (request_data['name'], request_data.get('type', 'cash'), float(request_data.get('balance', 0)), account_id)
            )
            return jsonify({'ok': True})
        except Exception as error:
            return jsonify({'error': str(error)}), 400


@acc_bp.route('/accounts/<int:account_id>', methods=['DELETE'])
@login_required
@manager_required
def delete_account(account_id):
    """Delete an account."""
    with get_db() as db:
        db.execute('DELETE FROM accounts WHERE id=?', (account_id,))
        return jsonify({'ok': True})


@acc_bp.route('/account-transfers')
@login_required
def list_transfers():
    """List all inter-account transfers with account names."""
    with get_db() as db:
        rows = db.execute(
            'SELECT t.*, fa.name as from_name, ta.name as to_name '
            'FROM account_transfers t '
            'JOIN accounts fa ON fa.id=t.from_account_id '
            'JOIN accounts ta ON ta.id=t.to_account_id '
            'ORDER BY t.date DESC, t.id DESC'
        ).fetchall()
        return jsonify([dict(row) for row in rows])


@acc_bp.route('/account-transfers', methods=['POST'])
@login_required
@manager_required
def add_transfer():
    """Create a new inter-account transfer and update balances."""
    request_data = request.get_json() or {}
    from_account_id = int(request_data.get('from_account_id', 0) or 0)
    to_account_id = int(request_data.get('to_account_id', 0) or 0)
    transfer_amount = float(request_data.get('amount', 0) or 0)
    
    if not from_account_id or not to_account_id:
        return jsonify({'error': 'Select both From and To accounts'}), 400
    if from_account_id == to_account_id:
        return jsonify({'error': 'From and To accounts must be different'}), 400
    if transfer_amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    
    with get_db() as db:
        try:
            source_account = db.execute('SELECT name FROM accounts WHERE id=?', (from_account_id,)).fetchone()
            if not source_account:
                return jsonify({'error': 'Source account not found'}), 404
            
            cursor = db.execute(
                'INSERT INTO account_transfers (from_account_id, to_account_id, amount, note, date) VALUES (?,?,?,?,?)',
                (from_account_id, to_account_id, transfer_amount, request_data.get('note', ''), request_data.get('date', ''))
            )
            db.execute('UPDATE accounts SET balance = balance - ? WHERE id=?', (transfer_amount, from_account_id))
            db.execute('UPDATE accounts SET balance = balance + ? WHERE id=?', (transfer_amount, to_account_id))
            return jsonify({'ok': True, 'id': cursor.lastrowid})
        except Exception as error:
            return jsonify({'error': str(error)}), 400


@acc_bp.route('/account-transfers/<int:transfer_id>', methods=['DELETE'])
@login_required
@manager_required
def delete_transfer(transfer_id):
    """Delete a transfer and reverse the balance changes."""
    with get_db() as db:
        transfer = db.execute('SELECT * FROM account_transfers WHERE id=?', (transfer_id,)).fetchone()
        if not transfer:
            return jsonify({'error': 'Transfer not found'}), 404
        transfer = dict(transfer)
        
        db.execute('UPDATE accounts SET balance = balance + ? WHERE id=?', (transfer['amount'], transfer['from_account_id']))
        db.execute('UPDATE accounts SET balance = balance - ? WHERE id=?', (transfer['amount'], transfer['to_account_id']))
        db.execute('DELETE FROM account_transfers WHERE id=?', (transfer_id,))
        return jsonify({'ok': True})


@acc_bp.route('/account-transfers/<int:transfer_id>', methods=['PUT'])
@login_required
@manager_required
def update_transfer(transfer_id):
    """Update a transfer: reverse old, apply new amounts and accounts."""
    request_data = request.get_json() or {}
    from_account_id = int(request_data.get('from_account_id', 0) or 0)
    to_account_id = int(request_data.get('to_account_id', 0) or 0)
    transfer_amount = float(request_data.get('amount', 0) or 0)
    
    if not from_account_id or not to_account_id:
        return jsonify({'error': 'Select both From and To accounts'}), 400
    if from_account_id == to_account_id:
        return jsonify({'error': 'From and To accounts must be different'}), 400
    if transfer_amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    
    with get_db() as db:
        try:
            transfer = db.execute('SELECT * FROM account_transfers WHERE id=?', (transfer_id,)).fetchone()
            if not transfer:
                return jsonify({'error': 'Transfer not found'}), 404
            transfer = dict(transfer)
            
            db.execute('UPDATE accounts SET balance = balance + ? WHERE id=?', (transfer['amount'], transfer['from_account_id']))
            db.execute('UPDATE accounts SET balance = balance - ? WHERE id=?', (transfer['amount'], transfer['to_account_id']))
            
            db.execute(
                'UPDATE account_transfers SET from_account_id=?, to_account_id=?, amount=?, note=?, date=? WHERE id=?',
                (from_account_id, to_account_id, transfer_amount, request_data.get('note', ''), request_data.get('date', ''), transfer_id)
            )
            db.execute('UPDATE accounts SET balance = balance - ? WHERE id=?', (transfer_amount, from_account_id))
            db.execute('UPDATE accounts SET balance = balance + ? WHERE id=?', (transfer_amount, to_account_id))
            return jsonify({'ok': True})
        except Exception as error:
            return jsonify({'error': str(error)}), 400
