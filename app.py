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
# ROUTE: Home
# -----------------------------------------------------------------------------
# The root URL '/'. Fetches all existing estimates (with customer name joined
# in) and passes them to the template for display in the estimates list.
# =============================================================================

@app.route("/")
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

@app.route("/customers", methods=["GET", "POST"])
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

@app.route("/estimates", methods=["POST"])
def create_estimate():
    data = request.get_json()
    conn = get_db()

    try:
        # Insert the estimate header
        cursor = conn.execute("""
            INSERT INTO estimates
                (customer_id, estimate_number, customer_reference, status, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data.get("customer_id"),
            data.get("estimate_number"),
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

@app.route("/estimates/<int:estimate_id>", methods=["GET"])
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
# RUN
# -----------------------------------------------------------------------------
# 'debug=True' means Flask will auto-reload when you save changes to this file
# — no need to restart the server manually during development.
# Remove or set to False before any kind of deployment (not relevant yet).
# =============================================================================

if __name__ == "__main__":
    app.run(debug=True)