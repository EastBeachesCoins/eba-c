# EBAccounting — Project Documentation
> Last updated: 2026-06-02
> Version: v005

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
│   ├── dashboard.html      # Dashboard page
│   ├── index.html          # Estimates page: list + form
│   ├── invoices.html       # Invoices page: list + form
│   ├── expenses.html       # Expenses page: list + form
│   ├── print_estimate.html    # Print/PDF view for estimates
│   ├── print_invoice.html     # Print/PDF view for invoices
│   └── print_receipt.html     # Print/PDF view for payment receipts
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

## Database Schema

Schema is maintained in `create_db.py` — that file is the source of truth.
Each table has inline comments explaining the design decisions.
The phased design notes below cover the *why* behind each phase's approach.

---

## Phased Roadmap

| Phase | Scope                              | Status      |
|-------|------------------------------------|-------------|
| 1     | Customers, Estimates, Line Items   | ✅ Complete |
| 2     | Invoices (convert from estimates)  | ✅ Complete |
| 3     | Payments incl. partial payments    | ✅ Complete |
| 4     | Expenses / COGS                    | ✅ Complete |
| 5     | Print estimates, invoices, receipts| ✅ Complete |
| 6     | Dashboard (gross profit, due, etc) | ✅ Complete |

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

### Phase 5 Design Note
Print templates are standalone HTML files rendered by Flask and served at
dedicated routes (/estimates/<id>/print, /invoices/<id>/print,
/invoices/<id>/receipt). They open in a new browser tab and the user saves
as PDF from there — no server-side PDF generation needed.
sent_at is a nullable TEXT column on estimates, invoices, and payments.
It is stamped via a POST to /api/<type>/<id>/send when the user clicks
"Mark as Sent" on the print view. Single timestamp per record — last sent
semantics. A full send log is deferred to the cloud link sprint.
The receipt template receives line_items from the route even though it doesn't
display them — they are needed to calculate the invoice grand total so balance
owing can be shown correctly.
Cloud link sharing (generate a shareable URL for customers) is deferred to a
future sprint. The sent_at column is forward-compatible with that feature.

### Phase 6 Design Note
The dashboard is a pure read layer — no new writes, no schema changes except
the jobs stub. All financial totals are calculated from source records at
query time, consistent with the no-stored-totals principle throughout.

Cash basis is used throughout: Collected (payments) and Disbursed (expenses).
The data model already supports an accrual view (Invoiced − Expenses) as a
future toggle — it's a different SQL query against the same tables, not a
schema change.

The jobs table is stubbed with FK relationships only. Column additions
(revenue, COGS, GP per job, line items) are deferred to a dedicated
job-costing sprint. FKs are established now because retrofitting
relationships later requires migrations; adding columns does not.

---

## V0 Cleanup Backlog
Items deferred from active sprints. To be addressed in a dedicated cleanup
sprint. Ranked by ease + importance:

6. **Import Wave data** — One-time migration script from Wave CSVs. Defer
   to its own sprint immediately before go-live.

---

## Future versions 
Items deferred to later version (v1,v2,etc) to keep v0 mission-focused

- Taxes: When the time comes, the clean solution is a tax_rates table — name, rate, applies_to (sales/purchases/both), jurisdiction, whatever. Then expenses and invoices reference it by ID. That's a self-contained sprint that doesn't touch anything already built — just adds the table, updates the UI dropdowns, done.
- Accounts Payable: To support that properly later you'd want something like a bills table (the obligation) and a bill_payments table (the cash out) — same pattern as invoices/payments but on the expense side. The current expenses table is cash-only by nature.
- Expense line items: We'll need a migration from 
- Right before going live: grab Wave CSVs to secure historical data and see if we can port it to our new app without too much yak shaving. Otherwise archive and start with fresh data.
- email link for estimates, invoices, receipts: A dead-simple "public facing" micro-server — a tiny separate Flask app you deploy once to something like Railway or Fly.io that just serves read-only estimate/invoice HTML. Your local app pushes the rendered HTML to it via an API call.
- See v0005 chat in Claude for context on these decisions.
- Job costing: built off the stub jobs table we created in our schema
- create one-push encrypted cloud storage as data backup

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

### v007 — 2026-06-04

Cleanup sprint — items 1–5 from v0 backlog

- Header/nav alignment fixed across all four pages (dashboard, expenses were
  inconsistent with estimates and invoices)
- CSS dialect on expenses.html aligned to app standard (--amber → --accent,
  --amber-dim → --accent-dim, text/muted colour values unified)
- Estimates list now hides declined estimates by default; "Show All" / "Hide
  Closed" toggle to reveal. Accepted estimates remain visible (still need
  attention — deposit pending, job not started, etc.)
- Save estimate and save invoice now PATCH existing records instead of POSTing
  new ones — estimate/invoice numbers no longer change on update
- Edit Customer — inline edit form on both estimates and invoices pages;
  appears when a customer is selected, pre-filled with current data, saves
  via PUT /api/customers/<id>

Flask routes added:
  GET  /api/customers/<id> — returns full customer record for edit form
  PUT  /api/customers/<id> — updates customer name, email, phone, address
  PATCH /api/estimates/<id> — updates estimate header + replaces line items
  PATCH /api/invoices/<id>  — updates invoice header + replaces line items

### v006 — 2026-06-04

Phase 6 complete — Dashboard

- `jobs` table stubbed in `create_db.py` (schema + FKs only, no UI)
  Columns: id, customer_id, estimate_id, invoice_id, name, status, notes, created_at
- `/` route reassigned to dashboard; estimates moved to `/estimates`
- `dashboard.html` added — industrial dark aesthetic, Chart.js (CDN) for chart
- Nav updated on all pages to include Dashboard link

Dashboard sections:
  Financial Snapshot — Invoiced / Collected / Expenses / Gross Profit cards
  with This Month / This Quarter / YTD toggle (JS, no server round-trip)
  Needs Attention — open estimates + outstanding invoices (clickable rows),
  recent payments feed (last 10)
  12-Month Overview — rolling bar+line chart; collected and expenses as bars,
  gross profit as amber line overlay

Flask routes added:
  GET / — renders dashboard.html with all data pre-baked (no separate API calls)

Data notes:
  All financial totals calculated from source records — never stored
  Cash basis throughout: collected in, disbursed out
  Invoice grand totals calculated inline from invoice_line_items in SQL
  Draft invoices excluded from outstanding panel by design

### v005 — 2026-06-02

Phase 5 complete — Print / Send to Customer
Schema migration: sent_at TEXT column added to estimates, invoices, payments
Flask routes added:

POST /api/estimates/<id>/send — stamps sent_at, sets status to 'sent'
POST /api/invoices/<id>/send — stamps sent_at, sets status to 'sent'
POST /api/payments/<id>/send — stamps sent_at on payment row
GET /estimates/<id>/print — renders print_estimate.html
GET /invoices/<id>/print — renders print_invoice.html
GET /invoices/<id>/receipt — renders print_receipt.html


Three print templates added (Libre Baskerville + Source Sans 3, light theme):

print_estimate.html — logo, parties, line items, GST, totals, notes,
signature lines, 30-day validity footer
print_invoice.html — logo, parties, dates, line items, balance owing,
payment status badge, no signature line
print_receipt.html — logo, parties, invoice summary bar, payment history
table, balance owing, "Paid in Full" stamp when balance is zero


static/ folder added with logo.png (East Beaches Floor & Tile)
Print / PDF button added to estimate form (visible when estimate loaded)
Print / PDF button added to invoice form (visible when invoice loaded)
Print / PDF button added per row in payment history (opens receipt)
All print views hide screen controls on print via @media print

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
