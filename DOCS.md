# EBAccounting — Project Documentation
> Last updated: 2026-05-26
> Version: v003

---

## What This Is

A local accounting web app built as a replacement for Wave accounting software,
tailored specifically for a contracting business. The owner uses Wave only for
estimates, invoicing, COGS/expenses, and a gross profit dashboard. This app
replicates and eventually improves on that workflow — fully local, no cloud
dependency, no subscription.

The project is named **eba-c** (EBAccounting, Claude build) to distinguish it
from a prior attempt in a separate folder.

---

## Tech Stack

| Layer    | Choice              | Why                                      |
|----------|---------------------|------------------------------------------|
| Backend  | Python + Flask      | Lightweight, local, easy to extend       |
| Database | SQLite              | Single file, zero setup, fully portable  |
| Frontend | HTML + CSS + JS     | No framework overhead, runs in browser   |
| Editor   | VS Code             | Owner's preferred environment            |
| OS       | Ubuntu              | Owner's machine                          |
| Hosting  | Local only          | Runs at localhost:5000, no deployment    |

---

## Owner / User Profile

- **Trade:** Contractor (not a developer)
- **Technical level:** Beginner coder, intermediate power user
- **Comfortable with:** Terminal basics, virtual environments, VS Code,
  Git/GitHub, high-level coding concepts
- **Prefers:** Understanding *why* things are built a certain way, not just
  copying syntax. Explanations of concepts, not hand-holding on basics.
- **Communication style:** Direct, honest feedback preferred over reassurance.
  Humour appreciated. One task at a time.
- **Workflow:** Code is written in Claude, saved in VS Code, pushed to GitHub
  at the end of each sprint.

---

## Project Structure

```
eba-c/
├── venv/                   # Python virtual environment (not committed to git)
├── templates/
│   ├── index.html          # Estimates page: list + form
│   ├── invoices.html       # Invoices page: list + form
│   └── expenses.html       # Expenses page: list + form
├── app.py                  # Flask server — routes and database queries
├── create_db.py            # Run once to create/verify database schema
├── ebaccounting.db         # SQLite database file (not committed to git)
├── requirements.txt        # Python dependencies
└── DOCS.md                 # This file
```

---

## Running the App

```bash
cd eba-c
source venv/bin/activate
python app.py
# Open http://127.0.0.1:5000 in browser
```

---

## Database Schema — Phase 1

### `customers`
Reusable customer records. Created once, linked to many estimates over time.

| Column     | Type    | Notes                        |
|------------|---------|------------------------------|
| id         | INTEGER | Primary key, auto-increment  |
| name       | TEXT    | Required                     |
| email      | TEXT    |                              |
| phone      | TEXT    |                              |
| address    | TEXT    |                              |
| created_at | TEXT    | Auto-set to datetime('now')  |

### `estimates`
One row per estimate.

| Column             | Type    | Notes                                          |
|--------------------|---------|------------------------------------------------|
| id                 | INTEGER | Primary key, auto-increment                    |
| customer_id        | INTEGER | Foreign key → customers.id                     |
| estimate_number    | TEXT    | Internal reference, unique (e.g. EST-001)      |
| customer_reference | TEXT    | Their PO / WO / address                        |
| status             | TEXT    | draft / sent / accepted / declined             |
| notes              | TEXT    |                                                |
| created_at         | TEXT    | Auto-set                                       |
| updated_at         | TEXT    | Auto-set (not yet wired to update on save)     |

### `estimate_line_items`
Each line on an estimate. Totals are calculated dynamically, never stored.

| Column      | Type    | Notes                                      |
|-------------|---------|--------------------------------------------|
| id          | INTEGER | Primary key, auto-increment                |
| estimate_id | INTEGER | Foreign key → estimates.id (CASCADE delete)|
| description | TEXT    | Required                                   |
| quantity    | REAL    |                                            |
| unit_price  | REAL    |                                            |
| taxable     | INTEGER | 0 = no GST, 1 = apply GST (5%)             |

**GST rate (5%) lives in index.html as `const GST_RATE = 0.05` — update there if needed.**

---

## Database Schema — Phase 2

### `invoices`
One row per invoice. Optionally linked back to a source estimate.

| Column             | Type    | Notes                                          |
|--------------------|---------|------------------------------------------------|
| id                 | INTEGER | Primary key, auto-increment                    |
| customer_id        | INTEGER | Foreign key → customers.id                     |
| estimate_id        | INTEGER | Nullable FK → estimates.id (null if scratch)   |
| invoice_number     | TEXT    | Auto-generated (e.g. INV-001), unique          |
| customer_reference | TEXT    | Their PO / WO / address                        |
| status             | TEXT    | draft / sent / partial / paid / overdue        |
| notes              | TEXT    |                                                |
| issued_date        | TEXT    |                                                |
| due_date           | TEXT    | Defaults to +30 days from issued in UI         |
| created_at         | TEXT    | Auto-set                                       |
| updated_at         | TEXT    | Auto-set (not yet wired to update on save)     |

### `invoice_line_items`
Independent copy of line items — not linked to estimate_line_items.

| Column      | Type    | Notes                                       |
|-------------|---------|---------------------------------------------|
| id          | INTEGER | Primary key, auto-increment                 |
| invoice_id  | INTEGER | Foreign key → invoices.id (CASCADE delete)  |
| description | TEXT    | Required                                    |
| quantity    | REAL    |                                             |
| unit_price  | REAL    |                                             |
| taxable     | INTEGER | 0 = no GST, 1 = apply GST (5%)              |

### Database Schema — Phase 3
payments
One row per payment received. A single invoice can have multiple payment rows
(partial payments). Balance owing is calculated at query time, never stored.

Column        / Type    / Notes
-------------------------------------------------------------------------
id            / INTEGER / Primary key, auto-increment
invoice_id    / INTEGER / Foreign key → invoices.id (CASCADE delete)
amount        / REAL    / Required
payment_date  / TEXT    / Required
method        / TEXT    / e-transfer / cheque / cash / credit card / bitcoin
notes         / TEXT    / Optional — post-dated, deposit, etc.
created_at    / TEXT    / Auto-set

### `vendors`
Reusable vendor records. Created once, referenced by expenses.

| Column     | Type    | Notes                        |
|------------|---------|------------------------------|
| id         | INTEGER | Primary key, auto-increment  |
| name       | TEXT    | Required                     |
| phone      | TEXT    |                              |
| email      | TEXT    |                              |
| notes      | TEXT    |                              |
| created_at | TEXT    | Auto-set to datetime('now')  |

### `expenses`
One row per expense. Cash-basis: recorded when money leaves.

| Column       | Type    | Notes                                           |
|--------------|---------|-------------------------------------------------|
| id           | INTEGER | Primary key, auto-increment                     |
| vendor_id    | INTEGER | Nullable FK → vendors.id                        |
| invoice_id   | INTEGER | Nullable FK → invoices.id (future job costing)  |
| estimate_id  | INTEGER | Nullable FK → estimates.id (future job costing) |
| category     | TEXT    | Defaults to 'cogs' — full picker in later sprint|
| description  | TEXT    | Optional                                        |
| amount       | REAL    | Required                                        |
| gst_paid     | REAL    | Nullable — entered manually, no rate logic yet  |
| expense_date | TEXT    | Required                                        |
| created_at   | TEXT    | Auto-set                                        |

---

## Phased Roadmap

| Phase | Scope                              | Status      |
|-------|------------------------------------|-------------|
| 1     | Customers, Estimates, Line Items   | ✅ Complete |
| 2     | Invoices (convert from estimates)  | ✅ Complete |
| 3     | Payments incl. partial payments    | ✅ Complete |
| 4     | Expenses / COGS                    | Planned     |
| 5     | Dashboard (gross profit, due, etc) | Planned     |

### Phase 2 Design Note
Invoices have their own tables (`invoices`, `invoice_line_items`) with an
optional `estimate_id` foreign key linking back to the source estimate.
Converting an estimate to an invoice **copies** the data — it does not rename
or delete the estimate. This preserves the original record and allows the
invoice to diverge if scope changed.

### Phase 3 Design Note
Payments support partial payments via a separate payments table linked to
invoices by invoice_id, with one row per payment. Balance owing is
calculated dynamically from invoice grand total minus SUM(payments.amount).
Balance is never stored — same principle as line item totals.

### Phase 4 Design Note
Expenses are recorded on a cash basis — one row per expense, logged when
money leaves. Vendor, invoice, and estimate FKs are all nullable so expenses
can be logged without those relationships for now, with job costing available
as a later bolt-on.

Category defaults to 'cogs' for v0. The column exists and accepts any string,
so a full category picker (overhead, other, CRA-specific labels) can be added
in a later sprint without schema changes.

GST paid is a flat nullable field — you enter what you paid, no rate logic.
A `tax_rates` table with named, configurable rates for both sales and purchase
taxes is planned for a later sprint.

Expense line items are not implemented in v0. The flat `amount` field maps
cleanly to a single line item, making a future migration to an
`expense_line_items` child table mechanical and scriptable when the time comes.

---

## V0 Cleanup Backlog
Items deferred from active sprints. To be addressed in a dedicated cleanup
session after the dashboard sprint.

- **Filter accepted estimates from the estimates list.** Once an estimate is
  converted to an invoice, it crowds the active list. Need a way to hide
  accepted estimates by default with an option to recall them if needed.
- Add 'edit customers' function to update customer info

---

## Future versions 
Items deferred to later version (v1,v2,etc) to keep v0 mission-focused

- Taxes: When the time comes, the clean solution is a tax_rates table — name, rate, applies_to (sales/purchases/both), jurisdiction, whatever. Then expenses and invoices reference it by ID. That's a self-contained sprint that doesn't touch anything already built — just adds the table, updates the UI dropdowns, done.
- Accounts Payable: To support that properly later you'd want something like a bills table (the obligation) and a bill_payments table (the cash out) — same pattern as invoices/payments but on the expense side. The current expenses table is cash-only by nature.
- Expense line items: We'll need a migration from 
- Right before going live: grab Wave CSVs to secure historical data and see if we can port it to our new app without too much yak shaving. Otherwise archive and start with fresh data.

## Key Design Decisions (and Why)

**Totals are never stored in the database.**
Subtotal, GST, and grand total are always calculated from line items at
display time. Storing derived values risks them going out of sync with their
source data.

**One customer per estimate.**
Confirmed with owner — no need for multi-customer or split-billing support.

**Estimates and invoices are separate records.**
Even though invoices often originate from estimates, they are stored
independently. The link is preserved via `estimate_id` on the invoice.

**API routes are namespaced under `/api/`.**
Page routes (returning HTML) and data routes (returning JSON) are kept
separate. Convention: `/api/x` for JSON, `/x` for pages. Established in
Phase 2 to keep the codebase readable as it grows.

**SQLite over LibreOffice or other options.**
SQLite is a single portable file, requires no server, and is supported natively
by Python. Perfectly scaled for a single-user local app.

**Flask over Electron or desktop frameworks.**
Keeps the stack simple and familiar (Python + browser). Electron would add
significant complexity with no benefit at this stage.

---

## Changelog

### v004 — 2026-05-28

- Phase 4 complete
- SQLite tables added: vendors, expenses
- Flask routes added: GET /api/vendors, POST /api/vendors,
  GET /api/expenses, POST /api/expenses, DELETE /api/expenses/<id>,
  GET /expenses (page)
- expenses.html — new expenses page, same industrial dark aesthetic
- Nav updated on all three pages (Estimates / Invoices / Expenses)
- Log Expense form: vendor selector + inline new vendor, amount, GST paid,
  date, description (optional)
- Expenses list with subtotal, GST paid, and total spent
- Category hardcoded to 'cogs' for v0 — column exists for future picker
- Expense date defaults to today

### v003 — 2026-05-26

- Phase 3 complete
- SQLite table added: payments
- Flask routes added: POST /api/invoices/<id>/payments,
GET /api/invoices/<id>/payments, DELETE /api/payments/<id>
invoices.html — payments card added below invoice form
- Payments section hidden until an existing invoice is loaded
- Log Payment form: amount, date, method (e-transfer/cheque/cash/credit card/bitcoin), notes
- Payment history table with per-row delete
- Balance owing calculated live: grand total minus total paid
- Payment date defaults to today

### v002 — 2026-05-25
- Phase 2 complete
- SQLite tables added: `invoices`, `invoice_line_items`
- Flask routes added: `POST /api/invoices`, `GET /api/invoices/<id>`,
  `POST /api/invoices/from-estimate/<id>`, `GET /invoices` (page)
- All routes namespaced under `/api/` (page routes stay at `/`)
- `invoices.html` — full invoices page, same industrial dark aesthetic
- Nav links added to both pages (Estimates / Invoices)
- "Convert to Invoice" button on estimate form — copies data, redirects
  to invoices page, preserves source estimate untouched
- Source estimate banner on invoice form (↳ converted from EST-xxx)
- Invoice numbers auto-generated server-side (INV-001, INV-002...)
- Issued date defaults to today, due date defaults to +30 days

### v001 — 2026-05-21
- Initial release
- SQLite database with `customers`, `estimates`, `estimate_line_items` tables
- Flask backend with routes: GET `/`, GET+POST `/api/customers`,
  POST `/api/estimates`, GET `/api/estimates/<id>`
- Full estimate UI: customer select + inline new customer form,
  estimate header fields, dynamic line items, live GST totals,
  notes, status selector
- Estimates list with status badges
- Click estimate row to reload into form
- Industrial dark UI aesthetic (IBM Plex Mono/Sans, amber accent)
- Virtual environment established, `requirements.txt` generated

---

## Notes for Claude (AI Context)

If you are a Claude instance starting a new session on this project, read this
section carefully before doing anything.

**What we're building:** A local Flask+SQLite accounting app for a contractor.
Replacing Wave accounting. Single user, runs on Ubuntu at localhost:5000.

**How we work:**
- One task/feature at a time. Stability before new features.
- Code is sectioned with clear comments explaining *why*, not just *what*.
- Owner reads and understands the code — don't just ship black boxes.
- Push to GitHub at end of each sprint, not continuously.
- When something works, confirm it before moving on.
- Be direct. Don't pad. Humour is welcome.

**Current state:** v003 complete. Phase 3 done and tested. All six database
tables exist and are working. Flask app runs. Estimates, invoices, and payments
are fully functional — invoices can be created, saved, reloaded, converted from
estimates, and paid in full or in partial payments.

**Next up:** Phase 4 — Expenses / COGS. Or tackle the cleanup backlog item
(filter accepted estimates from the estimates list) first — owner's call.

**What NOT to do:**
- Don't refactor working code without being asked.
- Don't add features outside the current phase.
- Don't skip schema design discussion before writing new tables.
- Don't store calculated totals in the database.
