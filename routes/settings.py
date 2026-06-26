from flask import Blueprint, request, jsonify
from database import get_db
from routes.auth import login_required, manager_required

settings_bp = Blueprint('settings', __name__, url_prefix='/api')


@settings_bp.route('/settings')
@login_required
def get_settings():
    with get_db() as db:
        rows = db.execute('SELECT key, value FROM settings').fetchall()
        return jsonify({r['key']: r['value'] for r in rows})


@settings_bp.route('/settings', methods=['PUT'])
@login_required
@manager_required
def update_settings():
    d = request.get_json()
    with get_db() as db:
        for key, value in d.items():
            db.execute(
                'INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=?',
                (key, str(value), str(value))
            )
        return jsonify({'ok': True})
