import sqlite3
import os

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

            INSERT OR IGNORE INTO users (id, username, password, role, name)
            VALUES (1, 'admin', 'admin123', 'manager', 'Manager');

            INSERT OR IGNORE INTO users (id, username, password, role, name)
            VALUES (2, 'staff1', 'staff123', 'staff', 'Staff One');

            INSERT OR IGNORE INTO products (id, name, category, base_price, cost_price, sku, barcode, has_variants, low_stock)
            VALUES (1, 'Bear Onesie', 'Onesies', 24.99, 12.00, 'ONS-001', '8901234567890', 1, 5);

            INSERT OR IGNORE INTO variants (id, product_id, size, color, sku, barcode, price, stock)
            VALUES
                (1, 1, '0-3M', 'Blue', 'ONS-001-03-BL', '8901234560010', NULL, 25),
                (2, 1, '0-3M', 'Pink', 'ONS-001-03-PK', '8901234560027', NULL, 20),
                (3, 1, '3-6M', 'Blue', 'ONS-001-06-BL', '8901234560034', NULL, 18),
                (4, 1, '3-6M', 'Pink', 'ONS-001-06-PK', '8901234560041', 26.99, 15),
                (5, 1, '6-12M', 'Blue', 'ONS-001-12-BL', '8901234560058', 27.99, 10),
                (6, 1, '6-12M', 'Pink', 'ONS-001-12-PK', '8901234560065', NULL, 8);

            INSERT OR IGNORE INTO products (id, name, category, base_price, cost_price, sku, barcode)
            VALUES (2, 'Bodysuit 3-Pack', 'Sets', 34.99, 16.00, 'BDY-001', '8901234560072');

            INSERT OR IGNORE INTO variants (id, product_id, size, color, sku, stock)
            VALUES (7, 2, '', '', 'BDY-001-DEF', 30);

            INSERT OR IGNORE INTO products (id, name, category, base_price, cost_price, sku, barcode)
            VALUES (3, 'Knitted Beanie', 'Accessories', 12.99, 5.00, 'BN-001', '8901234560089');

            INSERT OR IGNORE INTO variants (id, product_id, size, color, sku, stock)
            VALUES (8, 3, '', '', 'BN-001-DEF', 40);

            INSERT OR IGNORE INTO products (id, name, category, base_price, cost_price, sku, barcode)
            VALUES (4, 'Baby Blanket', 'Bedding', 29.99, 14.00, 'BLK-001', '8901234560096');

            INSERT OR IGNORE INTO variants (id, product_id, size, color, sku, stock)
            VALUES (9, 4, '', '', 'BLK-001-DEF', 15);

            INSERT OR IGNORE INTO customers (id, name, phone, baby_name, baby_birth)
            VALUES (1, 'Sarah Johnson', '555-0123', 'Emma', '2026-03');

            INSERT OR IGNORE INTO customers (id, name, phone, baby_name, baby_birth)
            VALUES (2, 'Mike Peters', '555-0456', 'Leo', '2025-11');
        ''')
