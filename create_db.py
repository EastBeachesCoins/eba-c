import sqlite3
import os

# =============================================================================
# DATABASE CONNECTION
# -----------------------------------------------------------------------------
# Looks for (or creates) the database file in the same folder as this script.
# 'os.path' builds the file path in a way that works regardless of where
# you run the script from. The file 'ebaccounting.db' is your entire database
# — one file, fully portable, no server needed.
# =============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "ebaccounting.db")

def get_connection():
    """Returns a connection to the database."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # Enforce relationships between tables
    return conn


# =============================================================================
# TABLE: customers
# -----------------------------------------------------------------------------
# Stores reusable customer records. A customer is created once and can be
# linked to many estimates over time. 'INTEGER PRIMARY KEY' auto-increments,
# meaning SQLite assigns a unique ID for each new customer automatically.
# =============================================================================

CREATE_CUSTOMERS = """
CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    email       TEXT,
    phone       TEXT,
    address     TEXT,
    created_at  TEXT    DEFAULT (datetime('now'))
);
"""


# =============================================================================
# TABLE: estimates
# -----------------------------------------------------------------------------
# One row per estimate. 'customer_id' is a foreign key — it links this estimate
# to a specific customer in the customers table. If you try to link to a
# customer that doesn't exist, SQLite will reject it (because of PRAGMA above).
#
# 'status' tracks where the estimate is in its lifecycle.
# 'estimate_number' is your human-readable internal reference (e.g. EST-001).
# 'customer_reference' is their identifier — PO number, WO number, address, etc.
# =============================================================================

CREATE_ESTIMATES = """
CREATE TABLE IF NOT EXISTS estimates (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id         INTEGER NOT NULL REFERENCES customers(id),
    estimate_number     TEXT    NOT NULL UNIQUE,
    customer_reference  TEXT,
    status              TEXT    NOT NULL DEFAULT 'draft',
    notes               TEXT,
    created_at          TEXT    DEFAULT (datetime('now')),
    updated_at          TEXT    DEFAULT (datetime('now')),
    sent_at             TEXT
);
"""


# =============================================================================
# TABLE: estimate_line_items
# -----------------------------------------------------------------------------
# Each line on an estimate is its own row here. This is the correct approach —
# it keeps the data flexible (any number of lines per estimate) and lets us
# calculate totals dynamically rather than storing numbers that could go stale.
#
# 'taxable' is 0 (no GST) or 1 (apply GST). SQLite has no boolean type;
# integers 0 and 1 are the standard stand-in.
#
# Totals (subtotal, tax, grand total) are NOT stored here — the app calculates
# them from these rows every time they're needed.
# =============================================================================

CREATE_ESTIMATE_LINE_ITEMS = """
CREATE TABLE IF NOT EXISTS estimate_line_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    estimate_id INTEGER NOT NULL REFERENCES estimates(id) ON DELETE CASCADE,
    description TEXT    NOT NULL,
    quantity    REAL    NOT NULL DEFAULT 1,
    unit_price  REAL    NOT NULL DEFAULT 0.0,
    taxable     INTEGER NOT NULL DEFAULT 0
);
"""

# 'ON DELETE CASCADE' means: if an estimate is deleted, its line items are
# automatically deleted too. No orphaned rows left behind.


# =============================================================================
# TABLE: invoices
# -----------------------------------------------------------------------------
# One row per invoice. Works like estimates, but 'estimate_id' is optional —
# it's only set if this invoice was converted from an existing estimate.
# If created from scratch, it stays NULL.
#
# 'issued_date' is when the invoice goes out. 'due_date' defaults to 30 days
# out but is set manually — the default is just a convenience, not enforced.
#
# Status lifecycle: draft → sent → partial → paid (or overdue at any point).
# =============================================================================

CREATE_INVOICES = """
CREATE TABLE IF NOT EXISTS invoices (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id         INTEGER NOT NULL REFERENCES customers(id),
    estimate_id         INTEGER REFERENCES estimates(id),
    invoice_number      TEXT    NOT NULL UNIQUE,
    customer_reference  TEXT,
    status              TEXT    NOT NULL DEFAULT 'draft',
    notes               TEXT,
    issued_date         TEXT,
    due_date            TEXT,
    created_at          TEXT    DEFAULT (datetime('now')),
    updated_at          TEXT    DEFAULT (datetime('now')),
    sent_at             TEXT
);
"""


# =============================================================================
# TABLE: invoice_line_items
# -----------------------------------------------------------------------------
# Identical structure to estimate_line_items — same logic applies.
# Totals are never stored, always calculated dynamically.
#
# When converting an estimate to an invoice, these rows are copied from
# estimate_line_items. After that they're independent — changes here
# don't affect the original estimate.
# =============================================================================

CREATE_INVOICE_LINE_ITEMS = """
CREATE TABLE IF NOT EXISTS invoice_line_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id  INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description TEXT    NOT NULL,
    quantity    REAL    NOT NULL DEFAULT 1,
    unit_price  REAL    NOT NULL DEFAULT 0.0,
    taxable     INTEGER NOT NULL DEFAULT 0
);
"""

# =============================================================================
# TABLE: payments
# -----------------------------------------------------------------------------
# One row per payment received against an invoice. Supports partial payments —
# a single invoice can have multiple payment rows over time.
#
# Balance owing is NOT stored here. It's calculated at query time as:
#   invoice grand total  −  SUM(payments.amount) for that invoice_id
#
# 'method' is free-form but a known list is suggested in the UI.
# 'notes' is optional — useful for logging things like "post-dated" or
# "deposit only" without needing a dedicated column for every edge case.
#
# ON DELETE CASCADE: if an invoice is deleted, its payment records go too.
# =============================================================================
 
CREATE_PAYMENTS = """
CREATE TABLE IF NOT EXISTS payments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id      INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    amount          REAL    NOT NULL,
    payment_date    TEXT    NOT NULL,
    method          TEXT,
    notes           TEXT,
    created_at      TEXT    DEFAULT (datetime('now')),
    sent_at         TEXT
);
"""
# Accepted values for 'method' (enforced in the UI, not the DB):
# cheque | e-transfer | cash | credit card | bitcoin

# --- Vendors ---
    # Reusable vendor records. Created once, referenced by expenses.
    # vendor_id on expenses is nullable so expenses can be logged without a vendor record.
CREATE_VENDORS = """
CREATE TABLE IF NOT EXISTS vendors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    phone       TEXT,
    email       TEXT,
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);
"""

    # --- Expenses ---
    # One row per expense. Cash-basis: recorded when money leaves.
    # vendor_id, invoice_id, estimate_id are all nullable FKs — for future job costing and AP workflows.
    # category defaults to 'cogs' for v0 — full category picker comes in a later sprint.
    # gst_paid is nullable — just a number you type in, no rate logic yet.
    # description is optional — vendor name carries enough context for now.
CREATE_EXPENSES = """
CREATE TABLE IF NOT EXISTS expenses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_id    INTEGER REFERENCES vendors(id),
    invoice_id   INTEGER REFERENCES invoices(id),
    estimate_id  INTEGER REFERENCES estimates(id),
    category     TEXT DEFAULT 'cogs',
    description  TEXT,
    amount       REAL NOT NULL,
    gst_paid     REAL,
    expense_date TEXT NOT NULL,
    created_at   TEXT DEFAULT (datetime('now'))
);
"""


# =============================================================================
# MAIN — CREATE ALL TABLES
# -----------------------------------------------------------------------------
# This block runs when you execute the file directly ('python create_db.py').
# It connects to the database, runs each CREATE TABLE statement in order,
# and confirms success. Safe to run more than once — 'IF NOT EXISTS' means
# it won't overwrite tables that are already there.
# =============================================================================

if __name__ == "__main__":
    conn = get_connection()
    cursor = conn.cursor()

    print(f"Connecting to database at: {DB_PATH}")

    cursor.execute(CREATE_CUSTOMERS)
    print("✓ Table 'customers' ready")

    cursor.execute(CREATE_ESTIMATES)
    print("✓ Table 'estimates' ready")

    cursor.execute(CREATE_ESTIMATE_LINE_ITEMS)
    print("✓ Table 'estimate_line_items' ready")

    cursor.execute(CREATE_INVOICES)
    print("✓ Table 'invoices' ready")

    cursor.execute(CREATE_INVOICE_LINE_ITEMS)
    print("✓ Table 'invoice_line_items' ready")

    cursor.execute(CREATE_PAYMENTS)
    print("✓ Table 'payments' ready")

    cursor.execute(CREATE_VENDORS)
    print("✓ Table 'vendors' ready")

    cursor.execute(CREATE_EXPENSES)
    print("✓ Table 'expenses' ready")


    conn.commit()
    conn.close()

    print("\nDatabase setup complete. You're ready to build.")