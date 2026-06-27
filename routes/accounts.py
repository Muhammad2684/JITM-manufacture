from flask import Blueprint, request, jsonify
from database import get_db
from routes.auth import login_required, manager_required

acc_bp = Blueprint('accounts', __name__, url_prefix='/api')


@acc_bp.route('/accounts')
@login_required
def list_accounts():
    with get_db() as db:
        rows = db.execute('SELECT * FROM accounts ORDER BY name').fetchall()
        return jsonify([dict(r) for r in rows])


@acc_bp.route('/accounts', methods=['POST'])
@login_required
@manager_required
def add_account():
    d = request.get_json()
    with get_db() as db:
        try:
            cur = db.execute(
                'INSERT INTO accounts (name, type, balance) VALUES (?,?,?)',
                (d['name'], d.get('type', 'cash'), float(d.get('balance', 0)))
            )
            return jsonify({'ok': True, 'id': cur.lastrowid})
        except Exception as e:
            return jsonify({'error': str(e)}), 400


@acc_bp.route('/accounts/<int:aid>', methods=['PUT'])
@login_required
@manager_required
def update_account(aid):
    d = request.get_json()
    with get_db() as db:
        try:
            db.execute(
                'UPDATE accounts SET name=?, type=?, balance=? WHERE id=?',
                (d['name'], d.get('type', 'cash'), float(d.get('balance', 0)), aid)
            )
            return jsonify({'ok': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 400


@acc_bp.route('/accounts/<int:aid>', methods=['DELETE'])
@login_required
@manager_required
def delete_account(aid):
    with get_db() as db:
        db.execute('DELETE FROM accounts WHERE id=?', (aid,))
        return jsonify({'ok': True})


@acc_bp.route('/account-transfers')
@login_required
def list_transfers():
    with get_db() as db:
        rows = db.execute(
            'SELECT t.*, fa.name as from_name, ta.name as to_name '
            'FROM account_transfers t '
            'JOIN accounts fa ON fa.id=t.from_account_id '
            'JOIN accounts ta ON ta.id=t.to_account_id '
            'ORDER BY t.date DESC, t.id DESC'
        ).fetchall()
        return jsonify([dict(r) for r in rows])


@acc_bp.route('/account-transfers', methods=['POST'])
@login_required
@manager_required
def add_transfer():
    d = request.get_json() or {}
    from_id = int(d.get('from_account_id', 0) or 0)
    to_id = int(d.get('to_account_id', 0) or 0)
    amount = float(d.get('amount', 0) or 0)
    if not from_id or not to_id:
        return jsonify({'error': 'Select both From and To accounts'}), 400
    if from_id == to_id:
        return jsonify({'error': 'From and To accounts must be different'}), 400
    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    with get_db() as db:
        try:
            src = db.execute('SELECT name FROM accounts WHERE id=?', (from_id,)).fetchone()
            if not src:
                return jsonify({'error': 'Source account not found'}), 404
            cur = db.execute(
                'INSERT INTO account_transfers (from_account_id, to_account_id, amount, note, date) VALUES (?,?,?,?,?)',
                (from_id, to_id, amount, d.get('note', ''), d.get('date', ''))
            )
            db.execute('UPDATE accounts SET balance = balance - ? WHERE id=?', (amount, from_id))
            db.execute('UPDATE accounts SET balance = balance + ? WHERE id=?', (amount, to_id))
            return jsonify({'ok': True, 'id': cur.lastrowid})
        except Exception as e:
            return jsonify({'error': str(e)}), 400


@acc_bp.route('/account-transfers/<int:tid>', methods=['DELETE'])
@login_required
@manager_required
def delete_transfer(tid):
    with get_db() as db:
        t = db.execute('SELECT * FROM account_transfers WHERE id=?', (tid,)).fetchone()
        if not t:
            return jsonify({'error': 'Transfer not found'}), 404
        t = dict(t)
        db.execute('UPDATE accounts SET balance = balance + ? WHERE id=?', (t['amount'], t['from_account_id']))
        db.execute('UPDATE accounts SET balance = balance - ? WHERE id=?', (t['amount'], t['to_account_id']))
        db.execute('DELETE FROM account_transfers WHERE id=?', (tid,))
        return jsonify({'ok': True})


@acc_bp.route('/account-transfers/<int:tid>', methods=['PUT'])
@login_required
@manager_required
def update_transfer(tid):
    d = request.get_json() or {}
    from_id = int(d.get('from_account_id', 0) or 0)
    to_id = int(d.get('to_account_id', 0) or 0)
    amount = float(d.get('amount', 0) or 0)
    if not from_id or not to_id:
        return jsonify({'error': 'Select both From and To accounts'}), 400
    if from_id == to_id:
        return jsonify({'error': 'From and To accounts must be different'}), 400
    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    with get_db() as db:
        try:
            t = db.execute('SELECT * FROM account_transfers WHERE id=?', (tid,)).fetchone()
            if not t:
                return jsonify({'error': 'Transfer not found'}), 404
            t = dict(t)
            # Reverse old transfer
            db.execute('UPDATE accounts SET balance = balance + ? WHERE id=?', (t['amount'], t['from_account_id']))
            db.execute('UPDATE accounts SET balance = balance - ? WHERE id=?', (t['amount'], t['to_account_id']))
            # Apply new transfer
            db.execute(
                'UPDATE account_transfers SET from_account_id=?, to_account_id=?, amount=?, note=?, date=? WHERE id=?',
                (from_id, to_id, amount, d.get('note', ''), d.get('date', ''), tid)
            )
            db.execute('UPDATE accounts SET balance = balance - ? WHERE id=?', (amount, from_id))
            db.execute('UPDATE accounts SET balance = balance + ? WHERE id=?', (amount, to_id))
            return jsonify({'ok': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 400
