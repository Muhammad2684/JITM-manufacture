"""Seed test data for payroll/month filter testing.
Run: python3 seed.py
"""
import sqlite3
import os
import random
from datetime import datetime, timedelta

DB = os.path.join(os.path.dirname(__file__), 'jitm.db')

def seed():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")

    # --- Ensure commission classes ---
    classes = [
        ('Basic', 2.0),
        ('Intermediate', 10.0),
        ('Hard', 20.0),
        ('No Commission', 0.0),
        ('Full Commission', 15.0),
        ('Half Commission', 5.0),
    ]
    for name, pct in classes:
        try:
            conn.execute("INSERT INTO commission_classes (name, percentage) VALUES (?,?)", (name, pct))
        except sqlite3.IntegrityError:
            conn.execute("UPDATE commission_classes SET percentage=? WHERE name=?", (pct, name))

    # --- Ensure employees ---
    employees_data = [
        ('Jibran', 'JIB', 20000),
        ('Ahmed', 'AHM', 25000),
        ('Sara', 'SAR', 18000),
        ('Usman', 'USM', 22000),
    ]
    for name, nick, salary in employees_data:
        existing = conn.execute("SELECT id FROM employees WHERE name=?", (name,)).fetchone()
        if not existing:
            conn.execute("INSERT INTO employees (name, nickname, salary, commissions) VALUES (?,?,?,0)", (name, nick, salary))

    all_employees = [r['id'] for r in conn.execute("SELECT id FROM employees WHERE active=1").fetchall()]

    # --- Fix old 0% commission classes ---
    conn.execute("UPDATE commission_classes SET percentage=15 WHERE name='Full Commission'")
    conn.execute("UPDATE commission_classes SET percentage=5 WHERE name='Half Commission'")

    # --- Ensure some products have commission classes ---
    conn.execute("UPDATE products SET commission_class='Hard' WHERE id=3")   # Knitted Beanie
    conn.execute("UPDATE products SET commission_class='Intermediate' WHERE id=18")  # 10% commision
    conn.execute("UPDATE products SET commission_class='Basic' WHERE id=17")  # 2% commision
    conn.execute("UPDATE products SET commission_class='Hard' WHERE id=19")  # 20% commision
    conn.execute("UPDATE products SET commission_class='Half Commission' WHERE id IN (10,15)")  # Bednet3, Diperbag
    conn.execute("UPDATE products SET commission_class='Full Commission' WHERE id=9")  # Bednet2
    conn.execute("UPDATE products SET commission_class='No Commission' WHERE id IN (5,8)")  # TEst, bednet

    # --- Pick some product variants that exist ---
    variants = conn.execute("""
        SELECT v.id, v.product_id, v.price, p.base_price, p.name, p.cost_price, p.commission_class
        FROM variants v JOIN products p ON p.id = v.product_id
        WHERE v.id IN (3, 17, 18, 19, 9, 10, 14, 15)
    """).fetchall()
    if not variants:
        print("No variants found — skipping sale creation")
        conn.commit()
        conn.close()
        return

    # --- Create sales across past months for testing ---
    # Find the max existing receipt number
    last_receipt = conn.execute("SELECT receipt FROM sales ORDER BY id DESC LIMIT 1").fetchone()
    next_num = 1000
    if last_receipt and '-' in last_receipt['receipt']:
        try:
            next_num = int(last_receipt['receipt'].split('-')[-1]) + 1
        except ValueError:
            pass

    months = ['2026-07', '2026-06', '2026-05', '2026-04', '2026-03']

    for month_str in months:
        year, month = map(int, month_str.split('-'))
        # 3-5 sales per month
        for _ in range(random.randint(3, 5)):
            # Pick a random employee
            staff_id = random.choice(all_employees)
            # Pick 1-3 random items
            num_items = random.randint(1, 3)
            chosen = random.sample(variants, min(num_items, len(variants)))

            total = 0
            sale_items = []
            for v in chosen:
                qty = random.randint(1, 3)
                price = float(v['price'] or v['base_price'] or 0)
                line_total = round(price * qty, 2)
                total += line_total

                # Look up commission_class percentage
                commission_pct = 0
                cc_name = v['commission_class']
                if cc_name:
                    cc = conn.execute("SELECT percentage FROM commission_classes WHERE name=?", (cc_name,)).fetchone()
                    if cc and cc['percentage']:
                        commission_pct = cc['percentage']

                commission = abs(line_total) * commission_pct / 100 if commission_pct else 0

                sale_items.append({
                    'product_id': v['product_id'],
                    'variant_id': v['id'],
                    'product_name': v['name'],
                    'variant_label': '',
                    'sku': '',
                    'quantity': qty,
                    'price': price,
                    'total': line_total,
                    'is_return': 0,
                    'staff_id': staff_id,
                    'cost_price': float(v['cost_price'] or 0),
                    'commission': round(commission, 2),
                })

            # Random day in month
            day = random.randint(1, 28)
            created_at = f"{year:04d}-{month:02d}-{day:02d} 10:0{random.randint(0,5)}:00"

            receipt = f"SEED-{next_num}"
            next_num += 1
            paid_amount = total if random.random() > 0.3 else 0  # 70% paid, 30% credit
            status = 'Paid' if paid_amount == total else ('Partial' if paid_amount > 0 else 'Unpaid')

            try:
                sid = conn.execute(
                    "INSERT INTO sales (receipt, subtotal, discount, discount_type, tax, total, payment, status, customer_id, customer_name, staff_id, staff_name, notes, paid, created_at) "
                    "VALUES (?,?,0,'percent',0,?,?,?,NULL,'Walk In',1,'Manager','Seeded',?,?)",
                    (receipt, total, total, 'cash' if paid_amount == total else 'credit', status,
                     paid_amount, created_at)
                ).lastrowid

                conn.execute(
                    "INSERT INTO payments (sale_id, method, amount) VALUES (?,?,?)",
                    (sid, 'cash' if paid_amount == total else 'credit', total)
                )

                for si in sale_items:
                    conn.execute(
                        "INSERT INTO sale_items (sale_id, product_id, variant_id, product_name, variant_label, sku, quantity, price, total, is_return, staff_id, cost_price, commission) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (sid, si['product_id'], si['variant_id'], si['product_name'],
                         si['variant_label'], si['sku'], si['quantity'], si['price'],
                         si['total'], si['is_return'], si['staff_id'], si['cost_price'], si['commission'])
                    )

                # Also update employee lifetime commissions
                conn.execute("UPDATE employees SET commissions=commissions+? WHERE id=?",
                             (sum(si['commission'] for si in sale_items), staff_id))

            except Exception as e:
                print(f"  Skipping sale: {e}")
                continue

    conn.commit()
    conn.close()
    print("Seed data added successfully!")


if __name__ == '__main__':
    seed()
