# EBAccounting — Project Documentation
> Last updated: 2026-05-21
> Version: v001

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
│   └── index.html          # All frontend: HTML, CSS, JavaScript
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

## Phased Roadmap

| Phase | Scope                              | Status      |
|-------|------------------------------------|-------------|
| 1     | Customers, Estimates, Line Items   | ✅ Complete  |
| 2     | Invoices (convert from estimates)  | Planned     |
| 3     | Payments incl. partial payments    | Planned     |
| 4     | Expenses / COGS                    | Planned     |
| 5     | Dashboard (gross profit, due, etc) | Planned     |

### Phase 2 Design Note
Invoices will have their own table (`invoices`, `invoice_line_items`) with an
optional `estimate_id` foreign key linking back to the source estimate.
Converting an estimate to an invoice **copies** the data — it does not rename
or delete the estimate. This preserves the original record and allows the
invoice to diverge if scope changed.

### Phase 3 Design Note
Payments will support partial payments — a separate `payments` table linked
to `invoices` by `invoice_id`, with amount and date per payment. Balance
owing is calculated dynamically from invoice total minus sum of payments.

---

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

**SQLite over LibreOffice or other options.**
SQLite is a single portable file, requires no server, and is supported natively
by Python. Perfectly scaled for a single-user local app.

**Flask over Electron or desktop frameworks.**
Keeps the stack simple and familiar (Python + browser). Electron would add
significant complexity with no benefit at this stage.

---

## Changelog

### v001 — 2026-05-21
- Initial release
- SQLite database with `customers`, `estimates`, `estimate_line_items` tables
- Flask backend with routes: GET `/`, GET+POST `/customers`,
  POST `/estimates`, GET `/estimates/<id>`
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

**Current state:** v001 complete. Phase 1 done and tested. All three database
tables exist and are working. Flask app runs. UI is functional — customers and
estimates can be created, saved, and reloaded.

**Next up:** Phase 2 — invoices. Before starting, review the Phase 2 design
note above and confirm the schema approach with the owner.

**What NOT to do:**
- Don't refactor working code without being asked.
- Don't add features outside the current phase.
- Don't skip schema design discussion before writing new tables.
- Don't store calculated totals in the database.
