# JITM POS — Agent Context

## Stack
- Flask (Python 3), SQLite, Jinja2 templates, vanilla CSS/JS
- Packaging: PyInstaller (`build.bat`, `installer.iss`) — `debug_mode` is off when frozen (`sys.frozen`)

## Currency
- Pakistani Rupee: `Rs` symbol, all prices display as `Rs X.XX`
- No dollar sign (`$`) anywhere in the codebase

## Design System (`static/style.css`)
- Card background: `#fcfbf8`, border: `1px solid #e2e1de`, radius: `10px`
- Accent blue: `#3b4fe2`
- Sidebar: dark `#1a1c2e`
- Money formatting: `Rs {:,.2f}` in Python, `'Rs ' + n.toLocaleString('en-PK', {...})` in JS

## Roles & Permissions
- Roles: `owner`, `manager`, `staff` (plus `admin` legacy). Default login: admin / admin123
- Sidebar items are permission-gated: each `menu_items` entry in `app.py` has a `permission` key
- Decorators in `routes/auth.py`: `login_required`, `manager_required`, `permission_required(permission)`
- Managers and owners implicitly have all permissions; staff need a `permissions` JSON array column on `users`

## Database (`database.py`)
- `init_db()` is idempotent (uses `IF NOT EXISTS`)
- Column migrations: use `ALTER TABLE ADD COLUMN` wrapped in try/except
- Core (POS) tables: users, products, variants, sales, sale_items, payments, customers, khata, restock_log, suppliers, supplier_khata, expenses, settings, commission_classes, categories
- Added later: sizes, accounts, account_transfers, transactions, purchase_invoices, purchase_invoice_items, purchase_returns, purchase_return_items, employees, attendance
- Manufacturing tables: raw_materials, bom, recipe_profiles, recipe_profile_items, production_orders, production_order_items, material_adjustments, material_transfers
- `products.category` is TEXT (freeform), `categories` table is a reference list for dropdowns
- `products.commission_class` is TEXT, `commission_classes` table is a reference list

## Flask Structure
- Blueprints under `routes/`: auth, products, pos, customers, khata, dashboard, suppliers, settings, summary, categories, sizes, purchase_invoices, purchase_returns, manufacturing, accounts, transactions, ledger, payroll, reports, data_management
- `app.py` (941 lines): `render_sidebar(active_page)` builds the permission-filtered nav menu; `render_page(template, active, **kwargs)` renders template with role, name, sidebar — register new blueprints at the top (lines ~102–120)
- `app.py` also holds the page route stubs (`/pos`, `/inventory`, `/sales-invoices`, ...) plus `view_sales_invoice` / `view_purchase_invoice` which build the render context DB calls
- Business logic lives in `routes/`; templates contain zero Python logic

## API Conventions
- `/api/accounts` — GET (list), POST (create), PUT `/api/accounts/<id>`, DELETE `/api/accounts/<id>`; `/api/account-transfers` — GET, POST, PUT, DELETE
- `/api/products` — GET (list + search by `?q=`), POST (create), PUT `/api/products/<id>`
- `/api/variants` — POST (create), PUT `/api/variants/<id>`, PUT `/api/variants/<id>/stock`
- `/api/categories`, `/api/commission-classes`, `/api/sizes` — GET, POST, DELETE `/api/<plural>/<id>`
- `/api/purchase-invoices` — GET, POST; `/api/purchase-invoices/<id>` — GET, PUT; `/api/purchase-returns` — GET, POST; `/api/purchase-returns/<id>` — GET, PUT
- `/api/transactions` — POST (apply payment), PUT, DELETE; payment recording updates invoice status via `update_sale_due(db, sale_id)` in `routes/transactions.py:42`
- `/api/ledger/<entity_type>/<entity_id>` — GET ledger of a customer/supplier/account
- `/api/employees` — GET, POST, PUT; payroll vouchers served from `app.py` routes (`/payroll/voucher/<eid>`, `/payroll/print/<eid>`, `/payroll/print-all`)
- `/api/reports/supplier-balances` — GET
- Data management (`/api/data/...` under `routes/data_management.py`): entities, template download, export, backup, db-path
- RESTful JSON, auth via session decorators (login_required, manager_required, permission_required)

## Manufacturing Module (`routes/manufacturing.py`)
- Raw materials — `/api/raw-materials`; rolling average cost; restocking works like products but flagged as raw material
- Recipes (BOM) — `/api/bom`; BOM lines tie a finished variant to raw material quantities
- Recipe Profiles — `/api/recipe-profiles` (+ `/api/recipe-profiles/<pid>/items` nested CRUD, `/api/recipe-profiles/<pid>/apply` consumes materials into inventory/purchase draft)
- Production Orders — `/api/production-orders`, `/api/production-orders/<oid>/complete` (complete allowed with negative raw stock after confirmation), `/api/production-orders/<oid>` PUT
- Material Transfers — `/api/material-transfers` (inter-material transfers, DELETE to reverse)
- Stock Adjustments — `/api/material-adjustments`
- Pagination applied to manufacturing pages
- Raw material value included in Summary assets; ledger page (`/ledger/<entity_type>/<entity_id>`) tracks production usage

## Inventory Product Form
- No "Has Variants" checkbox — default variant auto-created with stock=0
- No "Initial Stock" field
- SKU auto-generate checkbox ("Auto") generates `ABC123` pattern (3 letters + 3 digits), checks uniqueness against `all` array
- Category dropdown populated from `/api/categories`, includes "+ Create new category"
- Commission Class dropdown populated from `/api/commission-classes`, includes "+ Create new class"
- New categories/classes created via POST to respective API on save

## Search Bars
- All listing tables must have a search bar: `<div class="search"><input id="s" placeholder="Search..." oninput="load()"></div>` above the `.table-wrap`
- Client-side filtering in `load()` and `sortCol()`: get `document.getElementById('s').value.toLowerCase()`, then `.filter()` the list
- Search matches against relevant text fields (name, invoice_no, supplier, etc.)

## Sortable Columns Convention
- All listing tables must have sortable columns: `onclick="sortCol(n)"` on `<th>`, `<span id="siN">` for sort indicator (▲/▼)
- Each page needs: `sortIdx`, `sortDir` state variables + `sortCol(i)` function with column-specific value extractors
- The cached list (e.g. `supList`, `ccList`, `allSales`) is sorted in-place and re-rendered
- Apply this pattern to any new table added in the future

## Serial Number (SN) Column
- All data tables must include a `#` column as the first column with `onclick="sortCol(0)" style="cursor:pointer;user-select:none"># <span id="si0"></span>`
- In `render()`, add SN as the first `<td>` using the map index: `<td style="color:#6b7280;font-size:12px">'+(i+1)+'</td>` (adjust `l.map((item,i)=>` signature)
- In `sortCol()`, the first value extractor (index 0) must be `()=>0` so sorting by SN leaves the list unchanged
- All existing sort indices must be bumped by +1 (old index 0 → new index 1, etc.)

## Template Patterns
- Sidebar: `{{sidebar|safe}}` at top of body
- Role check in inline JS: `ROLE` JS variable set from `{{role|tojson}}`
- Modals: `class="modal"` with `id`, toggled via `classList.add/remove('show')`
- Tables rendered by inline JS `render()` functions from fetched JSON
- Inventory table columns: Product, SKU, Stock, Category, Sale Price, Avg Cost, Last P.Cost, Total Cost, (actions)
- Sortable columns via `sortCol(n)` with ▲/▼ indicators

## Total Footer Row
- All listing tables with numeric columns must include a `<tfoot id="tf">` after `<tbody>` for totals
- In `render()`, after populating `#tb`, compute sums from the current (filtered/sorted) list and set `#tf` innerHTML
- The totals row spans columns with `colspan` for labels, shows summed values in bold in the relevant `<td>`s
- Applied to: Inventory (Stock, Total Cost), Suppliers (Balance), Customers (Account Receivable), Purchase Invoices (Invoice Amount, Balance Due), Sales Invoices (Total)

## Sales Invoice Statuses
- **Paid** — cash/card sales fully paid (paid = total)
- **Unpaid** — credit sales, no payment collected (paid = 0)
- **Partial** — partially paid credit sales (0 < paid < total)
- **Overpaid** — customer paid more than total (paid > total)
- **returned** / **exchanged** — POS terminal returns/exchanges (separate flow)
- Status is set at creation based on payment method; updated by `update_sale_due(db, sale_id)` in `routes/transactions.py:42` when payments are applied
- `statusCell(s)` in templates renders colored badges with due amount info

## Default Login
- admin / admin123

## Run
```bash
python3 app.py
# Development server on http://0.0.0.0:5000 (debug on unless packaged/frozen)
```

## Git Workflow
This repo is the **JITM manufacturing edition** (POS base + manufacturing module).
- `origin` = `github.com/Muhammad2684/JITM-manufacture` (pushed via tokenized URL, credential embedded in remote URL)
- `pos` remote = `github.com/Muhammad2684/jitm-pos` (base POS edition; `main` ends at `4f00002`; combined history preserved on `backup-full-history`)
- Railway deployment should source from JITM-manufacture, not jitm-pos

After every successfully completed feature, run:
```bash
git add -A && git commit -m "<brief description of feature>" && git push
```
Commit immediately after verifying the feature works. Use a concise, descriptive commit message.