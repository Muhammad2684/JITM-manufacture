# UI Preset — JITM POS Design System

## Layout

- **Grid**: Responsive two-column (`lg:grid-cols-2`) with `gap-6 lg:gap-8`
- **Max width**: `max-w-7xl mx-auto` for content containers
- **Sidebar**: Fixed 230px dark sidebar. Main content offset by `margin-left:230px`

## Cards

- **Background**: `bg-[#fcfcf7]` (light cream)
- **Border**: `border border-gray-200`
- **Border radius**: `rounded-xl`
- **Padding**: `p-6`
- **Spacing between cards**: `space-y-6`
- **Spacing between card columns**: `gap-6 lg:gap-8`

## Section Headers

- Layout: `flex justify-between items-center`
- Bottom border: `pb-4 border-b border-gray-200`
- Margin below header: `mb-5`
- Title: `text-lg font-bold text-gray-900`
- Total value: `text-lg font-bold text-gray-900`

## Line Items

- Layout: `flex justify-between items-center py-1.5`
- Label: `text-sm text-gray-600`
- Value: `text-sm font-semibold text-indigo-600`
- Container spacing: `space-y-3`

## Typography

- Page title: `text-base font-semibold text-gray-900`
- Card headings: `text-lg font-bold text-gray-900`
- Labels: `text-sm text-gray-600`
- Values: `text-sm font-semibold text-indigo-600`
- Totals: `text-lg font-bold text-gray-900`

## Colors

- Page background: `bg-gray-50`
- Card background: `bg-[#fcfcf7]`
- Card border: `border-gray-200`
- Header bottom border: `border-gray-200`
- Value text: `text-indigo-600`
- Label text: `text-gray-600`
- Heading text: `text-gray-900`

## Data Pattern

- Fetch from API: `fetch('/api/<endpoint>').then(r=>r.json())`
- Render rows with a helper function generating `flex justify-between` markup
- Zero/null values display as `Rs 0.00`

## Example Card Structure

```html
<div class="bg-[#fcfcf7] rounded-xl border border-gray-200 p-6">
  <div class="flex justify-between items-center mb-5 pb-4 border-b border-gray-200">
    <h3 class="text-lg font-bold text-gray-900">Card Title</h3>
    <span class="text-lg font-bold text-gray-900" id="card-total">Rs 0.00</span>
  </div>
  <div id="card-items" class="space-y-3"></div>
</div>
```

## Responsive Breakpoints

- **Mobile (default)**: Single column
- **Large screens (`lg:`)**: Two columns
