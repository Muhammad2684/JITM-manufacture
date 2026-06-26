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

## Template Patterns
- Sidebar: `{{sidebar|safe}}` at top of body
- Role check in inline JS: `ROLE` JS variable set from `{{role|tojson}}`
- Modals: `class="modal"` with `id`, toggled via `classList.add/remove('show')`
- Tables rendered by inline JS `render()` functions from fetched JSON
- Inventory table columns: Product, SKU, Stock, Category, Sale Price, Avg Cost, Last P.Cost, Total Cost, (actions)
- Sortable columns via `sortCol(n)` with ▲/▼ indicators

## Default Login
- admin / admin123

## Run
```bash
python3 app.py
# Development server on http://0.0.0.0:5000
```
