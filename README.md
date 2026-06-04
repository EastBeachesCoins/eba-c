# EBAccounting

A local accounting web app for contractors. Handles estimates, invoices,
payments, expenses, and a gross profit dashboard. Built as a self-hosted
replacement for Wave accounting — no subscription, no cloud, no BS.

---

## What it does

- **Estimates** — create and send estimates to customers, track status
- **Invoices** — convert estimates to invoices or create from scratch
- **Payments** — log full or partial payments, print receipts
- **Expenses / COGS** — track what you spend, with GST paid
- **Dashboard** — invoiced, collected, expenses, and gross profit by month

All data lives in a single SQLite file on your machine. Nothing leaves your
computer.

---

## Requirements

- Python 3.10 or newer
- A terminal
- A browser

That's it. No database server, no Docker, no cloud account.

---

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/EastBeachesCoins/eba-c.git
cd eba-c
```

**2. Create a virtual environment**
```bash
python -m venv venv
source venv/bin/activate
```
> On Windows: `venv\Scripts\activate`

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Create the database**
```bash
python create_db.py
```
This creates `ebaccounting.db` in the project folder. Run it once — it's safe
to re-run if needed (uses `CREATE TABLE IF NOT EXISTS` throughout).

**5. Start the app**
```bash
python app.py
```

**6. Open your browser**
```
http://127.0.0.1:5000
```

---

## Project structure

```
eba-c/
├── templates/
│   ├── dashboard.html        # Dashboard
│   ├── index.html            # Estimates
│   ├── invoices.html         # Invoices
│   ├── expenses.html         # Expenses
│   ├── print_estimate.html   # Print / PDF view
│   ├── print_invoice.html    # Print / PDF view
│   └── print_receipt.html    # Payment receipt view
├── static/
│   └── logo.png              # Your logo (swap this out)
├── app.py                    # Flask backend — all routes
├── create_db.py              # Run once to set up the database
├── requirements.txt          # Python dependencies
└── ebaccounting.db           # SQLite database (created on first run)
```

---

## Notes

- The database file (`ebaccounting.db`) is excluded from git. Back it up
  manually or set up your own backup — it's just a file, copy it anywhere.
- To use your own logo on print views, replace `static/logo.png`.
- GST is hardcoded at 5% (Canadian). A configurable tax rates table is
  planned for a future version.
- This app is single-user and local only. There is no login system.

---

## Tech stack

| Layer    | Choice          |
|----------|-----------------|
| Backend  | Python + Flask  |
| Database | SQLite          |
| Frontend | HTML + CSS + JS |
