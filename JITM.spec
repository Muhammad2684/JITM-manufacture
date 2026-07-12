# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('templates', 'templates'), ('static', 'static')]
binaries = []
hiddenimports = []

# Core dependencies
for pkg in ['flask', 'flask_login', 'openpyxl', 'et_xmlfile', 'werkzeug', 'jinja2',
            'markupsafe', 'itsdangerous', 'click']:
    tmp_ret = collect_all(pkg)
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# Route modules (explicit)
hiddenimports += [
    'routes.auth', 'routes.products', 'routes.pos', 'routes.customers',
    'routes.dashboard', 'routes.suppliers', 'routes.settings', 'routes.summary',
    'routes.categories', 'routes.sizes', 'routes.purchase_invoices',
    'routes.accounts', 'routes.transactions', 'routes.ledger', 'routes.payroll',
    'routes.reports',
]

# Database module
hiddenimports += ['database']

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='JITM',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='static/icon.ico',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='JITM',
)
