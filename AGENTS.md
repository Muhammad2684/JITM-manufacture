# JITM POS — Agent Context

## Stack
- Flask (Python 3), SQLite, Jinja2 templates, vanilla CSS/JS

## Currency
- Pakistani Rupee: `Rs` symbol, all prices display as `Rs X.XX`
- No dollar sign (`$`) anywhere in the codebase

## Design System (`static/style.css`)
- Card background: `#fcfbf8`, border: `1px solid #e2e1de`, radius: `10px`
- Accent blue: `#3b4fe2`
- Sidebar: dark `#1a1c2e`

## Database (`database.py`)
- `init_db()` is idempotent (uses `IF NOT EXISTS`)
- Column migrations: use `ALTER TABLE ADD COLUMN` wrapped in try/except
- Tables: users, products, variants, sales, sale_items, payments, customers, khata, restock_log, suppliers, supplier_khata, expenses, settings, commission_classes, categories
- `products.category` is TEXT (freeform), `categories` table is a reference list for dropdowns
- `products.commission_class` is TEXT, `commission_classes` table is a reference list

## Flask Structure
- Blueprints under `routes/` (auth, products, pos, customers, khata, dashboard, suppliers, settings, summary, categories)
- `app.py` has `sidebar(active)` function and route stubs; register new blueprints here
- `page(template, active)` renders template with role, name, sidebar

## API Conventions
- `/api/accounts` — GET (list), POST (create), PUT `/api/accounts/<id>`, DELETE `/api/accounts/<id>`
- `/api/products` — GET (list + search by `?q=`), POST (create), PUT `/api/products/<id>`
- `/api/variants` — POST (create), PUT `/api/variants/<id>`, PUT `/api/variants/<id>/stock`
- `/api/categories` — GET, POST, DELETE `/api/categories/<id>`
- `/api/commission-classes` — GET, POST, DELETE `/api/commission-classes/<id>`
- RESTful JSON, auth via session (login_required, manager_required decorators)

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
- Status is set at creation based on payment method; updated by `update_sale_due()` in `routes/transactions.py:42` when payments are applied
- `statusCell(s)` in templates renders colored badges with due amount info

## Default Login
- admin / admin123

## Run
```bash
python3 app.py
# Development server on http://0.0.0.0:5000
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
