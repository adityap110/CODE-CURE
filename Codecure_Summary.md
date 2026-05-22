# CodeCure Project Summary

## 1. Project Structure
```text
.
├── static/
│   ├── manifest.json
│   └── service-worker.js
├── templates/
│   ├── index.html
│   └── login.html
├── .env
├── .env.example
├── .gcloudignore
├── .gitignore
├── app.py
├── app.yaml
├── codecure.db
├── config.py
├── models.py
├── render.yaml
├── requirement.txt
├── requirements.txt
├── test_models.py
├── update_app.py
├── utils.py
└── wsgi.py
```

## 2. Backend Implementation

### `c:\Users\adity\OneDrive\Desktop\Codecure\app.py`
```python
"""
CodeCure — AI-Powered Smart Pharmacy Management System
Main Application (Modular Refactor)
"""
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
import os, json, traceback
from datetime import datetime, date, timedelta

from config import Config
from models import get_db, init_db, log_activity, record_sale
from utils import (
    sanitize, sanitize_dict, validate_medicine_data,
    safe_int, safe_float, login_required, role_required,
    days_until_expiry, get_expiry_status
)

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# ─── DEMO USERS (will migrate to DB users table later) ────────────────────────

USERS = {
    "admin":      {"password": generate_password_hash("1234"), "role": "Admin"},
    "pharmacist": {"password": generate_password_hash("1234"), "role": "Pharmacist"},
    "cashier":    {"password": generate_password_hash("1234"), "role": "Cashier"},
    "doctor":     {"password": generate_password_hash("1234"), "role": "Doctor"},
}

# ─── ERROR HANDLER ─────────────────────────────────────────────────────────────

@app.errorhandler(Exception)
def handle_exception(e):
    traceback.print_exc()
    if request.path.startswith("/api/"):
        return jsonify({"error": "Internal server error"}), 500
    return f"<pre>{traceback.format_exc()}</pre>", 500

# ─── AUTH ROUTES ───────────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        u = request.form.get("username", "").strip().lower()
        p = request.form.get("password", "").strip()
        if u in USERS and check_password_hash(USERS[u]["password"], p):
            session["user"] = u
            session["role"] = USERS[u]["role"]
            log_activity("Login", f"{u} logged in", u)
            return redirect(url_for("dashboard"))
        error = "Invalid credentials"
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    user = session.pop("user", "unknown")
    session.pop("role", None)
    session.pop("cart", None)
    log_activity("Logout", f"{user} logged out", user)
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", user=session["user"], role=session["role"])

# ─── STATS API ─────────────────────────────────────────────────────────────────

@app.route("/api/stats")
@login_required
def api_stats():
    conn = get_db()
    today = date.today().isoformat()
    total   = conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]
    ok      = conn.execute("SELECT COUNT(*) FROM medicines WHERE quantity >= min_stock AND (expiry_date IS NULL OR expiry_date > ?)", (today,)).fetchone()[0]
    low     = conn.execute("SELECT COUNT(*) FROM medicines WHERE quantity < min_stock AND (expiry_date IS NULL OR expiry_date > ?)", (today,)).fetchone()[0]
    expired = conn.execute("SELECT COUNT(*) FROM medicines WHERE expiry_date <= ?", (today,)).fetchone()[0]
    conn.close()
    return jsonify({"total": total, "ok": ok, "low": low, "expired": expired})

# ─── MEDICINES CRUD ────────────────────────────────────────────────────────────

@app.route("/api/medicines", methods=["GET"])
@login_required
def api_medicines():
    filter_type = request.args.get("filter", "all")
    search = request.args.get("search", "").strip()
    sort_col = request.args.get("sort", "name")
    sort_dir = request.args.get("dir", "asc")
    page = safe_int(request.args.get("page", 1), default=1, minimum=1)
    per_page = safe_int(request.args.get("per_page", 50), default=50, minimum=1, maximum=200)
    today = date.today().isoformat()

    valid_cols = ["name", "category", "quantity", "expiry_date", "supplier", "price"]
    if sort_col not in valid_cols:
        sort_col = "name"
    sort_dir = "DESC" if sort_dir == "desc" else "ASC"

    conn = get_db()
    base_where = ""
    params = []
    if search:
        base_where = " AND (LOWER(name) LIKE ? OR LOWER(category) LIKE ? OR LOWER(supplier) LIKE ?)"
        search_param = f"%{search.lower()}%"
        params = [search_param, search_param, search_param]

    if filter_type == "low":
        where = "WHERE quantity < min_stock" + base_where
    elif filter_type == "expiring":
        where = "WHERE expiry_date BETWEEN ? AND '2025-12-31'" + base_where
        params = [today] + params
    elif filter_type == "expired":
        where = "WHERE expiry_date <= ?" + base_where
        params = [today] + params
    else:
        where = "WHERE 1=1" + base_where

    total = conn.execute(f"SELECT COUNT(*) FROM medicines {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM medicines {where} ORDER BY {sort_col} {sort_dir} LIMIT ? OFFSET ?",
        params + [per_page, (page-1)*per_page]
    ).fetchall()
    conn.close()
    return jsonify({
        "data": [dict(r) for r in rows],
        "total": total, "page": page, "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    })

@app.route("/api/medicines", methods=["POST"])
@role_required("Admin", "Pharmacist")
def api_add_medicine():
    data = request.json or {}
    clean = sanitize_dict(data, ["name", "category", "supplier", "expiry_date"])
    errors = validate_medicine_data({**data, **clean})
    if errors:
        return jsonify({"error": ", ".join(errors)}), 400
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO medicines (name,category,quantity,min_stock,expiry_date,supplier,price) VALUES (?,?,?,?,?,?,?)",
            (clean["name"], clean.get("category",""), safe_int(data.get("quantity",0)),
             safe_int(data.get("min_stock",10)), clean.get("expiry_date",""),
             clean.get("supplier",""), safe_float(data.get("price",0)))
        )
        conn.commit()
        log_activity("Add Medicine", clean["name"], session["user"])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

@app.route("/api/medicines/<int:mid>", methods=["PUT"])
@role_required("Admin", "Pharmacist")
def api_update_medicine(mid):
    data = request.json or {}
    clean = sanitize_dict(data, ["name", "category", "supplier", "expiry_date"])
    errors = validate_medicine_data({**data, **clean})
    if errors:
        return jsonify({"error": ", ".join(errors)}), 400
    conn = get_db()
    try:
        conn.execute(
            "UPDATE medicines SET name=?,category=?,quantity=?,min_stock=?,expiry_date=?,supplier=?,price=? WHERE id=?",
            (clean["name"], clean.get("category",""), safe_int(data.get("quantity",0)),
             safe_int(data.get("min_stock",10)), clean.get("expiry_date",""),
             clean.get("supplier",""), safe_float(data.get("price",0)), mid)
        )
        conn.commit()
        log_activity("Edit Medicine", f"ID {mid} updated", session["user"])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

@app.route("/api/medicines/<int:mid>", methods=["DELETE"])
@role_required("Admin")
def api_delete_medicine(mid):
    conn = get_db()
    row = conn.execute("SELECT name FROM medicines WHERE id=?", (mid,)).fetchone()
    conn.execute("DELETE FROM medicines WHERE id=?", (mid,))
    conn.commit()
    conn.close()
    log_activity("Delete Medicine", row["name"] if row else f"ID {mid}", session["user"])
    return jsonify({"success": True})

# ─── ALERTS ────────────────────────────────────────────────────────────────────

@app.route("/api/alerts")
@login_required
def api_alerts():
    today = date.today().isoformat()
    warn_date = (date.today() + timedelta(days=7)).isoformat()
    conn = get_db()
    low     = conn.execute("SELECT id,name,quantity,min_stock FROM medicines WHERE quantity < min_stock").fetchall()
    expired = conn.execute("SELECT id,name,expiry_date FROM medicines WHERE expiry_date <= ?", (today,)).fetchall()
    expiring = conn.execute("SELECT id,name,expiry_date FROM medicines WHERE expiry_date > ? AND expiry_date <= ?", (today, warn_date)).fetchall()
    out     = conn.execute("SELECT id,name FROM medicines WHERE quantity = 0").fetchall()
    conn.close()
    alerts = []
    for r in out:
        alerts.append({"type":"out","severity":"critical","name":r["name"],"detail":"Out of stock!"})
    for r in expired:
        alerts.append({"type":"expired","severity":"critical","name":r["name"],"detail":f"Expired on {r['expiry_date']}"})
    for r in low:
        if r["quantity"] > 0:
            alerts.append({"type":"low","severity":"warning","name":r["name"],"detail":f"Only {r['quantity']} left (min {r['min_stock']})"})
    for r in expiring:
        d = days_until_expiry(r["expiry_date"])
        alerts.append({"type":"expiring","severity":"warning","name":r["name"],"detail":f"Expires in {d} day(s)"})
    return jsonify(alerts)

@app.route("/api/activity")
@login_required
def api_activity():
    conn = get_db()
    rows = conn.execute("SELECT * FROM activity ORDER BY id DESC LIMIT 20").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

# ─── BILLING & POS ────────────────────────────────────────────────────────────

@app.route("/api/cart", methods=["GET"])
@login_required
def api_cart_get():
    cart = session.get("cart", [])
    conn = get_db()
    cart_items = []
    for item in cart:
        m = conn.execute("SELECT id, name, price, quantity FROM medicines WHERE id=?", (item["id"],)).fetchone()
        if m and m["quantity"] >= item["qty"]:
            cart_items.append({
                "id": m["id"], "name": m["name"], "price": m["price"],
                "qty": item["qty"], "subtotal": m["price"] * item["qty"]
            })
    conn.close()
    total = sum(i["subtotal"] for i in cart_items)
    return jsonify({"items": cart_items, "total": total})

@app.route("/api/cart", methods=["POST"])
@role_required("Admin", "Pharmacist", "Cashier")
def api_cart_add():
    data = request.json or {}
    mid = data.get("id")
    qty = safe_int(data.get("qty", 1), default=1, minimum=1)
    if not mid:
        return jsonify({"error": "Invalid item"}), 400
    conn = get_db()
    m = conn.execute("SELECT id, name, price, quantity FROM medicines WHERE id=?", (mid,)).fetchone()
    if not m:
        conn.close()
        return jsonify({"error": "Medicine not found"}), 404
    if m["quantity"] < qty:
        conn.close()
        return jsonify({"error": f"Insufficient stock. Only {m['quantity']} available."}), 400
    conn.close()
    cart = session.get("cart", [])
    for item in cart:
        if item["id"] == mid:
            item["qty"] = min(item["qty"] + qty, m["quantity"])
            break
    else:
        cart.append({"id": mid, "qty": qty})
    session["cart"] = cart
    return jsonify({"success": True, "cart_count": len(cart)})

@app.route("/api/cart/<int:mid>", methods=["DELETE"])
@login_required
def api_cart_remove(mid):
    cart = session.get("cart", [])
    cart = [i for i in cart if i["id"] != mid]
    session["cart"] = cart
    return jsonify({"success": True})

@app.route("/api/cart/clear", methods=["POST"])
@login_required
def api_cart_clear():
    session["cart"] = []
    return jsonify({"success": True})

@app.route("/api/checkout", methods=["POST"])
@role_required("Admin", "Pharmacist", "Cashier")
def api_checkout():
    cart = session.get("cart", [])
    if not cart:
        return jsonify({"error": "Cart is empty"}), 400
    conn = get_db()
    user = session["user"]
    invoice_items = []
    try:
        for item in cart:
            mid, qty = item["id"], item["qty"]
            m = conn.execute("SELECT name, price, quantity FROM medicines WHERE id=?", (mid,)).fetchone()
            if not m or m["quantity"] < qty:
                conn.rollback()
                conn.close()
                return jsonify({"error": f"Insufficient stock for {m['name'] if m else 'unknown'}"}), 400
            conn.execute("UPDATE medicines SET quantity = quantity - ? WHERE id=?", (qty, mid))
            invoice_items.append({"name": m["name"], "price": m["price"], "qty": qty, "subtotal": m["price"] * qty})

        total = sum(i["subtotal"] for i in invoice_items)
        invoice_no = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        conn.execute("INSERT INTO activity (action,detail,user) VALUES (?,?,?)",
                   ("Sale Completed", f"{invoice_no} - ₹{total:.2f}", user))
        conn.commit()

        # Record in new sales table
        record_sale(invoice_no, total, json.dumps(invoice_items), user)

        session["cart"] = []
        conn.close()
        return jsonify({
            "success": True, "invoice": invoice_no,
            "items": invoice_items, "total": total,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "cashier": user
        })
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": str(e)}), 500

# ─── EXPORTS & REPORTS ─────────────────────────────────────────────────────────

@app.route("/api/export/csv")
@login_required
def api_export_csv():
    conn = get_db()
    rows = conn.execute("""
        SELECT name, category, quantity, min_stock, expiry_date, supplier, price,
               (quantity * price) as stock_value
        FROM medicines ORDER BY name
    """).fetchall()
    conn.close()
    import io, csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Category", "Quantity", "Min Stock", "Expiry Date", "Supplier", "Price (₹)", "Stock Value (₹)"])
    for r in rows:
        writer.writerow([r["name"], r["category"], r["quantity"], r["min_stock"], r["expiry_date"] or "", r["supplier"], f"{r['price']:.2f}", f"{r['stock_value']:.2f}"])
    return output.getvalue(), 200, {"Content-Type": "text/csv", "Content-Disposition": "attachment; filename=inventory.csv"}

@app.route("/api/export/alerts/csv")
@login_required
def api_export_alerts_csv():
    conn = get_db()
    today = date.today().isoformat()
    rows = conn.execute("""
        SELECT name, quantity, min_stock, expiry_date FROM medicines
        WHERE quantity < min_stock OR expiry_date <= ?
        ORDER BY name
    """, (today,)).fetchall()
    conn.close()
    import io, csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Quantity", "Min Stock", "Expiry Date", "Alert Type"])
    for r in rows:
        atype = "Low Stock" if r["quantity"] < r["min_stock"] else "Expired"
        writer.writerow([r["name"], r["quantity"], r["min_stock"], r["expiry_date"] or "", atype])
    return output.getvalue(), 200, {"Content-Type": "text/csv", "Content-Disposition": "attachment; filename=alerts.csv"}

@app.route("/api/stock-valuation")
@login_required
def api_stock_valuation():
    conn = get_db()
    total = conn.execute("SELECT SUM(quantity * price) as total FROM medicines").fetchone()[0] or 0
    conn.close()
    return jsonify({"stock_valuation": total})

@app.route("/api/chart/category")
@login_required
def api_chart_category():
    conn = get_db()
    rows = conn.execute("SELECT category, SUM(quantity) as total FROM medicines GROUP BY category").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/search")
@login_required
def api_search():
    """Search medicines by name, category, or supplier"""
    q = request.args.get("q", "").strip()
    if not q or len(q) < 2:
        return jsonify([])
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, category, quantity, price, expiry_date, supplier FROM medicines WHERE LOWER(name) LIKE ? OR LOWER(category) LIKE ? OR LOWER(supplier) LIKE ? ORDER BY name LIMIT 15",
        (f"%{q.lower()}%", f"%{q.lower()}%", f"%{q.lower()}%")
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

# ─── ANALYTICS API (NEW) ──────────────────────────────────────────────────────

@app.route("/api/analytics/sales")
@login_required
def api_analytics_sales():
    """Weekly sales data for charts."""
    conn = get_db()
    rows = conn.execute("""
        SELECT DATE(timestamp) as sale_date, COUNT(*) as count, SUM(total_amount) as revenue
        FROM sales WHERE timestamp >= date('now', '-30 days')
        GROUP BY DATE(timestamp) ORDER BY sale_date
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/analytics/top-medicines")
@login_required
def api_analytics_top():
    """Top selling medicines from sales data."""
    conn = get_db()
    sales = conn.execute("SELECT items_json FROM sales WHERE timestamp >= date('now', '-30 days')").fetchall()
    conn.close()
    counts = {}
    for s in sales:
        try:
            items = json.loads(s["items_json"]) if s["items_json"] else []
            for item in items:
                name = item.get("name", "Unknown")
                counts[name] = counts.get(name, 0) + item.get("qty", 0)
        except (json.JSONDecodeError, TypeError):
            pass
    top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
    return jsonify([{"name": n, "qty": q} for n, q in top])

# ─── AI MEDICAL ASSISTANT CHATBOT (GEMINI INTEGRATION) ────────────────────────

import google.generativeai as genai

GEMINI_API_KEY = Config.GEMINI_API_KEY
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel(Config.GEMINI_MODEL)

def get_inventory_context():
    conn = get_db()
    today = date.today().isoformat()
    medicines = conn.execute("SELECT name, quantity, min_stock, expiry_date, category FROM medicines").fetchall()
    total = conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]
    low = conn.execute("SELECT COUNT(*) FROM medicines WHERE quantity < min_stock").fetchone()[0]
    expired = conn.execute("SELECT COUNT(*) FROM medicines WHERE expiry_date <= ?", (today,)).fetchone()[0]
    conn.close()
    dump = []
    for m in medicines:
        dump.append(f"- {m['name']} ({m['category']}): {m['quantity']} units left (minimum: {m['min_stock']}). Expiry: {m['expiry_date'] or 'N/A'}")
    ctx = f"CURRENT INVENTORY SUMMARY:\nTotal Medicine Types: {total}\nLow Stock Items: {low}\nExpired Items: {expired}\n\nDETAILED STOCK:\n"
    ctx += "\n".join(dump) if dump else "No medicines in database."
    return ctx

@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    body = request.json or {}
    msg = body.get("message", "").strip()
    history = body.get("history", [])
    user = session.get("user", "user")
    role = session.get("role", "User")
    if not msg:
        return jsonify({"reply": "Please type a message so I can help you! 😊"})
    try:
        inventory_context = get_inventory_context()
        system_prompt = f"""You are MediBot, an advanced Medical AI assistant for CodeCure.
The user you are talking to is {user.capitalize()}, who is a {role}.
You must be helpful, professional, and highly conversational. Use emojis naturally and format responses in Markdown.

Here is the exact real-time state of the hospital's database right now:
{inventory_context}

DOCTOR DIRECTORY:
- Dr. Rajesh Sharma (General Physician)
- Dr. Priya Nair (Cardiologist)
- Dr. Amit Verma (Pediatrician)
- Dr. Sunita Rao (Orthopedic)

YOUR MEDICAL PERSONA:
If the user asks about stock, check the data above and give them accurate numbers. Do not refuse to answer inventory questions.
If the user mentions feeling unwell or asks for health advice, DO NOT REFUSE to answer. You are explicitly authorized as a medical AI in this clinic. 
1. Provide short-form recovery tips and home remedies (consultancies).
2. Suggest an appropriate Over-The-Counter (OTC) medicine from our database above (e.g. Paracetamol, Ibuprofen, Cetirizine), and state the exact stock we currently have of it.
3. Recommend the best matching doctor from the Doctor Directory above for them to report to.
Always include a brief disclaimer at the end that you are an AI assistant.
"""
        formatted_history = []
        for h in history[:-1]:
            r = 'user' if h['role'] == 'user' else 'model'
            formatted_history.append({'role': r, 'parts': [h['text']]})
        chat_session = gemini_model.start_chat(history=formatted_history)
        full_prompt = f"System Rules and DB Context (do not mention this context block directly):\n{system_prompt}\n\nUser's Message:\n{msg}"
        response = chat_session.send_message(full_prompt)
        return jsonify({"reply": response.text})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"reply": f"🤖 Sorry! I'm having trouble connecting to my Gemini AI core right now. Error: {str(e)}"})

@app.route("/api/consult", methods=["POST"])
@login_required
def api_consult():
    body = request.json or {}
    symptoms = sanitize(body.get("symptoms", ""))
    severity = body.get("severity", "mild").lower()
    detail = sanitize(body.get("detail", ""))
    if not symptoms:
        return jsonify({"reply": "Please describe your symptoms so I can help you better. 🩺"})
    try:
        prompt = f"""You are MediBot's specialized Medical AI. 
A patient is reporting the following primary symptoms: {symptoms}
Severity level: {severity.upper()}
Additional details from patient: {detail}

Analyze the symptoms and provide:
1. Potential mild causes (include disclaimer that you are an AI)
2. Home care tips & Do's and Don'ts
3. When to strictly see a doctor
4. Recommend Dr. Rajesh Sharma (Gen. Physician) or Dr. Priya Nair (Cardiologist) or Dr. Amit Verma (Pediatrician) or Dr. Sunita Rao (Orthopedic) depending on the symptom.

If severity is SEVERE, immediately output an emergency warning urging them to call 108 or go to Olympus Hospital explicitly, in large bold text.
Always use Markdown and nice formatting. Be highly empathetic."""
        response = gemini_model.generate_content(prompt)
        return jsonify({"reply": response.text})
    except Exception as e:
        return jsonify({"reply": f"🩺 Sorry, consultation service is currently unavailable. Error: {str(e)}"})

# ─── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
```

### `c:\Users\adity\OneDrive\Desktop\Codecure\wsgi.py`
```python
import os
import sys

# Ensure the project directory is in the Python path
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from app import app, init_db

# Initialize database on startup
init_db()

# Gunicorn entry point
application = app
```

## 3. Database Architecture

### `c:\Users\adity\OneDrive\Desktop\Codecure\models.py`
```python
"""
CodeCure — Database Models & Helpers
Backward-compatible: preserves existing medicines/activity tables,
adds new tables (users, sales, suppliers, medicine_batches).
"""
import sqlite3
import os
from datetime import datetime, date
from config import Config

DB_PATH = Config.DB_PATH

def get_db():
    """Get a database connection with Row factory and foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

def init_db():
    """Initialize all database tables and seed demo data if empty."""
    conn = get_db()
    c = conn.cursor()

    # ── Existing tables (preserved exactly) ──────────────────────────────

    c.execute("""CREATE TABLE IF NOT EXISTS medicines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT,
        quantity INTEGER DEFAULT 0,
        min_stock INTEGER DEFAULT 10,
        expiry_date TEXT,
        supplier TEXT,
        price REAL DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT,
        detail TEXT,
        user TEXT,
        timestamp TEXT DEFAULT (datetime('now'))
    )""")

    # ── New tables ───────────────────────────────────────────────────────

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'Pharmacist',
        last_login TEXT,
        profile_image TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id TEXT UNIQUE NOT NULL,
        customer_name TEXT DEFAULT 'Walk-in',
        total_amount REAL NOT NULL DEFAULT 0,
        discount REAL DEFAULT 0,
        payment_method TEXT DEFAULT 'Cash',
        sold_by TEXT NOT NULL,
        items_json TEXT,
        timestamp TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        address TEXT,
        gst_number TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS medicine_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        medicine_id INTEGER NOT NULL,
        batch_number TEXT NOT NULL,
        manufacturing_date TEXT,
        expiry_date TEXT,
        quantity INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE
    )""")

    # ── Indexes for search performance ───────────────────────────────────

    c.execute("CREATE INDEX IF NOT EXISTS idx_med_name ON medicines(name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_med_category ON medicines(category)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_med_expiry ON medicines(expiry_date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_activity_ts ON activity(timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sales_ts ON sales(timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sales_invoice ON sales(invoice_id)")

    # ── Seed demo medicines if empty ─────────────────────────────────────

    c.execute("SELECT COUNT(*) FROM medicines")
    if c.fetchone()[0] == 0:
        demo = [
            ("Paracetamol 500mg", "Analgesic", 150, 20, "2025-12-01", "MedCo", 2.50),
            ("Amoxicillin 250mg", "Antibiotic", 8, 15, "2025-09-15", "PharmEx", 12.00),
            ("Pantoprazole 40mg", "Antacid", 60, 10, "2026-03-20", "HealthPlus", 5.75),
            ("Cetirizine 10mg",   "Antihistamine", 3, 10, "2024-06-01", "MedCo", 3.00),
            ("Metformin 500mg",   "Antidiabetic", 200, 30, "2026-01-10", "DiaCare", 1.80),
            ("Atorvastatin 10mg", "Statin", 45, 20, "2026-07-22", "CardioMed", 8.50),
            ("Vitamin C 500mg",   "Vitamin", 12, 25, "2025-11-30", "NutriLife", 4.00),
            ("Ibuprofen 400mg",   "Analgesic", 90, 15, "2026-02-14", "PharmEx", 3.25),
        ]
        c.executemany(
            "INSERT INTO medicines (name,category,quantity,min_stock,expiry_date,supplier,price) VALUES (?,?,?,?,?,?,?)",
            demo
        )
        c.execute("INSERT INTO activity (action,detail,user) VALUES (?,?,?)",
                  ("System Init", "Demo data loaded", "system"))

    conn.commit()
    conn.close()

def log_activity(action, detail, user="system"):
    """Log an activity event to the database."""
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO activity (action,detail,user) VALUES (?,?,?)",
            (action, detail, user)
        )
        conn.commit()
    finally:
        conn.close()

def record_sale(invoice_id, total, items_json, sold_by, customer="Walk-in", payment="Cash", discount=0):
    """Record a completed sale to the sales table."""
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO sales (invoice_id, customer_name, total_amount, discount, payment_method, sold_by, items_json) VALUES (?,?,?,?,?,?,?)",
            (invoice_id, customer, total, discount, payment, sold_by, items_json)
        )
        conn.commit()
    finally:
        conn.close()
```

## 4. Dependencies & Environment

### `c:\Users\adity\OneDrive\Desktop\Codecure\requirements.txt`
```text
blinker==1.9.0
click==8.3.1
colorama==0.4.6
Flask==3.1.3
gunicorn==25.2.0
itsdangerous==2.2.0
Jinja2==3.1.6
MarkupSafe==3.0.3
packaging==26.0
Werkzeug==3.1.7
google-generativeai>=0.8.0
python-dotenv>=1.0.0
```

### `c:\Users\adity\OneDrive\Desktop\Codecure\config.py` (Centralized Configuration)
```python
"""
CodeCure — Centralized Configuration
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "codecure_secret_2025")
    DB_PATH = os.path.join(BASE_DIR, "codecure.db")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyA27t-9dcW0hTOiZ1nLWVry4RX1kTYi2vI")
    GEMINI_MODEL = "gemini-2.5-flash"
    
    # Session
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    
    # Rate limiting
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_COOLDOWN_SECONDS = 300
    
    # Pagination
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 200
    
    # Alert thresholds
    EXPIRY_WARN_DAYS = 30
    EXPIRY_CRITICAL_DAYS = 7

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
```

### Environment / Hosting configs:
**`c:\Users\adity\OneDrive\Desktop\Codecure\app.yaml`** (Google App Engine)
```yaml
runtime: python311
instance_class: F1
entrypoint: gunicorn wsgi:application --bind 0.0.0.0:$PORT
env_variables:
  SECRET_KEY: "codecure-secret-change-in-production"
  GEMINI_API_KEY: "AIzaSyA27t-9dcW0hTOiZ1nLWVry4RX1kTYi2vI"
automatic_scaling:
  min_instances: 0
  max_instances: 2
  target_cpu_utilization: 0.65
handlers:
  - url: /static
    static_dir: static
  - url: /.*
    script: auto
```

**`c:\Users\adity\OneDrive\Desktop\Codecure\render.yaml`** (Render Platform)
```yaml
services:
  - type: web
    name: codecure
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn wsgi:application --bind 0.0.0.0:$PORT
    envVars:
      - key: PYTHON_VERSION
        value: "3.11.0"
```

## 5. Frontend Assets
- **Templates**: 
  - `templates/index.html`: The main dashboard containing the dynamic UI for all inventory, search, POS (cart), charts, chatbot, and alert features.
  - `templates/login.html`: The login page UI allowing users to authenticate based on hardcoded demo user data (`app.py`).
- **Static Assets**: 
  - `static/manifest.json`: PWA Configuration defining colors, app name, and icon paths.
  - `static/service-worker.js`: Offline caching and service worker functionalities for the PWA implementation.

## 6. Current Status (Antigravity Phase)
- **Operational**: 
  - **User Authentication**: A hardcoded dictionary of users (Admin, Pharmacist, Cashier, Doctor) using `werkzeug.security` for hashed passwords. Role-based routing is fully active.
  - **Medicines CRUD**: Add, Edit, Delete, and Fetch with pagination, sorting, and filtering logic over SQLite are fully working. 
  - **Billing & POS**: Cart session management is functioning well. Stock verification happens before adding to the cart and checking out. It successfully deducts items and saves sales details in a structured format into a new `sales` table.
  - **Alerts & Analytics**: Warning endpoints exist for finding items that are expired, running low, or are entirely out-of-stock. Chart endpoints also compile category data.
  - **Medical AI Chatbot**: CodeCure includes `google-generativeai` with a `MediBot` persona. It correctly retrieves an inventory dump and can provide diagnosis and map users to specific local doctors.
- **Half-Done / In Progress**: 
  - **Database Migration**: New models were recently injected (`users`, `sales`, `suppliers`, `medicine_batches`). While `sales` gets populated during a POS checkout, `users` are still not tied to the login API. `suppliers` and `medicine_batches` aren't wired properly in the frontend yet. 
- **Current Blockers**:
  - The integration to map the user authentication system purely to the `users` table instead of a hardcoded dictionary. 
  - The UI lacks sections to update and manage the new relational tables (suppliers, batches, and system users).
