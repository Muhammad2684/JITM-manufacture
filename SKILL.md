# JITM-POS Coding Skill
> Drop this file in `.skill/SKILL.md`. OpenCode reads it automatically before touching any file in this repo.
> Purpose: enforce consistent, readable code across all future AI-assisted work on this project.

---

## 1. Stack at a Glance

| Layer | Tech |
|---|---|
| Backend | Python 3, Flask, Blueprints |
| Database | SQLite via `database.py` (`get_db()`, `init_db()`) |
| Templates | Jinja2 (`.html` in `templates/`) |
| Frontend | Vanilla JS (no framework), single `static/style.css` |
| Auth | Flask session (`login_required`, `manager_required` decorators from `routes/auth.py`) |
| Currency | Pakistani Rupee — always display as `Rs X.XX`, never `$` |

---

## 2. Project Structure — Never Deviate From This

```
app.py                  ← Route stubs + sidebar() + page() helper. ONLY these.
database.py             ← init_db(), get_db(), schema migrations
routes/
  auth.py               ← login, logout, staff CRUD, decorators
  pos.py                ← /api/sale, /api/sales, /api/sales/<id>
  products.py           ← /api/products, /api/variants
  customers.py          ← /api/customers
  suppliers.py          ← /api/suppliers
  purchase_invoices.py  ← /api/purchase-invoices
  accounts.py           ← /api/accounts
  transactions.py       ← /api/transactions (payment recording, invoice status updates)
  ledger.py             ← /api/ledger
  dashboard.py          ← /api/dashboard
  summary.py            ← /api/summary
  settings.py           ← /api/settings
  categories.py         ← /api/categories
  sizes.py              ← /api/sizes
templates/              ← One .html per page, no logic, only Jinja2 + inline JS
static/style.css        ← Single global stylesheet
```

**Rules:**
- New features go in the matching existing route file. Do not create new route files unless a truly separate domain is added.
- Business logic lives in `routes/`. Templates contain zero Python-equivalent logic.
- Do not put SQL in `app.py`. The only DB call allowed in `app.py` is inside `view_sales_invoice` and `view_purchase_invoice` (already there — do not move these out, they build render context).

---

## 3. Naming Conventions

### Python variables — always descriptive, never single-letter

| Bad (old AI style) | Good |
|---|---|
| `d` | `data` or `request_data` |
| `r` | `row` |
| `c` | `customer` or `conn` (be specific) |
| `p` | `product` or `payment` (be specific per context) |
| `si` | `sale_item` |
| `q` | `search_query` |
| `cid` | `customer_id` |
| `sid` | `supplier_id` or `sale_id` (pick one per function) |
| `aid` | `account_id` |
| `pid` | `product_id` |
| `vid` | `variant_id` |
| `inv` | `invoice` |
| `acc` | `account` |
| `txn` | `transaction` |
| `amt` | `amount` |
| `qty` | `quantity` (acceptable shorthand — widely understood) |

### Functions
- Route functions: `verb_noun()` — e.g. `list_customers`, `add_product`, `complete_sale`
- Helper functions: descriptive verb phrases — e.g. `resolve_customer`, `process_sale_items`, `apply_stock_change`
- No `do_thing`, `handle_thing`, `process` without a noun

### CSS class names in templates
- Existing class names (`.ct`, `.pg`, `.pd-item`) must NOT be renamed — they are used across templates
- New classes: use full words, kebab-case — e.g. `.product-search-row`, `.payment-badge`

---

## 4. Flask Route Conventions

Every route function must have:
1. A one-line docstring explaining what it does
2. Descriptive parameter names (`customer_id` not `cid`)
3. The `@login_required` decorator (and `@manager_required` if write operation)

```python
# CORRECT
@cust_bp.route('/customers/<int:customer_id>', methods=['PUT'])
@login_required
def update_customer(customer_id):
    """Update name, phone, email, address, baby info, notes, and credit for a customer."""
    data = request.get_json()
    with get_db() as db:
        db.execute(
            'UPDATE customers SET name=?, phone=?, email=?, address=?, '
            'baby_name=?, baby_birth=?, notes=?, credit=? WHERE id=?',
            (data['name'], data.get('phone', ''), data.get('email', ''),
             data.get('address', ''), data.get('baby_name', ''),
             data.get('baby_birth', ''), data.get('notes', ''),
             float(data.get('credit', 0)), customer_id)
        )
        return jsonify({'ok': True})

# WRONG — no docstring, single-letter vars, param named `cid`
@cust_bp.route('/customers/<int:cid>', methods=['PUT'])
@login_required
def update_customer(cid):
    d = request.get_json()
    with get_db() as db:
        db.execute('UPDATE customers SET name=? WHERE id=?', (d['name'], cid))
        return jsonify({'ok': True})
```

---

## 5. Database Patterns

### Always use context manager
```python
# CORRECT
with get_db() as db:
    row = db.execute('SELECT * FROM customers WHERE id=?', (customer_id,)).fetchone()

# WRONG — never leave connection open
db = get_db()
row = db.execute(...).fetchone()
```

### Transactions with IMMEDIATE lock
Use `db.execute('BEGIN IMMEDIATE')` only when:
- Multiple tables are written in one operation (e.g. sale + sale_items + payments + stock update)
- Stock levels are being changed (race condition risk)

Single-table reads and writes do NOT need explicit `BEGIN IMMEDIATE`.

### Column access
Always access rows by column name, never by index:
```python
# CORRECT
customer_name = row['name']

# WRONG
customer_name = row[1]
```

### Migrations
Add new columns in `database.py` using try/except `ALTER TABLE`:
```python
try:
    db.execute('ALTER TABLE customers ADD COLUMN credit_limit REAL DEFAULT NULL')
except Exception:
    pass  # Column already exists
```

---

## 6. Response Format

All API routes return JSON. Standard shapes:

```python
# Success (create/update/delete)
return jsonify({'ok': True})
return jsonify({'ok': True, 'id': new_id})

# Success (read)
return jsonify([dict(row) for row in rows])
return jsonify(dict(row))

# Error
return jsonify({'error': 'Human readable message'}), 400
return jsonify({'error': 'Not found'}), 404
return jsonify({'error': 'Manager access required'}), 403
```

Never return bare strings from API routes. Never return HTML from `/api/` routes.

---

## 7. Breaking Up Large Functions

If a route function exceeds ~60 lines, extract helpers. Pattern used in this codebase:

```python
# Helper — pure function, takes db + data, returns result
def resolve_customer(db, data, session):
    """Find or create customer from request data. Returns (customer_id, customer_name)."""
    ...
    return customer_id, customer_name


def process_sale_items(db, items, is_return):
    """Validate items, compute subtotal, decrement stock. Returns (sale_items, subtotal, errors)."""
    ...
    return sale_items, subtotal, errors


# Route — orchestrates helpers, builds response
@pos_bp.route('/sale', methods=['POST'])
@login_required
def complete_sale():
    """Process a POS sale or return. Handles split payments, credit, and stock updates."""
    data = request.get_json()
    ...
    customer_id, customer_name = resolve_customer(db, data, session)
    sale_items, subtotal, errors = process_sale_items(db, data['items'], is_return)
    ...
```

Helpers live in the same file as the route, above the route function.

---

## 8. Template Conventions

### Required structure every template must follow
```html
<!DOCTYPE html>
<html>
<head>
    <title>JITM · PageName</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <link rel="stylesheet" href="/static/style.css">
    <!-- page-specific <style> block here if needed -->
</head>
<body>
    {{sidebar|safe}}
    <div class="main">
        <div class="topbar">
            <div class="page-title">Page Title</div>
            <!-- action buttons -->
        </div>
        <!-- content -->
    </div>
    <script>
        const ROLE = {{role|tojson}};
        // page JS
    </script>
</body>
</html>
```

### JS inside templates
- One `load()` function fetches data and calls `render(list)`
- One `render(list)` function generates table rows from the list
- Search: `document.getElementById('s').value.toLowerCase()` filtered inside `render()` or `load()`
- Sorting: `sortCol(n)` with `sortIdx` / `sortDir` state, `▲`/`▼` indicators via `<span id="siN">`

### Fetch pattern
```javascript
// CORRECT
fetch('/api/customers')
    .then(r => r.json())
    .then(data => render(data));

// Error handling for mutations
fetch('/api/customers', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) })
    .then(r => r.json())
    .then(data => {
        if (data.error) { alert(data.error); return; }
        load();
    });
```

### Tables
Every data table must have:
- Search bar above it: `<div class="search"><input id="s" placeholder="Search..." oninput="load()"></div>`
- `#` column as first column (SN — serial number using map index)
- Sortable columns via `onclick="sortCol(n)"`
- `<tfoot id="tf">` for numeric column totals
- Actions column (edit/delete) controlled by `if (ROLE === 'manager')` where applicable

---

## 9. Design System (Do Not Invent New Values)

```
Card bg:        #fcfbf8
Card border:    1px solid #e2e1de
Border radius:  10px
Accent blue:    #3b4fe2
Sidebar bg:     #1a1c2e
Text primary:   #1a1c2e
Text muted:     #6b7280
Success green:  #16a34a
Danger red:     #dc2626
Warning orange: #d97706
```

All monetary values: `Rs {:,.2f}.format(amount)` in Python, `'Rs ' + n.toLocaleString('en-PK', {minimumFractionDigits:2, maximumFractionDigits:2})` in JS.

---

## 10. What NOT to Do

- Do not use `print()` for debugging — use nothing, or raise exceptions
- Do not catch bare `except:` — use `except Exception as e:` and return the error
- Do not hardcode user IDs, account names, or business logic constants outside of the relevant route file
- Do not add `console.log()` statements in committed code
- Do not use `SELECT *` when you only need specific columns in a hot path (okay for low-frequency reads)
- Do not add `target="_blank"` to internal navigation links (only POS and invoice create pages open in new tab — already set in `app.py`'s sidebar)
- Do not create a new CSS file — everything goes in `static/style.css`
- Do not install new Python packages without updating `requirements.txt`

---

## 11. Git Commit Rules

After every successfully verified feature or fix:
```bash
git add -A && git commit -m "<verb>: <what changed>" && git push
```

Examples of good commit messages:
- `refactor: rename single-letter vars in pos.py`
- `fix: correct credit limit check on split payments`
- `feat: add due date filter to purchase invoices list`

Bad:
- `update`
- `fix bug`
- `changes`
