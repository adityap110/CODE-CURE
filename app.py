from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3
import os
from datetime import datetime, date
import re

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "codecure_secret_2025")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "codecure.db")

# ─── DB HELPERS ───────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

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

    # Seed demo data if empty
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
    conn = get_db()
    conn.execute("INSERT INTO activity (action,detail,user) VALUES (?,?,?)", (action, detail, user))
    conn.commit()
    conn.close()

def validate_medicine_data(data):
    """Validate medicine data for add/edit operations"""
    errors = []
    if not data.get("name", "").strip():
        errors.append("Medicine name is required")
    if len(data.get("name", "")) > 255:
        errors.append("Medicine name too long (max 255 chars)")
    try:
        qty = int(data.get("quantity", 0))
        if qty < 0:
            errors.append("Quantity cannot be negative")
    except (ValueError, TypeError):
        errors.append("Quantity must be a number")
    try:
        min_s = int(data.get("min_stock", 10))
        if min_s < 0:
            errors.append("Min stock cannot be negative")
    except (ValueError, TypeError):
        errors.append("Min stock must be a number")
    try:
        price = float(data.get("price", 0))
        if price < 0:
            errors.append("Price cannot be negative")
    except (ValueError, TypeError):
        errors.append("Price must be a valid number")
    return errors

# ─── AUTH ──────────────────────────────────────────────────────────────────────

USERS = {
    "admin":      {"password": generate_password_hash("1234"), "role": "Admin"},
    "pharmacist": {"password": generate_password_hash("1234"), "role": "Pharmacist"},
    "doctor":     {"password": generate_password_hash("1234"), "role": "Doctor"},
}

@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    return f"<pre>{traceback.format_exc()}</pre>", 500

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
    log_activity("Logout", f"{user} logged out", user)
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", user=session["user"], role=session["role"])

# ─── API ───────────────────────────────────────────────────────────────────────

@app.route("/api/stats")
def api_stats():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    today = date.today().isoformat()
    soon  = "2025-09-30"  # within ~6 months from demo date

    total   = conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]
    ok      = conn.execute("SELECT COUNT(*) FROM medicines WHERE quantity >= min_stock AND (expiry_date IS NULL OR expiry_date > ?)", (today,)).fetchone()[0]
    low     = conn.execute("SELECT COUNT(*) FROM medicines WHERE quantity < min_stock AND (expiry_date IS NULL OR expiry_date > ?)", (today,)).fetchone()[0]
    expired = conn.execute("SELECT COUNT(*) FROM medicines WHERE expiry_date <= ?", (today,)).fetchone()[0]
    conn.close()
    return jsonify({"total": total, "ok": ok, "low": low, "expired": expired})

@app.route("/api/medicines", methods=["GET"])
def api_medicines():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    filter_type = request.args.get("filter", "all")
    today = date.today().isoformat()

    conn = get_db()
    if filter_type == "low":
        rows = conn.execute("SELECT * FROM medicines WHERE quantity < min_stock ORDER BY quantity ASC").fetchall()
    elif filter_type == "expiring":
        rows = conn.execute("SELECT * FROM medicines WHERE expiry_date BETWEEN ? AND '2025-12-31' ORDER BY expiry_date ASC", (today,)).fetchall()
    elif filter_type == "expired":
        rows = conn.execute("SELECT * FROM medicines WHERE expiry_date <= ? ORDER BY expiry_date ASC", (today,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM medicines ORDER BY name ASC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/medicines", methods=["POST"])
def api_add_medicine():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    if session["role"] not in ("Admin", "Pharmacist"):
        return jsonify({"error": "Permission denied"}), 403

    data = request.json
    errors = validate_medicine_data(data)
    if errors:
        return jsonify({"error": ", ".join(errors)}), 400

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO medicines (name,category,quantity,min_stock,expiry_date,supplier,price) VALUES (?,?,?,?,?,?,?)",
            (data["name"].strip(), data.get("category","").strip(), int(data.get("quantity",0)),
             int(data.get("min_stock",10)), data.get("expiry_date",""),
             data.get("supplier","").strip(), float(data.get("price",0)))
        )
        conn.commit()
        log_activity("Add Medicine", data["name"], session["user"])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

@app.route("/api/medicines/<int:mid>", methods=["PUT"])
def api_update_medicine(mid):
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    if session["role"] not in ("Admin", "Pharmacist"):
        return jsonify({"error": "Permission denied"}), 403

    data = request.json
    errors = validate_medicine_data(data)
    if errors:
        return jsonify({"error": ", ".join(errors)}), 400

    conn = get_db()
    try:
        conn.execute(
            "UPDATE medicines SET name=?,category=?,quantity=?,min_stock=?,expiry_date=?,supplier=?,price=? WHERE id=?",
            (data["name"].strip(), data.get("category","").strip(), int(data.get("quantity",0)),
             int(data.get("min_stock",10)), data.get("expiry_date",""),
             data.get("supplier","").strip(), float(data.get("price",0)), mid)
        )
        conn.commit()
        log_activity("Edit Medicine", f"ID {mid} updated", session["user"])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

@app.route("/api/medicines/<int:mid>", methods=["DELETE"])
def api_delete_medicine(mid):
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    if session["role"] != "Admin":
        return jsonify({"error": "Only Admin can delete"}), 403
    conn = get_db()
    row = conn.execute("SELECT name FROM medicines WHERE id=?", (mid,)).fetchone()
    conn.execute("DELETE FROM medicines WHERE id=?", (mid,))
    conn.commit()
    conn.close()
    log_activity("Delete Medicine", row["name"] if row else f"ID {mid}", session["user"])
    return jsonify({"success": True})

@app.route("/api/alerts")
def api_alerts():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    today = date.today().isoformat()
    conn = get_db()
    low     = conn.execute("SELECT id,name,quantity,min_stock FROM medicines WHERE quantity < min_stock").fetchall()
    expired = conn.execute("SELECT id,name,expiry_date FROM medicines WHERE expiry_date <= ?", (today,)).fetchall()
    conn.close()
    alerts = []
    for r in low:
        alerts.append({"type":"low","name":r["name"],"detail":f"Only {r['quantity']} left (min {r['min_stock']})"})
    for r in expired:
        alerts.append({"type":"expired","name":r["name"],"detail":f"Expired on {r['expiry_date']}"})
    return jsonify(alerts)

@app.route("/api/activity")
def api_activity():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    rows = conn.execute("SELECT * FROM activity ORDER BY id DESC LIMIT 20").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/chart/category")
def api_chart_category():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    conn = get_db()
    rows = conn.execute("SELECT category, SUM(quantity) as total FROM medicines GROUP BY category").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/search")
def api_search():
    """Search medicines by name, category, or supplier"""
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    q = request.args.get("q", "").strip()
    if not q or len(q) < 2:
        return jsonify([])

    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, category, quantity, expiry_date, supplier FROM medicines WHERE LOWER(name) LIKE ? OR LOWER(category) LIKE ? OR LOWER(supplier) LIKE ? ORDER BY name LIMIT 15",
        (f"%{q.lower()}%", f"%{q.lower()}%", f"%{q.lower()}%")
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

# ─── AI MEDICAL ASSISTANT CHATBOT ─────────────────────────────────────────────

MEDICINE_INFO = {
    "paracetamol": {
        "use": "Pain relief & fever reduction",
        "dosage": "Adults: 500mg–1g every 4–6 hours (max 4g/day)",
        "side_effects": "Rare at recommended doses. Liver damage with overdose.",
        "storage": "Store below 25°C in a dry place",
        "interactions": "Avoid with alcohol. Caution with warfarin, carbamazepine.",
        "category": "Analgesic"
    },
    "amoxicillin": {
        "use": "Bacterial infections (ear, nose, throat, urinary tract, skin)",
        "dosage": "Adults: 250–500mg every 8 hours for 7–14 days",
        "side_effects": "Diarrhea, nausea, rash. Rarely: allergic reactions.",
        "storage": "Store below 25°C. Reconstituted suspension: refrigerate, use within 14 days.",
        "interactions": "May reduce efficacy of oral contraceptives. Avoid with methotrexate.",
        "category": "Antibiotic"
    },
    "pantoprazole": {
        "use": "Acid reflux (GERD), stomach ulcers, Zollinger-Ellison syndrome",
        "dosage": "Adults: 40mg once daily before breakfast for 4–8 weeks",
        "side_effects": "Headache, diarrhea, nausea. Long-term: B12/magnesium deficiency.",
        "storage": "Store below 30°C, protect from moisture",
        "interactions": "Reduces absorption of ketoconazole, iron supplements. Caution with clopidogrel.",
        "category": "Antacid"
    },
    "cetirizine": {
        "use": "Allergies, hay fever, hives, allergic rhinitis",
        "dosage": "Adults: 10mg once daily. Children 6–12: 5mg twice daily.",
        "side_effects": "Drowsiness, dry mouth, fatigue, headache.",
        "storage": "Store at room temperature (15–30°C)",
        "interactions": "Enhanced sedation with alcohol and CNS depressants.",
        "category": "Antihistamine"
    },
    "metformin": {
        "use": "Type 2 diabetes – lowers blood sugar levels",
        "dosage": "Adults: Start 500mg twice daily with meals, max 2550mg/day",
        "side_effects": "Nausea, diarrhea, metallic taste. Rarely: lactic acidosis.",
        "storage": "Store below 25°C, protect from light and moisture",
        "interactions": "Avoid excessive alcohol. Hold before contrast dye procedures. Caution with diuretics.",
        "category": "Antidiabetic"
    },
    "atorvastatin": {
        "use": "High cholesterol, cardiovascular disease prevention",
        "dosage": "Adults: 10–80mg once daily, usually at bedtime",
        "side_effects": "Muscle pain, headache, joint pain. Rarely: liver damage, rhabdomyolysis.",
        "storage": "Store at room temperature, protect from light",
        "interactions": "Avoid grapefruit. Caution with erythromycin, cyclosporine, fibrates.",
        "category": "Statin"
    },
    "vitamin c": {
        "use": "Immune support, antioxidant, scurvy prevention, wound healing",
        "dosage": "Adults: 65–90mg daily (supplement: 250–500mg daily)",
        "side_effects": "High doses: stomach cramps, diarrhea, kidney stones.",
        "storage": "Store in a cool, dry place away from light",
        "interactions": "May increase iron absorption. High doses may interfere with certain lab tests.",
        "category": "Vitamin"
    },
    "ibuprofen": {
        "use": "Pain, inflammation, fever, arthritis, menstrual cramps",
        "dosage": "Adults: 200–400mg every 4–6 hours (max 1200mg/day OTC)",
        "side_effects": "Stomach upset, nausea, dizziness. Risk of GI bleeding with long-term use.",
        "storage": "Store at room temperature, protect from moisture",
        "interactions": "Avoid with aspirin, anticoagulants, other NSAIDs. Caution with ACE inhibitors.",
        "category": "Analgesic"
    },
}

GENERAL_TIPS = [
    "💡 Always check expiry dates during monthly inventory audits.",
    "💡 Maintain FIFO (First In, First Out) for medicine dispensing.",
    "💡 Keep emergency medicines (epinephrine, naloxone) easily accessible.",
    "💡 Store vaccines and insulin in temperature-controlled refrigerators (2–8°C).",
    "💡 Document all controlled substance transactions as per regulations.",
    "💡 Train staff on proper handling of cytotoxic and hazardous drugs.",
    "💡 Set reorder points at 20% above minimum stock levels for safety.",
    "💡 Separate look-alike/sound-alike (LASA) medications to prevent errors.",
    "💡 Implement barcode scanning for accurate inventory tracking and reduced errors.",
    "💡 Schedule regular audits (quarterly) to prevent discrepancies and shrinkage.",
    "💡 Use color-coded labels for different medicine categories for quick identification.",
    "💡 Maintain a cold chain log for temperature-sensitive medicines.",
    "💡 Train staff on proper PPE usage when handling hazardous substances.",
    "💡 Keep detailed records of medicine recalls and disposal procedures.",
]

@app.route("/api/chat", methods=["POST"])
def api_chat():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    msg = request.json.get("message", "").strip().lower()
    user = session.get("user", "user")
    role = session.get("role", "User")

    if not msg:
        return jsonify({"reply": "Please type a message so I can help you! 😊"})

    reply = process_chat(msg, user, role)
    return jsonify({"reply": reply})


def process_chat(msg, user, role):
    import random

    # ── Greetings & Casual Talk ──
    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "howdy", "sup", "what's up", "how are you"]
    if any(g in msg for g in greetings):
        responses = [
            f"Hey {user.capitalize()}! 👋 How's your day going? Need help with anything inventory-related?",
            f"Hello {user.capitalize()}! 😊 Great to see you! What can I help you with today?",
            f"Hi there {user.capitalize()}! 🎉 Ready to tackle some inventory tasks?",
            f"What's up {user.capitalize()}! 👋 How can I assist with your medical inventory?",
        ]
        return random.choice(responses)

    # ── Health Check ──
    if any(k in msg for k in ["how are you", "how r u", "you okay", "you doing"]):
        return "I'm doing great! Thanks for asking! 😄 I'm fully operational and ready to help you manage your inventory. How are *you* doing?"

    # ── Thanks & Appreciation ──
    if any(k in msg for k in ["thank", "thanks", "appreciate", "thanks mate", "cheers"]):
        responses = [
            f"Happy to help, {user.capitalize()}! 🙌 Let me know if you need anything else!",
            f"Anytime, {user.capitalize()}! 😊 That's what I'm here for!",
            f"No problem at all! Glad I could assist! 👍",
            f"My pleasure! Feel free to ask anytime! 🎯",
        ]
        return random.choice(responses)

    # ── Goodbye ──
    if any(k in msg for k in ["bye", "goodbye", "see you", "exit", "quit", "later", "see ya", "take care"]):
        responses = [
            f"Goodbye, {user.capitalize()}! 👋 Keep that inventory in perfect shape! 🏥",
            f"Take care, {user.capitalize()}! See you soon! 👍",
            f"Catch you later! Stay organized! 🎯",
            f"See you next time, {user.capitalize()}! Keep up the good work! 💪",
        ]
        return random.choice(responses)

    # ── Help & What Can You Do ──
    if any(k in msg for k in ["help", "what can you do", "commands", "menu", "capabilities", "what do you do", "features"]):
        return ("I'm **MediBot**, your intelligent medical inventory assistant! 🤖 Here's what I can do:\n\n"
                "**📊 Inventory & Stock Management:**\n"
                "• Ask about stock status, low items, or expired medicines\n"
                "• Search for any medicine in the database\n"
                "• Get alerts about inventory issues\n\n"
                "**💊 Medicine Information:**\n"
                "• Info on dosage, side effects, and interactions\n"
                "• Storage instructions and best practices\n\n"
                "**💡 Tips & Guidance:**\n"
                "• Inventory management best practices\n"
                "• Pharmaceutical handling tips\n\n"
                "**Just chat naturally!** Try things like:\n"
                "• \"How's our stock looking?\"\n"
                "• \"Do we have paracetamol?\"\n"
                "• \"Give me a management tip\"\n"
                "• \"What's expiring soon?\"\n\n"
                "What would you like to know? 😊")

    # ── Smart Stock Status Detection ──
    stock_keywords = ["stock", "inventory", "how many", "total", "overview", "status", "how's our", "our stock", "do we have"]
    if any(k in msg for k in stock_keywords):
        conn = get_db()
        today = date.today().isoformat()
        total = conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]
        ok = conn.execute("SELECT COUNT(*) FROM medicines WHERE quantity >= min_stock AND (expiry_date IS NULL OR expiry_date > ?)", (today,)).fetchone()[0]
        low = conn.execute("SELECT COUNT(*) FROM medicines WHERE quantity < min_stock").fetchone()[0]
        expired = conn.execute("SELECT COUNT(*) FROM medicines WHERE expiry_date <= ?", (today,)).fetchone()[0]
        total_qty = conn.execute("SELECT COALESCE(SUM(quantity),0) FROM medicines").fetchone()[0]
        total_val = conn.execute("SELECT COALESCE(SUM(quantity * price),0) FROM medicines").fetchone()[0]
        conn.close()

        summary = (f"**Here's your inventory snapshot:**\n\n"
                  f"📦 **{total}** medicine types | **{total_qty:,}** total units\n"
                  f"💰 Estimated value: **₹{total_val:,.2f}**\n\n"
                  f"✅ **{ok}** items - Good stock levels\n"
                  f"⚠️ **{low}** items - Running low\n"
                  f"🚨 **{expired}** items - Expired\n\n")

        if low > 0:
            summary += f"*You have {low} item(s) that need reordering soon!* 📉"
        elif expired > 0:
            summary += f"*{expired} item(s) need to be removed.* ⚠️"
        else:
            summary += "*Everything looks great! Keep up the good work!* ✨"

        return summary

    # ── Low Stock Detection ──
    if any(k in msg for k in ["low", "running low", "reorder", "shortage", "need to order", "out of stock", "almost out"]):
        conn = get_db()
        rows = conn.execute("SELECT name, quantity, min_stock FROM medicines WHERE quantity < min_stock ORDER BY quantity ASC").fetchall()
        conn.close()
        if not rows:
            return "✅ Good news! All your medicines are above minimum stock levels. No reordering needed right now!"
        items = "\n".join(f"• **{r['name']}** — {r['quantity']} left (minimum: {r['min_stock']})" for r in rows)
        return f"⚠️ **Alert: {len(rows)} item(s) running low:**\n\n{items}\n\n💡 I'd recommend contacting your suppliers to order these ASAP!"

    # ── Expired Detection ──
    if any(k in msg for k in ["expired", "expiry", "expire", "old", "outdated", "past date", "gone bad"]):
        conn = get_db()
        today = date.today().isoformat()
        rows = conn.execute("SELECT name, expiry_date FROM medicines WHERE expiry_date <= ? ORDER BY expiry_date ASC", (today,)).fetchall()
        conn.close()
        if not rows:
            return "✅ Great! No expired medicines detected. Your inventory is clean and current!"
        items = "\n".join(f"• **{r['name']}** — Expired {r['expiry_date']}" for r in rows)
        return f"🚨 **Found {len(rows)} expired item(s):**\n\n{items}\n\n⚠️ These should be safely removed and disposed of according to pharmaceutical guidelines."

    # ── Alerts ──
    if any(k in msg for k in ["alert", "warning", "issue", "problem", "what's wrong", "any issues", "anything urgent"]):
        conn = get_db()
        today = date.today().isoformat()
        low = conn.execute("SELECT name, quantity, min_stock FROM medicines WHERE quantity < min_stock").fetchall()
        expired = conn.execute("SELECT name, expiry_date FROM medicines WHERE expiry_date <= ?", (today,)).fetchall()
        conn.close()
        if not low and not expired:
            return "✅ Everything is looking perfect! No active alerts or issues right now. Your inventory is well-maintained! 🎉"

        alerts_text = "🔔 **Here are your current alerts:**\n\n"
        if low:
            alerts_text += f"**⚠️ Low Stock ({len(low)} items):**\n"
            for i, r in enumerate(low[:5], 1):
                alerts_text += f"  {i}. {r['name']} — {r['quantity']} units left\n"
            if len(low) > 5:
                alerts_text += f"  ...and {len(low)-5} more\n"
        if expired:
            alerts_text += f"\n**🚨 Expired ({len(expired)} items):**\n"
            for i, r in enumerate(expired[:5], 1):
                alerts_text += f"  {i}. {r['name']} (since {r['expiry_date']})\n"
            if len(expired) > 5:
                alerts_text += f"  ...and {len(expired)-5} more\n"
        return alerts_text

    # ── Medicine Info (Natural Queries) ──
    medicine_queries = ["tell me about", "info on", "what about", "info for", "information", "details"]
    if any(q in msg for q in medicine_queries):
        for med_key, med_data in MEDICINE_INFO.items():
            if med_key in msg:
                if any(k in msg for k in ["dosage", "dose", "take", "how much"]):
                    return f"💊 **{med_key.title()} - Dosage Information**\n\n{med_data['dosage']}\n\n⚠️ Always consult with a doctor before making dosage changes."
                if any(k in msg for k in ["interaction", "mix", "combine", "conflict", "together"]):
                    return f"⚠️ **{med_key.title()} - Drug Interactions**\n\n{med_data['interactions']}\n\n🏥 Always mention all medications to your healthcare provider."
                if any(k in msg for k in ["side effect", "adverse", "reaction", "bad effect"]):
                    return f"⚠️ **{med_key.title()} - Side Effects**\n\n{med_data['side_effects']}\n\n🏥 Contact a doctor if you experience severe reactions."
                if any(k in msg for k in ["storage", "store", "keep", "temperature", "store how"]):
                    return f"🏥 **{med_key.title()} - Storage Instructions**\n\n{med_data['storage']}"
                return (f"💊 **{med_key.title()}** ({med_data['category']})\n\n"
                        f"**What it's used for:** {med_data['use']}\n"
                        f"**How to take:** {med_data['dosage']}\n"
                        f"**Possible side effects:** {med_data['side_effects']}\n"
                        f"**How to store:** {med_data['storage']}\n"
                        f"**Drug interactions:** {med_data['interactions']}\n\n"
                        f"⚠️ *This is for reference only. Always consult a healthcare professional.*")

    # ── Direct Medicine Names ──
    for med_key, med_data in MEDICINE_INFO.items():
        if med_key in msg:
            if any(k in msg for k in ["dosage", "dose", "how much", "how to take"]):
                return f"💊 **{med_key.title()} - Dosage**\n\n{med_data['dosage']}\n\n⚠️ Always consult a doctor before adjusting doses."
            if any(k in msg for k in ["interaction", "mix", "combine", "conflict"]):
                return f"⚠️ **{med_key.title()} - Interactions**\n\n{med_data['interactions']}\n\n🏥 Keep your doctor informed about all meds."
            if any(k in msg for k in ["side effect", "adverse", "reaction"]):
                return f"⚠️ **{med_key.title()} - Side Effects**\n\n{med_data['side_effects']}\n\n🏥 Report severe reactions immediately."
            if any(k in msg for k in ["storage", "store", "keep", "temperature"]):
                return f"🏥 **{med_key.title()} - Storage**\n\n{med_data['storage']}"
            return (f"💊 **{med_key.title()}** ({med_data['category']})\n\n"
                    f"**Used for:** {med_data['use']}\n"
                    f"**Dosage:** {med_data['dosage']}\n"
                    f"**Side effects:** {med_data['side_effects']}\n"
                    f"**Storage:** {med_data['storage']}\n"
                    f"**Interactions:** {med_data['interactions']}\n\n"
                    f"⚠️ *For reference only. Always consult a professional.*")

    # ── Smart Search ──
    search_keywords = ["search", "find", "look for", "do we have", "do we stock", "check if", "is there", "available", "have any"]
    if any(k in msg for k in search_keywords):
        search_term = msg
        for k in search_keywords:
            search_term = search_term.replace(k, "").strip()
        search_term = search_term.replace("?", "").replace("a ", "").replace("any ", "").strip()

        if len(search_term) > 1:
            conn = get_db()
            rows = conn.execute("SELECT name, quantity, expiry_date, category FROM medicines WHERE LOWER(name) LIKE ?", (f"%{search_term}%",)).fetchall()
            conn.close()
            if rows:
                results = "\n".join(f"• **{r['name']}** — {r['quantity']} units, expires {r['expiry_date'] or 'N/A'} ({r['category']})" for r in rows)
                return f"✅ **Found {len(rows)} result(s) for \"{search_term}\":**\n\n{results}"
            else:
                return f"🔍 No medicines found matching \"{search_term}\". Try a different name or ask me about a medicine we do have!"

    # ── Tips & Best Practices ──
    if any(k in msg for k in ["tip", "advice", "suggest", "best practice", "recommendation", "how should", "how to", "best way"]):
        tip = random.choice(GENERAL_TIPS)
        return f"{tip}\n\n💡 Need another tip? Just ask!"

    # ── Fallback with Personality ──
    fallback_responses = [
        f"Hmm, I'm not quite sure what you mean! 🤔 I'm specifically trained to help with medical inventory.\nTry asking about:\n• Stock levels\n• Expired medicines\n• Medicine info\n• Search for medicines\n\nOr ask \"help\" for options! 😊",
        f"I didn't catch that! 👂 I'm here for inventory management. Stock check? Medicine details? Low stock alerts?",
        f"Not sure about that! 🤷 I can help with:\n✅ Inventory management\n✅ Medicine info\n✅ Stock alerts\n✅ Expiry tracking\n\nWhat would you like?",
    ]
    return random.choice(fallback_responses)


# ─── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
