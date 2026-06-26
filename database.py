import sqlite3
import os
from werkzeug.security import generate_password_hash

DB = os.path.join(os.path.dirname(__file__), 'jitm.db')


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
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
                customer_id INTEGER REFERENCES customers(id),
                customer_name TEXT DEFAULT '',
                staff_id INTEGER NOT NULL REFERENCES users(id),
                staff_name TEXT NOT NULL,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS khata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL REFERENCES customers(id),
                type TEXT NOT NULL,
                amount REAL NOT NULL,
                balance REAL NOT NULL,
                reference TEXT DEFAULT '',
                sale_id INTEGER REFERENCES sales(id),
                note TEXT DEFAULT '',
                staff_name TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS supplier_khata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
                type TEXT NOT NULL,
                amount REAL NOT NULL,
                balance REAL NOT NULL,
                reference TEXT DEFAULT '',
                note TEXT DEFAULT '',
                staff_name TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS commission_classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
            db.execute('ALTER TABLE purchase_invoices ADD COLUMN due_date TEXT DEFAULT \'\'')
        except Exception:
            pass

        try:
            db.execute('ALTER TABLE purchase_invoices ADD COLUMN description TEXT DEFAULT \'\'')
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

        db.execute(
            'INSERT OR IGNORE INTO products (id, name, category, base_price, cost_price, sku, barcode, low_stock) '
            'VALUES (?,?,?,?,?,?,?,?)',
            (1, 'Bear Onesie', 'Onesies', 24.99, 12.00, 'ONS-001', '8901234567890', 5)
        )
        db.execute(
            'INSERT OR IGNORE INTO variants (id, product_id, sku, stock) VALUES (?,?,?,?)',
            (1, 1, 'ONS-001-DEF', 81)
        )

        db.execute(
            'INSERT OR IGNORE INTO products (id, name, category, base_price, cost_price, sku, barcode) '
            'VALUES (?,?,?,?,?,?,?)',
            (2, 'Bodysuit 3-Pack', 'Sets', 34.99, 16.00, 'BDY-001', '8901234560072')
        )
        db.execute(
            'INSERT OR IGNORE INTO variants (id, product_id, sku, stock) VALUES (?,?,?,?)',
            (2, 2, 'BDY-001-DEF', 30)
        )

        db.execute(
            'INSERT OR IGNORE INTO products (id, name, category, base_price, cost_price, sku, barcode) '
            'VALUES (?,?,?,?,?,?,?)',
            (3, 'Knitted Beanie', 'Accessories', 12.99, 5.00, 'BN-001', '8901234560089')
        )
        db.execute(
            'INSERT OR IGNORE INTO variants (id, product_id, sku, stock) VALUES (?,?,?,?)',
            (3, 3, 'BN-001-DEF', 40)
        )

        db.execute(
            'INSERT OR IGNORE INTO products (id, name, category, base_price, cost_price, sku, barcode) '
            'VALUES (?,?,?,?,?,?,?)',
            (4, 'Baby Blanket', 'Bedding', 29.99, 14.00, 'BLK-001', '8901234560096')
        )
        db.execute(
            'INSERT OR IGNORE INTO variants (id, product_id, sku, stock) VALUES (?,?,?,?)',
            (4, 4, 'BLK-001-DEF', 15)
        )

        for c in [(1, 'Sarah Johnson', '555-0123', 'Emma', '2026-03'),
                   (2, 'Mike Peters', '555-0456', 'Leo', '2025-11')]:
            db.execute(
                'INSERT OR IGNORE INTO customers (id, name, phone, baby_name, baby_birth) VALUES (?,?,?,?,?)',
                c
            )

        for s in [(1, 'Wonder Wear Ltd', '555-1001', '', '', 'Ali Khan', 'Onesie supplier'),
                  (2, 'Cozy Knits', '555-1002', '', '', '', 'Beanie & blanket supplier')]:
            db.execute(
                'INSERT OR IGNORE INTO suppliers (id, name, phone, email, address, contact_person, notes) VALUES (?,?,?,?,?,?,?)',
                s
            )

        for cc in ['Full Commission', 'Half Commission', 'No Commission']:
            db.execute('INSERT OR IGNORE INTO commission_classes (name) VALUES (?)', (cc,))

        for cat in ['Onesies', 'Sets', 'Accessories', 'Bedding']:
            db.execute('INSERT OR IGNORE INTO categories (name) VALUES (?)', (cat,))
