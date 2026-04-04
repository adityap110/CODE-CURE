from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import os
from datetime import datetime, date

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

# ─── AUTH ──────────────────────────────────────────────────────────────────────

USERS = {
    "admin":      {"password": "1234", "role": "Admin"},
    "pharmacist": {"password": "1234", "role": "Pharmacist"},
    "doctor":     {"password": "1234", "role": "Doctor"},
}

@app.route("/", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        u = request.form.get("username", "").strip().lower()
        p = request.form.get("password", "").strip()
        if u in USERS and USERS[u]["password"] == p:
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
    conn = get_db()
    conn.execute(
        "INSERT INTO medicines (name,category,quantity,min_stock,expiry_date,supplier,price) VALUES (?,?,?,?,?,?,?)",
        (data["name"], data.get("category",""), int(data.get("quantity",0)),
         int(data.get("min_stock",10)), data.get("expiry_date",""),
         data.get("supplier",""), float(data.get("price",0)))
    )
    conn.commit()
    conn.close()
    log_activity("Add Medicine", data["name"], session["user"])
    return jsonify({"success": True})

@app.route("/api/medicines/<int:mid>", methods=["PUT"])
def api_update_medicine(mid):
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    if session["role"] not in ("Admin", "Pharmacist"):
        return jsonify({"error": "Permission denied"}), 403
    data = request.json
    conn = get_db()
    conn.execute(
        "UPDATE medicines SET name=?,category=?,quantity=?,min_stock=?,expiry_date=?,supplier=?,price=? WHERE id=?",
        (data["name"], data.get("category",""), int(data.get("quantity",0)),
         int(data.get("min_stock",10)), data.get("expiry_date",""),
         data.get("supplier",""), float(data.get("price",0)), mid)
    )
    conn.commit()
    conn.close()
    log_activity("Edit Medicine", f"ID {mid} updated", session["user"])
    return jsonify({"success": True})

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

    # ── Greetings ──
    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "howdy"]
    if any(g in msg for g in greetings):
        return (f"Hello {user.capitalize()}! 👋 I'm **MediBot**, your Smart Medical Inventory Assistant.\n\n"
                "I can help you with:\n"
                "• 📦 **Stock status** — ask about inventory levels\n"
                "• 💊 **Medicine info** — dosage, side effects, interactions\n"
                "• ⚠️ **Alerts** — expired or low stock items\n"
                "• 💡 **Tips** — inventory management best practices\n"
                "• 🔍 **Search** — find specific medicines\n\n"
                "What would you like to know?")

    # ── Help ──
    if msg in ["help", "what can you do", "commands", "menu"]:
        return ("Here's what I can help with:\n\n"
                "📦 **\"stock status\"** — Overview of your inventory\n"
                "⚠️ **\"alerts\"** or **\"low stock\"** — Current warnings\n"
                "💊 **\"info [medicine]\"** — Details about a specific medicine\n"
                "💊 **\"dosage [medicine]\"** — Dosage guidance\n"
                "⚠️ **\"interactions [medicine]\"** — Drug interactions\n"
                "🏥 **\"storage [medicine]\"** — Storage instructions\n"
                "📋 **\"expired\"** — List expired medicines\n"
                "💡 **\"tip\"** — Random inventory management tip\n"
                "📊 **\"summary\"** — Full inventory summary")

    # ── Stock Status ──
    if any(k in msg for k in ["stock status", "inventory status", "overview", "summary", "how many", "total"]):
        conn = get_db()
        today = date.today().isoformat()
        total = conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]
        ok = conn.execute("SELECT COUNT(*) FROM medicines WHERE quantity >= min_stock AND (expiry_date IS NULL OR expiry_date > ?)", (today,)).fetchone()[0]
        low = conn.execute("SELECT COUNT(*) FROM medicines WHERE quantity < min_stock", ).fetchone()[0]
        expired = conn.execute("SELECT COUNT(*) FROM medicines WHERE expiry_date <= ?", (today,)).fetchone()[0]
        total_qty = conn.execute("SELECT COALESCE(SUM(quantity),0) FROM medicines").fetchone()[0]
        total_val = conn.execute("SELECT COALESCE(SUM(quantity * price),0) FROM medicines").fetchone()[0]
        conn.close()
        return (f"📊 **Inventory Summary**\n\n"
                f"• Total medicines: **{total}** types\n"
                f"• Total units in stock: **{total_qty}**\n"
                f"• Estimated value: **₹{total_val:,.2f}**\n"
                f"• ✅ Healthy stock: **{ok}**\n"
                f"• ⚠️ Low stock: **{low}**\n"
                f"• 🚨 Expired: **{expired}**\n\n"
                f"{'⚠️ *Action needed: Some items require attention!*' if (low+expired) > 0 else '✅ *Everything looks good!*'}")

    # ── Low Stock ──
    if any(k in msg for k in ["low stock", "running low", "reorder", "shortage"]):
        conn = get_db()
        rows = conn.execute("SELECT name, quantity, min_stock FROM medicines WHERE quantity < min_stock ORDER BY quantity ASC").fetchall()
        conn.close()
        if not rows:
            return "✅ Great news! All medicines are above minimum stock levels."
        items = "\n".join(f"• **{r['name']}** — {r['quantity']} left (min: {r['min_stock']})" for r in rows)
        return f"⚠️ **Low Stock Alert** — {len(rows)} item(s) need reordering:\n\n{items}\n\n💡 *Tip: Contact your suppliers ASAP to avoid stockouts.*"

    # ── Expired ──
    if any(k in msg for k in ["expired", "expiry", "expire"]):
        conn = get_db()
        today = date.today().isoformat()
        rows = conn.execute("SELECT name, expiry_date FROM medicines WHERE expiry_date <= ? ORDER BY expiry_date ASC", (today,)).fetchall()
        conn.close()
        if not rows:
            return "✅ No expired medicines found. Your inventory is up to date!"
        items = "\n".join(f"• **{r['name']}** — expired on {r['expiry_date']}" for r in rows)
        return f"🚨 **Expired Medicines** — {len(rows)} item(s):\n\n{items}\n\n⚠️ *These should be removed from inventory and disposed of properly following pharmaceutical waste guidelines.*"

    # ── Alerts ──
    if any(k in msg for k in ["alert", "warning", "problem", "issue"]):
        conn = get_db()
        today = date.today().isoformat()
        low = conn.execute("SELECT name, quantity, min_stock FROM medicines WHERE quantity < min_stock").fetchall()
        expired = conn.execute("SELECT name, expiry_date FROM medicines WHERE expiry_date <= ?", (today,)).fetchall()
        conn.close()
        if not low and not expired:
            return "✅ No active alerts! Everything is running smoothly."
        parts = ["🔔 **Active Alerts**\n"]
        if low:
            parts.append(f"**⚠️ Low Stock ({len(low)}):**")
            for r in low:
                parts.append(f"  • {r['name']} — {r['quantity']} left")
        if expired:
            parts.append(f"\n**🚨 Expired ({len(expired)}):**")
            for r in expired:
                parts.append(f"  • {r['name']} — since {r['expiry_date']}")
        return "\n".join(parts)

    # ── Medicine Info ──
    for med_key, med_data in MEDICINE_INFO.items():
        if med_key in msg:
            if any(k in msg for k in ["dosage", "dose", "how much", "how to take"]):
                return f"💊 **{med_key.title()} — Dosage**\n\n{med_data['dosage']}\n\n⚠️ *Always consult a doctor before adjusting dosage.*"
            if any(k in msg for k in ["interaction", "mix", "combine", "conflict"]):
                return f"⚠️ **{med_key.title()} — Drug Interactions**\n\n{med_data['interactions']}\n\n🏥 *Always inform your doctor about all medications you take.*"
            if any(k in msg for k in ["side effect", "adverse", "reaction"]):
                return f"⚠️ **{med_key.title()} — Side Effects**\n\n{med_data['side_effects']}\n\n🏥 *Report any severe reactions to a healthcare provider immediately.*"
            if any(k in msg for k in ["storage", "store", "keep", "temperature"]):
                return f"🏥 **{med_key.title()} — Storage**\n\n{med_data['storage']}"
            # General info
            return (f"💊 **{med_key.title()}** ({med_data['category']})\n\n"
                    f"**Use:** {med_data['use']}\n"
                    f"**Dosage:** {med_data['dosage']}\n"
                    f"**Side Effects:** {med_data['side_effects']}\n"
                    f"**Storage:** {med_data['storage']}\n"
                    f"**Interactions:** {med_data['interactions']}\n\n"
                    f"⚠️ *This is for reference only. Always consult a healthcare professional.*")

    # ── Search Medicine ──
    if any(k in msg for k in ["search", "find", "look up", "check"]):
        search_term = msg.replace("search", "").replace("find", "").replace("look up", "").replace("check", "").strip()
        if search_term:
            conn = get_db()
            rows = conn.execute("SELECT name, quantity, expiry_date, category FROM medicines WHERE LOWER(name) LIKE ?", (f"%{search_term}%",)).fetchall()
            conn.close()
            if rows:
                items = "\n".join(f"• **{r['name']}** — Qty: {r['quantity']}, Exp: {r['expiry_date'] or 'N/A'}, Cat: {r['category']}" for r in rows)
                return f"🔍 **Search Results for \"{search_term}\":**\n\n{items}"
            return f"🔍 No medicines found matching \"{search_term}\". Try a different term."

    # ── Tips ──
    if any(k in msg for k in ["tip", "advice", "suggest", "best practice", "recommendation"]):
        import random
        return random.choice(GENERAL_TIPS) + "\n\n*Ask for another tip anytime!*"

    # ── Thank You ──
    if any(k in msg for k in ["thank", "thanks", "appreciate"]):
        return f"You're welcome, {user.capitalize()}! 😊 I'm always here to help. Feel free to ask anything else!"

    # ── Bye ──
    if any(k in msg for k in ["bye", "goodbye", "see you", "exit"]):
        return f"Goodbye, {user.capitalize()}! 👋 Stay healthy and keep your inventory in check! 🏥"

    # ── Fallback ──
    return ("I'm not sure I understand that. Here are some things you can ask me:\n\n"
            "• **\"stock status\"** — inventory overview\n"
            "• **\"low stock\"** — items running low\n"
            "• **\"expired\"** — expired medicines\n"
            "• **\"info paracetamol\"** — medicine details\n"
            "• **\"dosage amoxicillin\"** — dosage info\n"
            "• **\"interactions metformin\"** — drug interactions\n"
            "• **\"tip\"** — management best practice\n"
            "• **\"help\"** — full command list")


# ─── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
