"""
Database schema for JITM POS system.

Tables:
- users: System users (managers, staff) with authentication
- products: Product catalog with pricing and categorization
- variants: Product variants (size/color combinations) with stock levels
- sales: Sales transactions (invoices) with customer and payment info
- sale_items: Line items for each sale
- payments: Payment records for sales (supports split payments)
- customers: Customer records with contact info and credit tracking
- suppliers: Supplier records with contact info and balance tracking
- purchase_invoices: Purchase invoices from suppliers
- purchase_invoice_items: Line items for purchase invoices
- accounts: Cash and bank accounts for tracking money
- account_transfers: Transfers between accounts
- transactions: Financial transactions (receipts/payments) linked to accounts
- restock_log: History of stock changes with cost tracking
- expenses: Business expenses
- commission_classes: Commission rate classes for products
- categories: Product categories
- sizes: Available product sizes
- settings: System configuration key-value pairs
- raw_materials: Raw materials inventory for manufacturing
- bom: Bill of materials (raw materials required per finished product)
- recipe_profiles: Reusable recipe templates (not tied to a variant)
- recipe_profile_items: Materials in a recipe profile
- production_orders: Production orders to manufacture finished goods
- production_order_items: Line items for each production order
"""

import json
import sqlite3
import os
import sys
from werkzeug.security import generate_password_hash

if getattr(sys, 'frozen', False):
    # Packaged app: keep the database in per-user AppData, NOT next to the
    # .exe. Folders under Program Files (a) usually need admin rights to
    # write to and (b) get wiped by the uninstaller on uninstall/reinstall,
    # which is why data wasn't surviving before.
    _LEGACY_DIR = os.path.dirname(sys.executable)
    BASE_DIR = os.path.join(
        os.environ.get('LOCALAPPDATA', _LEGACY_DIR), 'JITM POS'
    )
    os.makedirs(BASE_DIR, exist_ok=True)

    # One-time migration: if an older build left data next to the .exe,
    # copy it into the new AppData location the first time this runs so
    # existing installs don't appear to "lose" their data.
    _legacy_db = os.path.join(_LEGACY_DIR, 'jitm.db')
    _new_db = os.path.join(BASE_DIR, 'jitm.db')
    if os.path.exists(_legacy_db) and not os.path.exists(_new_db):
        try:
            import shutil as _shutil
            _shutil.copy2(_legacy_db, _new_db)
            for _ext in ('-wal', '-shm'):
                if os.path.exists(_legacy_db + _ext):
                    _shutil.copy2(_legacy_db + _ext, _new_db + _ext)
        except Exception:
            pass

    _legacy_cfg = os.path.join(_LEGACY_DIR, 'instance', 'db_config.json')
    _new_cfg = os.path.join(BASE_DIR, 'instance', 'db_config.json')
    if os.path.exists(_legacy_cfg) and not os.path.exists(_new_cfg):
        try:
            import shutil as _shutil
            os.makedirs(os.path.dirname(_new_cfg), exist_ok=True)
            _shutil.copy2(_legacy_cfg, _new_cfg)
        except Exception:
            pass
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(CONFIG_DIR, 'db_config.json')


def _get_db_path():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
                path = cfg.get('db_path', '')
                if path and os.path.exists(os.path.dirname(path)):
                    return path
        except Exception:
            pass
    return os.path.join(BASE_DIR, 'jitm.db')


def set_db_path(new_path):
    abs_path = os.path.abspath(new_path)
    dirname = os.path.dirname(abs_path)
    os.makedirs(dirname, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump({'db_path': abs_path}, f)
    global DB
    DB = abs_path


DB = _get_db_path()


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with get_db() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'staff',
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT DEFAULT '',
                base_price REAL NOT NULL DEFAULT 0,
                cost_price REAL NOT NULL DEFAULT 0,
                sku TEXT UNIQUE NOT NULL,
                barcode TEXT UNIQUE DEFAULT NULL,
                has_variants INTEGER NOT NULL DEFAULT 0,
                low_stock INTEGER NOT NULL DEFAULT 5,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                size TEXT DEFAULT '',
                color TEXT DEFAULT '',
                sku TEXT NOT NULL,
                barcode TEXT UNIQUE DEFAULT NULL,
                price REAL DEFAULT NULL,
                stock INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt TEXT UNIQUE NOT NULL,
                subtotal REAL NOT NULL DEFAULT 0,
                discount REAL NOT NULL DEFAULT 0,
                discount_type TEXT DEFAULT 'percent',
                tax REAL NOT NULL DEFAULT 0,
                total REAL NOT NULL DEFAULT 0,
                payment TEXT NOT NULL DEFAULT 'cash',
                status TEXT NOT NULL DEFAULT 'completed',
                paid REAL NOT NULL DEFAULT 0,
                customer_id INTEGER REFERENCES customers(id),
                customer_name TEXT DEFAULT '',
                staff_id INTEGER NOT NULL REFERENCES users(id),
                staff_name TEXT NOT NULL,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL,
                variant_id INTEGER REFERENCES variants(id),
                product_name TEXT NOT NULL,
                variant_label TEXT DEFAULT '',
                sku TEXT DEFAULT '',
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                total REAL NOT NULL,
                is_return INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
                method TEXT NOT NULL,
                amount REAL NOT NULL,
                reference TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                address TEXT DEFAULT '',
                baby_name TEXT DEFAULT '',
                baby_birth TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                credit REAL NOT NULL DEFAULT 0,
                total_spent REAL NOT NULL DEFAULT 0,
                visit_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS restock_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                variant_id INTEGER NOT NULL REFERENCES variants(id),
                old_stock INTEGER NOT NULL,
                new_stock INTEGER NOT NULL,
                qty_added INTEGER NOT NULL,
                cost REAL DEFAULT 0,
                note TEXT DEFAULT '',
                staff_name TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                address TEXT DEFAULT '',
                contact_person TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                balance REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS commission_classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS sizes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            INSERT OR IGNORE INTO settings (key, value) VALUES
                ('store_name', 'JITM Baby Garments'),
                ('tax_rate', '8'),
                ('receipt_footer', 'Thank you for shopping with us!'),
                ('currency', 'Rs');

            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'cash',
                balance REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS account_transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_account_id INTEGER NOT NULL REFERENCES accounts(id),
                to_account_id INTEGER NOT NULL REFERENCES accounts(id),
                amount REAL NOT NULL DEFAULT 0,
                note TEXT DEFAULT '',
                date TEXT NOT NULL DEFAULT (date('now')),
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL REFERENCES accounts(id),
                type TEXT NOT NULL CHECK(type IN ('receipt','payment')),
                amount REAL NOT NULL DEFAULT 0,
                description TEXT DEFAULT '',
                party_type TEXT DEFAULT 'other',
                party_id INTEGER DEFAULT NULL,
                reference_type TEXT DEFAULT NULL,
                reference_id INTEGER DEFAULT NULL,
                allocations TEXT DEFAULT '[]',
                date TEXT NOT NULL DEFAULT (date('now')),
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS purchase_invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_no TEXT NOT NULL,
                issue_date TEXT NOT NULL,
                due_date TEXT DEFAULT '',
                supplier_id INTEGER REFERENCES suppliers(id),
                description TEXT DEFAULT '',
                invoice_amount REAL NOT NULL DEFAULT 0,
                balance_due REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Unpaid',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS purchase_invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL REFERENCES purchase_invoices(id) ON DELETE CASCADE,
                line_number INTEGER NOT NULL DEFAULT 0,
                item TEXT DEFAULT '',
                product_id INTEGER,
                qty REAL NOT NULL DEFAULT 1,
                unit_price REAL NOT NULL DEFAULT 0,
                total REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                nickname TEXT DEFAULT '',
                salary REAL NOT NULL DEFAULT 0,
                commissions REAL NOT NULL DEFAULT 0,
                advance REAL NOT NULL DEFAULT 0,
                remaining_advance REAL NOT NULL DEFAULT 0,
                overtime REAL NOT NULL DEFAULT 0,
                father_name TEXT DEFAULT '',
                cnic TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                leaves REAL NOT NULL DEFAULT 0,
                absents REAL NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
                date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'present',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                UNIQUE(employee_id, date)
            );

            CREATE TABLE IF NOT EXISTS raw_materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                unit TEXT DEFAULT '',
                stock REAL NOT NULL DEFAULT 0,
                cost_per_unit REAL NOT NULL DEFAULT 0,
                low_stock REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS bom (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                variant_id INTEGER NOT NULL REFERENCES variants(id) ON DELETE CASCADE,
                raw_material_id INTEGER NOT NULL REFERENCES raw_materials(id) ON DELETE CASCADE,
                qty_per_unit REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS recipe_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS recipe_profile_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL REFERENCES recipe_profiles(id) ON DELETE CASCADE,
                raw_material_id INTEGER NOT NULL REFERENCES raw_materials(id) ON DELETE CASCADE,
                qty_required REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS production_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_no TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                total_cost REAL NOT NULL DEFAULT 0,
                notes TEXT DEFAULT '',
                created_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                completed_at TEXT DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS production_order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                production_order_id INTEGER NOT NULL REFERENCES production_orders(id) ON DELETE CASCADE,
                product_id INTEGER NOT NULL REFERENCES products(id),
                variant_id INTEGER REFERENCES variants(id),
                quantity REAL NOT NULL DEFAULT 1,
                unit_cost REAL NOT NULL DEFAULT 0,
                total REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS material_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_material_id INTEGER NOT NULL REFERENCES raw_materials(id) ON DELETE CASCADE,
                old_qty REAL NOT NULL DEFAULT 0,
                new_qty REAL NOT NULL DEFAULT 0,
                delta REAL NOT NULL DEFAULT 0,
                reason TEXT NOT NULL DEFAULT 'Other',
                notes TEXT DEFAULT '',
                created_by TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS material_transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_material_id INTEGER NOT NULL REFERENCES raw_materials(id) ON DELETE CASCADE,
                to_material_id INTEGER NOT NULL REFERENCES raw_materials(id) ON DELETE CASCADE,
                qty REAL NOT NULL DEFAULT 0,
                date TEXT NOT NULL DEFAULT (date('now', 'localtime')),
                note TEXT DEFAULT '',
                created_by TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
        ''')

        # migrations
        try:
            db.execute('ALTER TABLE products ADD COLUMN commission_class TEXT DEFAULT NULL')
        except Exception:
            pass  # already exists

        try:
            db.execute('ALTER TABLE commission_classes ADD COLUMN percentage REAL NOT NULL DEFAULT 0')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE suppliers ADD COLUMN company_phone TEXT DEFAULT \'\'')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE suppliers ADD COLUMN supplier_code TEXT DEFAULT \'\'')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE suppliers ADD COLUMN type TEXT DEFAULT \'\'')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE suppliers ADD COLUMN area TEXT DEFAULT \'\'')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE suppliers ADD COLUMN city TEXT DEFAULT \'\'')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE suppliers ADD COLUMN country TEXT DEFAULT \'\'')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE suppliers ADD COLUMN telephone TEXT DEFAULT \'\'')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE suppliers ADD COLUMN fax TEXT DEFAULT \'\'')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE suppliers ADD COLUMN account_no TEXT DEFAULT \'\'')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE suppliers ADD COLUMN due_days INTEGER DEFAULT 0')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE purchase_invoices ADD COLUMN due_date TEXT DEFAULT \'\'')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE employees ADD COLUMN commissions REAL NOT NULL DEFAULT 0')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE employees ADD COLUMN father_name TEXT DEFAULT \'\'')
        except Exception:
            pass
        try:
            db.execute('ALTER TABLE employees ADD COLUMN cnic TEXT DEFAULT \'\'')
        except Exception:
            pass
        try:
            db.execute('ALTER TABLE employees ADD COLUMN phone TEXT DEFAULT \'\'')
        except Exception:
            pass
        try:
            db.execute('ALTER TABLE employees ADD COLUMN leaves REAL NOT NULL DEFAULT 0')
        except Exception:
            pass
        try:
            db.execute('ALTER TABLE employees ADD COLUMN absents REAL NOT NULL DEFAULT 0')
        except Exception:
            pass
        try:
            db.execute('ALTER TABLE employees ADD COLUMN overtime REAL NOT NULL DEFAULT 0')
        except Exception:
            pass
        try:
            db.execute('ALTER TABLE employees ADD COLUMN advance REAL NOT NULL DEFAULT 0')
        except Exception:
            pass
        try:
            db.execute('ALTER TABLE employees ADD COLUMN remaining_advance REAL NOT NULL DEFAULT 0')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE purchase_invoices ADD COLUMN description TEXT DEFAULT \'\'')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE sales ADD COLUMN paid REAL NOT NULL DEFAULT 0')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE sales ADD COLUMN due_date TEXT DEFAULT NULL')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE sales ADD COLUMN cash_tendered REAL DEFAULT 0')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE sales ADD COLUMN change_given REAL DEFAULT 0')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE sale_items ADD COLUMN staff_id INTEGER DEFAULT NULL')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE sale_items ADD COLUMN cost_price REAL DEFAULT 0')
        except Exception:
            pass

        # Backfill cost_price for existing sale_items using historical weighted average cost
        try:
            # First, try to calculate from restock_log (historical cost)
            db.execute('''
                UPDATE sale_items 
                SET cost_price = COALESCE(
                    (SELECT 
                        CASE 
                            WHEN SUM(rl.qty_added) > 0 
                            THEN SUM(rl.qty_added * rl.cost) / SUM(rl.qty_added)
                            ELSE 0 
                        END
                     FROM restock_log rl 
                     JOIN variants v ON v.id = rl.variant_id
                     WHERE v.id = sale_items.variant_id 
                       AND rl.created_at < (SELECT created_at FROM sales WHERE id = sale_items.sale_id)
                    ),
                    0
                )
                WHERE cost_price = 0 OR cost_price IS NULL
            ''')
            
            # For any still missing, fall back to product's current cost_price
            db.execute('''
                UPDATE sale_items 
                SET cost_price = COALESCE(
                    (SELECT p.cost_price 
                     FROM products p 
                     JOIN variants v ON v.product_id = p.id 
                     WHERE v.id = sale_items.variant_id),
                    0
                )
                WHERE cost_price = 0 OR cost_price IS NULL
            ''')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE sale_items ADD COLUMN commission REAL DEFAULT 0')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE customers ADD COLUMN credit_limit REAL DEFAULT NULL')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE products ADD COLUMN supplier_id INTEGER DEFAULT NULL REFERENCES suppliers(id)')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE products ADD COLUMN brand TEXT DEFAULT \'\'')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE products ADD COLUMN make TEXT DEFAULT \'\'')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE products ADD COLUMN color TEXT DEFAULT \'\'')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE transactions ADD COLUMN party_type TEXT DEFAULT \'other\'')
        except Exception:
            pass
        try:
            db.execute('ALTER TABLE transactions ADD COLUMN party_id INTEGER DEFAULT NULL')
        except Exception:
            pass
        try:
            db.execute('ALTER TABLE transactions ADD COLUMN reference_type TEXT DEFAULT NULL')
        except Exception:
            pass
        try:
            db.execute('ALTER TABLE transactions ADD COLUMN reference_id INTEGER DEFAULT NULL')
        except Exception:
            pass
        try:
            db.execute('ALTER TABLE transactions ADD COLUMN allocations TEXT DEFAULT \'[]\'')
        except Exception:
            pass
        try:
            db.execute('ALTER TABLE transactions ADD COLUMN expense_category TEXT DEFAULT NULL')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE users ADD COLUMN nick_name TEXT DEFAULT \'\'')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE users ADD COLUMN permissions TEXT DEFAULT \'[]\'')
        except Exception:
            pass

        try:
            db.execute('''CREATE TABLE IF NOT EXISTS purchase_invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL REFERENCES purchase_invoices(id) ON DELETE CASCADE,
                line_number INTEGER NOT NULL DEFAULT 0,
                item TEXT DEFAULT '',
                product_id INTEGER,
                qty REAL NOT NULL DEFAULT 1,
                unit_price REAL NOT NULL DEFAULT 0,
                total REAL NOT NULL DEFAULT 0
            )''')
        except Exception:
            pass

        try:
            db.execute('''CREATE TABLE IF NOT EXISTS purchase_returns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                return_no TEXT NOT NULL,
                return_date TEXT NOT NULL,
                supplier_id INTEGER REFERENCES suppliers(id),
                description TEXT DEFAULT '',
                total_amount REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )''')
        except Exception:
            pass

        try:
            db.execute('''CREATE TABLE IF NOT EXISTS purchase_return_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                return_id INTEGER NOT NULL REFERENCES purchase_returns(id) ON DELETE CASCADE,
                line_number INTEGER NOT NULL DEFAULT 0,
                item TEXT DEFAULT '',
                product_id INTEGER,
                qty REAL NOT NULL DEFAULT 1,
                unit_price REAL NOT NULL DEFAULT 0,
                total REAL NOT NULL DEFAULT 0
            )''')
        except Exception:
            pass

        try:
            db.execute('CREATE INDEX IF NOT EXISTS idx_variants_product_id ON variants(product_id)')
        except Exception:
            pass

        try:
            db.execute('CREATE INDEX IF NOT EXISTS idx_restock_log_variant_id ON restock_log(variant_id)')
        except Exception:
            pass

        # Migrate bom to variant_id (table introduced with manufacturing feature)
        try:
            cols = [r['name'] for r in db.execute('PRAGMA table_info(bom)').fetchall()]
            if 'variant_id' not in cols:
                cnt = db.execute('SELECT COUNT(*) FROM bom').fetchone()[0]
                if cnt == 0:
                    db.execute('DROP TABLE bom')
                    db.execute('''CREATE TABLE bom (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        variant_id INTEGER NOT NULL REFERENCES variants(id) ON DELETE CASCADE,
                        raw_material_id INTEGER NOT NULL REFERENCES raw_materials(id) ON DELETE CASCADE,
                        qty_per_unit REAL NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
                    )''')
                else:
                    db.execute('ALTER TABLE bom ADD COLUMN variant_id INTEGER DEFAULT NULL')
        except Exception:
            pass

        # Allow purchase invoice items to reference raw materials (manufacturing)
        try:
            db.execute('ALTER TABLE purchase_invoice_items ADD COLUMN item_type TEXT DEFAULT \'product\'')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE purchase_invoice_items ADD COLUMN raw_material_id INTEGER DEFAULT NULL')
        except Exception:
            pass

        # Track which recipe profile a BOM row came from (for "applied to" counts)
        try:
            db.execute('ALTER TABLE bom ADD COLUMN profile_id INTEGER REFERENCES recipe_profiles(id) ON DELETE SET NULL')
        except Exception:
            pass

        # Rebuild restock_log to also track raw materials: nullable variant_id,
        # raw_material_id column, and REAL stock columns (raw materials use kg/m).
        try:
            cols = [r['name'] for r in db.execute('PRAGMA table_info(restock_log)').fetchall()]
            if 'raw_material_id' not in cols:
                db.execute('''CREATE TABLE restock_log_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    variant_id INTEGER REFERENCES variants(id),
                    raw_material_id INTEGER REFERENCES raw_materials(id),
                    old_stock REAL NOT NULL,
                    new_stock REAL NOT NULL,
                    qty_added REAL NOT NULL,
                    cost REAL DEFAULT 0,
                    note TEXT DEFAULT '',
                    staff_name TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
                )''')
                db.execute('''INSERT INTO restock_log_new
                    (id, variant_id, old_stock, new_stock, qty_added, cost, note, staff_name, created_at)
                    SELECT id, variant_id, old_stock, new_stock, qty_added, cost, note, staff_name, created_at
                    FROM restock_log''')
                db.execute('DROP TABLE restock_log')
                db.execute('ALTER TABLE restock_log_new RENAME TO restock_log')
                db.execute('CREATE INDEX IF NOT EXISTS idx_restock_log_variant_id ON restock_log(variant_id)')
        except Exception:
            pass

        hashed_admin = generate_password_hash('admin123')
        hashed_staff = generate_password_hash('staff123')
        db.execute(
            'INSERT OR IGNORE INTO users (id, username, password, role, name) VALUES (?,?,?,?,?)',
            (1, 'admin', hashed_admin, 'manager', 'Manager')
        )
        db.execute(
            'INSERT OR IGNORE INTO users (id, username, password, role, name) VALUES (?,?,?,?,?)',
            (2, 'staff1', hashed_staff, 'staff', 'Staff One')
        )

        for prod in [
            (1, 'Bear Onesie', 'Onesies', 24.99, 12.00, 'ONS-001', '8901234567890'),
            (2, 'Bodysuit 3-Pack', 'Sets', 34.99, 16.00, 'BDY-001', '8901234560072'),
            (3, 'Knitted Beanie', 'Accessories', 12.99, 5.00, 'BN-001', '8901234560089'),
            (4, 'Baby Blanket', 'Bedding', 29.99, 14.00, 'BLK-001', '8901234560096'),
        ]:
            db.execute(
                'INSERT OR IGNORE INTO products (id, name, category, base_price, cost_price, sku, barcode) '
                'VALUES (?,?,?,?,?,?,?)', prod
            )
            db.execute(
                'INSERT OR IGNORE INTO variants (id, product_id, sku, stock) VALUES (?,?,?,?)',
                (prod[0], prod[0], prod[5], 0)
            )

        for cc in ['Full Commission', 'Half Commission', 'No Commission']:
            db.execute('INSERT OR IGNORE INTO commission_classes (name) VALUES (?)', (cc,))

        for cat in ['Onesies', 'Sets', 'Accessories', 'Bedding']:
            db.execute('INSERT OR IGNORE INTO categories (name) VALUES (?)', (cat,))

        seed_customers = ['Sophia Ahmed', 'Ali Raza', 'Ayesha Khan', 'Fatima Noor']
        for i, name in enumerate(seed_customers, 1):
            db.execute(
                'INSERT OR IGNORE INTO customers (id, name, phone, credit) VALUES (?,?,?,?)',
                (i, name, f'0300-000000{i}', 0)
            )

        # Clean up old reversal pairs in restock_log (legacy cleanup)
        try:
            db.execute('BEGIN IMMEDIATE')
            # Delete reversal entries (negative qty from old update code)
            db.execute('DELETE FROM restock_log WHERE qty_added < 0 AND note LIKE \'PI #%\'')
            # For duplicate positive entries with same variant and note, keep first and update its cost
            dupes = db.execute(
                'SELECT variant_id, note FROM restock_log WHERE qty_added > 0 AND note LIKE \'PI #%\' '
                'GROUP BY variant_id, note HAVING COUNT(*) > 1'
            ).fetchall()
            for d in dupes:
                rows = db.execute(
                    'SELECT id, cost FROM restock_log WHERE variant_id=? AND note=? AND qty_added > 0 ORDER BY id',
                    (d['variant_id'], d['note'])
                ).fetchall()
                if len(rows) > 1:
                    first_id = rows[0]['id']
                    last_cost = rows[-1]['cost']
                    db.execute('UPDATE restock_log SET cost=? WHERE id=?', (last_cost, first_id))
                    ids_to_delete = [r['id'] for r in rows[1:]]
                    placeholders = ','.join('?' * len(ids_to_delete))
                    db.execute(f'DELETE FROM restock_log WHERE id IN ({placeholders})', ids_to_delete)
            db.execute('COMMIT')
        except Exception:
            pass

        seed_suppliers = ['New Born Fashions', 'Kids Wear House', 'Baby Garments Co', 'Tiny Tots Suppliers']
        for i, name in enumerate(seed_suppliers, 1):
            db.execute(
                'INSERT OR IGNORE INTO suppliers (id, name, phone, balance) VALUES (?,?,?,?)',
                (i, name, f'0301-000000{i}', 0)
            )

        seed_accounts = [('POS Petty Cash', 'cash'), ('Jibraan', 'bank'), ('Ahmed', 'bank'), ('Zahid', 'bank')]
        for i, (name, typ) in enumerate(seed_accounts, 1):
            db.execute(
                'INSERT OR IGNORE INTO accounts (id, name, type, balance) VALUES (?,?,?,?)',
                (i, name, typ, 0)
            )
