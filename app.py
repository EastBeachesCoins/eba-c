from flask import Flask, render_template, request, jsonify
import sqlite3
import os

# =============================================================================
# APP SETUP
# -----------------------------------------------------------------------------
# Creates the Flask application instance. '__name__' tells Flask where to look
# for templates and static files — it resolves to the current file's directory.
# =============================================================================

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "ebaccounting.db")


# =============================================================================
# DATABASE HELPER
# -----------------------------------------------------------------------------
# A small reusable function that opens a database connection.
# 'row_factory' makes rows behave like dictionaries — so you can access
# columns by name (row['customer_name']) instead of index (row[0]).
# We open and close a connection per request; fine for a local single-user app.
# =============================================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# =============================================================================
# ROUTE: Dashboard — GET
# -----------------------------------------------------------------------------
# New root route. Fetches all data needed for the three dashboard sections:
#   1. Operational: open estimates, unpaid invoices, recent payments
#   2. Snapshot cards: invoiced / collected / expenses / GP by period
#   3. Chart: 12-month rolling income + expenses by month
#
# All totals are calculated in SQL — same principle as everywhere else.
# Grand totals on invoices are computed from line items on the fly.
# =============================================================================

@app.route("/")
def dashboard():
    conn = get_db()

    # --- Open estimates (draft or sent — not accepted/declined) ---
    open_estimates = conn.execute("""
        SELECT e.id, e.estimate_number, e.customer_reference, e.status,
               e.created_at, c.name AS customer_name
        FROM estimates e
        JOIN customers c ON e.customer_id = c.id
        WHERE e.status IN ('draft', 'sent')
        ORDER BY e.created_at DESC
    """).fetchall()

    # --- Unpaid invoices with balance owing ---
    # Grand total is calculated from line items. Balance = grand total - paid.
    # 'partial' and 'sent' and 'overdue' all count as unpaid.
    unpaid_invoices = conn.execute("""
        SELECT
            i.id,
            i.invoice_number,
            i.customer_reference,
            i.status,
            i.due_date,
            c.name AS customer_name,
            -- Grand total from line items (subtotal + 5% GST on taxable lines)
            SUM(li.quantity * li.unit_price * (1 + 0.05 * li.taxable)) AS grand_total,
            -- Total collected so far
            COALESCE((
                SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id
            ), 0) AS total_paid
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        JOIN invoice_line_items li ON li.invoice_id = i.id
        WHERE i.status IN ('sent', 'partial', 'overdue')
        GROUP BY i.id
        ORDER BY i.due_date ASC
    """).fetchall()

    # --- Recent payments (last 10) ---
    recent_payments = conn.execute("""
        SELECT
            p.id,
            p.amount,
            p.payment_date,
            p.method,
            i.invoice_number,
            i.id AS invoice_id,
            c.name AS customer_name
        FROM payments p
        JOIN invoices i ON p.invoice_id = i.id
        JOIN customers c ON i.customer_id = c.id
        ORDER BY p.payment_date DESC, p.created_at DESC
        LIMIT 10
    """).fetchall()

    # --- 12-month rolling data for snapshot cards and chart ---
    # strftime('%Y-%m', ...) groups by year-month string (e.g. '2026-05').
    # We pull all 12 months and let the frontend handle period filtering
    # for the This Month / This Quarter / YTD toggle.

    monthly_invoiced = conn.execute("""
        SELECT
            strftime('%Y-%m', i.issued_date) AS month,
            SUM(li.quantity * li.unit_price * (1 + 0.05 * li.taxable)) AS total
        FROM invoices i
        JOIN invoice_line_items li ON li.invoice_id = i.id
        WHERE i.issued_date >= date('now', '-12 months')
        GROUP BY month
        ORDER BY month ASC
    """).fetchall()

    monthly_collected = conn.execute("""
        SELECT
            strftime('%Y-%m', payment_date) AS month,
            SUM(amount) AS total
        FROM payments
        WHERE payment_date >= date('now', '-12 months')
        GROUP BY month
        ORDER BY month ASC
    """).fetchall()

    monthly_expenses = conn.execute("""
        SELECT
            strftime('%Y-%m', expense_date) AS month,
            SUM(amount) AS total
        FROM expenses
        WHERE expense_date >= date('now', '-12 months')
        GROUP BY month
        ORDER BY month ASC
    """).fetchall()

    conn.close()

    return render_template("dashboard.html",
        open_estimates   = [dict(r) for r in open_estimates],
        unpaid_invoices  = [dict(r) for r in unpaid_invoices],
        recent_payments  = [dict(r) for r in recent_payments],
        monthly_invoiced = [dict(r) for r in monthly_invoiced],
        monthly_collected= [dict(r) for r in monthly_collected],
        monthly_expenses = [dict(r) for r in monthly_expenses],
    )

# =============================================================================
# ROUTE: Estimates
# -----------------------------------------------------------------------------
# Fetches all existing estimates (with customer name joined
# in) and passes them to the template for display in the estimates list.
# =============================================================================

@app.route("/estimates")
def index():
    conn = get_db()
    estimates = conn.execute("""
        SELECT e.id, e.estimate_number, e.customer_reference, e.status,
               e.created_at, c.name AS customer_name
        FROM estimates e
        JOIN customers c ON e.customer_id = c.id
        ORDER BY e.created_at DESC
    """).fetchall()
    conn.close()
    return render_template("index.html", estimates=estimates)


# =============================================================================
# ROUTE: Customers — GET all, POST new
# -----------------------------------------------------------------------------
# GET  /customers      → returns all customers as JSON (used to populate
#                        the customer dropdown in the estimate form)
# POST /customers      → creates a new customer from form data, returns
#                        the new customer's id and name as JSON
# =============================================================================

@app.route("/api/customers", methods=["GET", "POST"])
def customers():
    conn = get_db()

    if request.method == "GET":
        rows = conn.execute("SELECT id, name FROM customers ORDER BY name").fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])

    if request.method == "POST":
        data = request.get_json()
        cursor = conn.execute("""
            INSERT INTO customers (name, email, phone, address)
            VALUES (?, ?, ?, ?)
        """, (
            data.get("name"),
            data.get("email"),
            data.get("phone"),
            data.get("address")
        ))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return jsonify({"id": new_id, "name": data.get("name")}), 201


# =============================================================================
# ROUTE: Estimates — POST new
# -----------------------------------------------------------------------------
# Receives the full estimate payload as JSON: estimate fields + line items
# array. Inserts the estimate row first, then loops through line items and
# inserts each one linked to the new estimate's id.
#
# This is wrapped in a try/except so if anything fails mid-save, we return
# a clear error rather than a silent failure or crash.
# =============================================================================

@app.route("/api/estimates", methods=["POST"])
def create_estimate():
    data = request.get_json()
    conn = get_db()

    try:
    # Auto-generate the next estimate number
        count = conn.execute("SELECT COUNT(*) FROM estimates").fetchone()[0]
        estimate_number = f"EST-{str(count + 1).zfill(3)}"

    # Insert the estimate header
        cursor = conn.execute("""
        INSERT INTO estimates
            (customer_id, estimate_number, customer_reference, status, notes)
         VALUES (?, ?, ?, ?, ?)
    """, (
        data.get("customer_id"),
        estimate_number,
        data.get("customer_reference"),
        data.get("status", "draft"),
        data.get("notes")
    ))
        estimate_id = cursor.lastrowid

        # Insert each line item linked to the new estimate
        for item in data.get("line_items", []):
            conn.execute("""
                INSERT INTO estimate_line_items
                    (estimate_id, description, quantity, unit_price, taxable)
                VALUES (?, ?, ?, ?, ?)
            """, (
                estimate_id,
                item.get("description"),
                item.get("quantity"),
                item.get("unit_price"),
                1 if item.get("taxable") else 0
            ))

        conn.commit()
        return jsonify({"id": estimate_id}), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

    finally:
        conn.close()


# =============================================================================
# ROUTE: Single Estimate — GET
# -----------------------------------------------------------------------------
# Fetches one estimate by ID, including all its line items. Used when you
# click an estimate in the list to view or edit it. Returns JSON.
# =============================================================================

@app.route("/api/estimates/<int:estimate_id>", methods=["GET"])
def get_estimate(estimate_id):
    conn = get_db()

    estimate = conn.execute("""
        SELECT e.*, c.name AS customer_name
        FROM estimates e
        JOIN customers c ON e.customer_id = c.id
        WHERE e.id = ?
    """, (estimate_id,)).fetchone()

    if not estimate:
        conn.close()
        return jsonify({"error": "Estimate not found"}), 404

    line_items = conn.execute("""
        SELECT * FROM estimate_line_items WHERE estimate_id = ?
    """, (estimate_id,)).fetchall()

    conn.close()

    return jsonify({
        **dict(estimate),
        "line_items": [dict(i) for i in line_items]
    })

# =============================================================================
# ROUTE: Invoices — POST new
# -----------------------------------------------------------------------------
# Same pattern as create_estimate. Accepts the full invoice payload as JSON:
# header fields + line items array.
#
# 'estimate_id' is optional — only present if this invoice was converted from
# an existing estimate. If creating from scratch it will be None/null.
#
# Invoice number is auto-generated here using the same approach as estimates:
# count existing invoices and zero-pad the next number (INV-001, INV-002...).
# =============================================================================

@app.route("/api/invoices", methods=["POST"])
def create_invoice():
    data = request.get_json()
    conn = get_db()

    try:
        # Auto-generate the next invoice number
        count = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        invoice_number = f"INV-{str(count + 1).zfill(3)}"

        cursor = conn.execute("""
            INSERT INTO invoices
                (customer_id, estimate_id, invoice_number, customer_reference,
                 status, notes, issued_date, due_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("customer_id"),
            data.get("estimate_id"),       # None if created from scratch
            invoice_number,
            data.get("customer_reference"),
            data.get("status", "draft"),
            data.get("notes"),
            data.get("issued_date"),
            data.get("due_date")
        ))
        invoice_id = cursor.lastrowid

        # Insert each line item linked to the new invoice
        for item in data.get("line_items", []):
            conn.execute("""
                INSERT INTO invoice_line_items
                    (invoice_id, description, quantity, unit_price, taxable)
                VALUES (?, ?, ?, ?, ?)
            """, (
                invoice_id,
                item.get("description"),
                item.get("quantity"),
                item.get("unit_price"),
                1 if item.get("taxable") else 0
            ))

        conn.commit()
        return jsonify({"id": invoice_id, "invoice_number": invoice_number}), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

    finally:
        conn.close()


# =============================================================================
# ROUTE: Single Invoice — GET
# -----------------------------------------------------------------------------
# Fetches one invoice by ID with its line items. Same structure as
# get_estimate. Also joins customer name and — if it exists — the linked
# estimate number, useful for displaying "converted from EST-003" in the UI.
# =============================================================================

@app.route("/api/invoices/<int:invoice_id>", methods=["GET"])
def get_invoice(invoice_id):
    conn = get_db()

    invoice = conn.execute("""
        SELECT i.*, c.name AS customer_name, e.estimate_number
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        LEFT JOIN estimates e ON i.estimate_id = e.id
        WHERE i.id = ?
    """, (invoice_id,)).fetchone()

    if not invoice:
        conn.close()
        return jsonify({"error": "Invoice not found"}), 404

    line_items = conn.execute("""
        SELECT * FROM invoice_line_items WHERE invoice_id = ?
    """, (invoice_id,)).fetchall()

    conn.close()

    return jsonify({
        **dict(invoice),
        "line_items": [dict(i) for i in line_items]
    })


# =============================================================================
# ROUTE: Convert Estimate to Invoice — POST
# -----------------------------------------------------------------------------
# Copies an estimate's header fields and line items into new invoice records.
# The estimate is NOT modified — it stays exactly as-is. The invoice gets
# its own independent copy of the line items so it can diverge if scope
# changes after the estimate was accepted.
#
# The frontend will call this with just the estimate_id plus any overrides
# (issued_date, due_date, notes). Everything else is copied from the estimate.
# =============================================================================

@app.route("/api/invoices/from-estimate/<int:estimate_id>", methods=["POST"])
def invoice_from_estimate(estimate_id):
    data = request.get_json()
    conn = get_db()

    try:
        # Fetch the source estimate
        estimate = conn.execute("""
            SELECT * FROM estimates WHERE id = ?
        """, (estimate_id,)).fetchone()

        if not estimate:
            return jsonify({"error": "Estimate not found"}), 404

        # Auto-generate the next invoice number
        count = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        invoice_number = f"INV-{str(count + 1).zfill(3)}"

        # Create the invoice, copying fields from the estimate
        cursor = conn.execute("""
            INSERT INTO invoices
                (customer_id, estimate_id, invoice_number, customer_reference,
                 status, notes, issued_date, due_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            estimate["customer_id"],
            estimate_id,
            invoice_number,
            estimate["customer_reference"],
            "draft",
            data.get("notes", estimate["notes"]),
            data.get("issued_date"),
            data.get("due_date")
        ))
        invoice_id = cursor.lastrowid

        # Copy line items from the estimate — these are now independent rows
        source_items = conn.execute("""
            SELECT * FROM estimate_line_items WHERE estimate_id = ?
        """, (estimate_id,)).fetchall()

        for item in source_items:
            conn.execute("""
                INSERT INTO invoice_line_items
                    (invoice_id, description, quantity, unit_price, taxable)
                VALUES (?, ?, ?, ?, ?)
            """, (
                invoice_id,
                item["description"],
                item["quantity"],
                item["unit_price"],
                item["taxable"]
            ))

        conn.commit()
        return jsonify({"id": invoice_id, "invoice_number": invoice_number}), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

    finally:
        conn.close()

# =============================================================================
# ROUTE: Invoices page
# -----------------------------------------------------------------------------
# Serves the invoices HTML page. Fetches all invoices with customer name
# joined in, same pattern as the index route for estimates.
# =============================================================================

@app.route("/invoices")
def invoices_page():
    conn = get_db()
    invoices = conn.execute("""
        SELECT i.id, i.invoice_number, i.customer_reference, i.status,
               i.issued_date, i.due_date, c.name AS customer_name
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        ORDER BY i.created_at DESC
    """).fetchall()
    conn.close()
    return render_template("invoices.html", invoices=invoices)

# =============================================================================
# PAYMENTS
# -----------------------------------------------------------------------------
# Payments are stored one row per payment in the 'payments' table, linked to
# an invoice by invoice_id. Balance owing is never stored — it's calculated
# as: invoice grand total minus the sum of all payments for that invoice.
# =============================================================================

@app.route('/api/invoices/<int:invoice_id>/payments', methods=['POST'])
def add_payment(invoice_id):
    """Log a new payment against an invoice."""
    data = request.get_json()
    conn = get_db()
    conn.execute("""
        INSERT INTO payments (invoice_id, amount, payment_date, method, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (
        invoice_id,
        data['amount'],
        data['payment_date'],
        data.get('method'),
        data.get('notes')
    ))
    conn.commit()
    return jsonify({'success': True})


@app.route('/api/invoices/<int:invoice_id>/payments', methods=['GET'])
def get_payments(invoice_id):
    """Return all payments for an invoice, plus total paid."""
    conn = get_db()
    rows = conn.execute("""
        SELECT id, amount, payment_date, method, notes
        FROM payments
        WHERE invoice_id = ?
        ORDER BY payment_date ASC
    """, (invoice_id,)).fetchall()

    payments = [dict(r) for r in rows]
    total_paid = sum(p['amount'] for p in payments)

    return jsonify({'payments': payments, 'total_paid': total_paid})


@app.route('/api/payments/<int:payment_id>', methods=['DELETE'])
def delete_payment(payment_id):
    """Delete a single payment by its own ID."""
    conn = get_db()
    conn.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
    conn.commit()
    return jsonify({'success': True})

# =============================================================================
# VENDORS
# -----------------------------------------------------------------------------
# GET  /customers      → returns all customers as JSON (used to populate
#                        the customer dropdown in the estimate form)
# POST /customers      → creates a new customer from form data, returns
#                        the new customer's id and name as JSON
# =============================================================================

@app.route('/api/vendors', methods=['GET'])
def get_vendors():
    # Returns all vendors for dropdowns and future vendor management UI
    conn = get_db()
    vendors = conn.execute('SELECT * FROM vendors ORDER BY name ASC').fetchall()
    conn.close()
    return jsonify([dict(v) for v in vendors])


@app.route('/api/vendors', methods=['POST'])
def create_vendor():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Vendor name is required'}), 400
    conn = get_db()
    cursor = conn.execute(
        'INSERT INTO vendors (name, phone, email, notes) VALUES (?, ?, ?, ?)',
        (name, data.get('phone', ''), data.get('email', ''), data.get('notes', ''))
    )
    conn.commit()
    vendor_id = cursor.lastrowid
    conn.close()
    return jsonify({'id': vendor_id, 'name': name}), 201

# =============================================================================
# ROUTE: Expenses page
# -----------------------------------------------------------------------------
# Serves the expenses HTML page. Fetches all expenses with vendor name
# joined in, same pattern as the index route for estimates.
# =============================================================================

@app.route('/expenses')
def expenses_page():
    return render_template('expenses.html')


# =============================================================================
# EXPENSES
# -----------------------------------------------------------------------------
# Same pattern as create_estimate. Accepts the full expense payload as JSON:
# header fields + line items array.
#
# Expense number is auto-generated here using the same approach as estimates:
# count existing invoices and zero-pad the next number (EXP-001, EXP-002...).
# =============================================================================

@app.route('/api/expenses', methods=['GET'])
def get_expenses():
    # Returns all expenses joined with vendor name for display
    conn = get_db()
    expenses = conn.execute('''
        SELECT e.*, v.name AS vendor_name
        FROM expenses e
        LEFT JOIN vendors v ON e.vendor_id = v.id
        ORDER BY e.expense_date DESC
    ''').fetchall()
    conn.close()
    return jsonify([dict(e) for e in expenses])


@app.route('/api/expenses', methods=['POST'])
def create_expense():
    data = request.get_json()
    # amount and expense_date are the only required fields
    amount = data.get('amount')
    expense_date = data.get('expense_date', '').strip()
    if not amount or not expense_date:
        return jsonify({'error': 'Amount and expense date are required'}), 400
    conn = get_db()
    cursor = conn.execute(
        '''INSERT INTO expenses
           (vendor_id, invoice_id, estimate_id, category, description, amount, gst_paid, expense_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (
            data.get('vendor_id') or None,
            data.get('invoice_id') or None,
            data.get('estimate_id') or None,
            data.get('category', 'cogs'),
            data.get('description', '').strip() or None,
            amount,
            data.get('gst_paid') or None,
            expense_date
        )
    )
    conn.commit()
    expense_id = cursor.lastrowid
    conn.close()
    return jsonify({'id': expense_id}), 201


@app.route('/api/expenses/<int:expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    conn = get_db()
    conn.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
    conn.commit()
    conn.close()
    return jsonify({'deleted': expense_id})

# -------------------------------------------------------------------------
# MARK AS SENT
# Sets sent_at timestamp and updates status to 'sent' on estimates/invoices
# payments just get the timestamp — no status column to update
# -------------------------------------------------------------------------

@app.route('/api/estimates/<int:estimate_id>/send', methods=['POST'])
def send_estimate(estimate_id):
    conn = get_db()
    conn.execute('''
        UPDATE estimates
        SET sent_at = datetime('now'), status = 'sent'
        WHERE id = ?
    ''', (estimate_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/invoices/<int:invoice_id>/send', methods=['POST'])
def send_invoice(invoice_id):
    conn = get_db()
    conn.execute('''
        UPDATE invoices
        SET sent_at = datetime('now'), status = 'sent'
        WHERE id = ?
    ''', (invoice_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/payments/<int:payment_id>/send', methods=['POST'])
def send_payment(payment_id):
    conn = get_db()
    conn.execute('''
        UPDATE payments
        SET sent_at = datetime('now')
        WHERE id = ?
    ''', (payment_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# -------------------------------------------------------------------------
# PRINT VIEWS
# Return standalone HTML pages for printing / saving as PDF
# Each route fetches all data needed for that document type
# -------------------------------------------------------------------------

@app.route('/estimates/<int:estimate_id>/print')
def print_estimate(estimate_id):
    conn = get_db()

    estimate = conn.execute('''
        SELECT e.*, c.name as customer_name, c.email as customer_email,
               c.phone as customer_phone, c.address as customer_address
        FROM estimates e
        JOIN customers c ON e.customer_id = c.id
        WHERE e.id = ?
    ''', (estimate_id,)).fetchone()

    line_items = conn.execute('''
        SELECT * FROM estimate_line_items WHERE estimate_id = ?
    ''', (estimate_id,)).fetchall()

    conn.close()

    if not estimate:
        return "Estimate not found", 404

    return render_template('print_estimate.html',
                           estimate=estimate,
                           line_items=line_items)


@app.route('/invoices/<int:invoice_id>/print')
def print_invoice(invoice_id):
    conn = get_db()

    invoice = conn.execute('''
        SELECT i.*, c.name as customer_name, c.email as customer_email,
               c.phone as customer_phone, c.address as customer_address
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        WHERE i.id = ?
    ''', (invoice_id,)).fetchone()

    line_items = conn.execute('''
        SELECT * FROM invoice_line_items WHERE invoice_id = ?
    ''', (invoice_id,)).fetchall()

    payments = conn.execute('''
        SELECT * FROM payments WHERE invoice_id = ? ORDER BY payment_date ASC
    ''', (invoice_id,)).fetchall()

    conn.close()

    if not invoice:
        return "Invoice not found", 404

    return render_template('print_invoice.html',
                           invoice=invoice,
                           line_items=line_items,
                           payments=payments)


@app.route('/invoices/<int:invoice_id>/receipt')
def print_receipt(invoice_id):
    conn = get_db()

    invoice = conn.execute('''
        SELECT i.*, c.name as customer_name, c.email as customer_email,
               c.phone as customer_phone, c.address as customer_address
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        WHERE i.id = ?
    ''', (invoice_id,)).fetchone()

    line_items = conn.execute('''
        SELECT * FROM invoice_line_items WHERE invoice_id = ?
    ''', (invoice_id,)).fetchall()

    payments = conn.execute('''
        SELECT * FROM payments WHERE invoice_id = ? ORDER BY payment_date ASC
    ''', (invoice_id,)).fetchall()

    conn.close()

    if not invoice:
        return "Invoice not found", 404

    # Receipt is only meaningful if at least one payment exists
    if not payments:
        return "No payments recorded for this invoice", 400

    return render_template('print_receipt.html',
                           invoice=invoice,
                           line_items=line_items,
                           payments=payments)


# =============================================================================
# RUN
# -----------------------------------------------------------------------------
# 'debug=True' means Flask will auto-reload when you save changes to this file
# — no need to restart the server manually during development.
# Remove or set to False before any kind of deployment (not relevant yet).
# =============================================================================

if __name__ == "__main__":
    app.run(debug=True)