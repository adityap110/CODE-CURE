import re

with open('app.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Alerts
text = re.sub(
    r'low = list\(conn\.medicines\.find\(\{"\$expr": \{"\$lt": \["\$quantity", "\$min_stock"\]\}\}\)\)\s*expired = list\(conn\.medicines\.find\(\{"expiry_date": \{"\$nin": \[None, ""\], "\$lte": today\}\}\)\)\s*expiring = list\(conn\.medicines\.find\(\{"expiry_date": \{"\$gt": today, "\$lte": warn_date\}\}\)\)\s*out = list\(conn\.medicines\.find\(\{"quantity": 0\}\)\)',
    '''low     = conn.execute("SELECT id,name,quantity,min_stock FROM medicines WHERE quantity < min_stock").fetchall()
    expired = conn.execute("SELECT id,name,expiry_date FROM medicines WHERE expiry_date != '' AND expiry_date <= ?", (today,)).fetchall()
    expiring = conn.execute("SELECT id,name,expiry_date FROM medicines WHERE expiry_date > ? AND expiry_date <= ?", (today, warn_date)).fetchall()
    out     = conn.execute("SELECT id,name FROM medicines WHERE quantity = 0").fetchall()''',
    text, flags=re.DOTALL
)

# Restock & Discard
text = re.sub(
    r'row = conn\.medicines\.find_one\(\{"_id": ObjectId\(mid\)\}\)\s*if not row:\s*return jsonify\(\{"error": "Medicine not found"\}\), 404\s*new_qty = safe_int\(data\.get\("quantity", 0\)\)\s*if new_qty <= 0:\s*new_qty = row\["min_stock"\] \* 2\s*# Default: double the minimum\s*conn\.medicines\.update_one\(\{"_id": ObjectId\(mid\)\}, \{"\$set": \{"quantity": new_qty\}\}\)',
    '''row = conn.execute("SELECT name, min_stock FROM medicines WHERE id=?", (mid,)).fetchone()
        if not row:
            return jsonify({"error": "Medicine not found"}), 404
        new_qty = safe_int(data.get("quantity", 0))
        if new_qty <= 0:
            new_qty = row["min_stock"] * 2
        conn.execute("UPDATE medicines SET quantity=? WHERE id=?", (new_qty, mid))
        conn.commit()''',
    text, flags=re.DOTALL
)

text = re.sub(
    r'row = conn\.medicines\.find_one\(\{"_id": ObjectId\(mid\)\}\)\s*if not row:\s*return jsonify\(\{"error": "Medicine not found"\}\), 404\s*conn\.medicines\.update_one\(\{"_id": ObjectId\(mid\)\}, \{"\$set": \{"quantity": 0\}\}\)',
    '''row = conn.execute("SELECT name, quantity FROM medicines WHERE id=?", (mid,)).fetchone()
        if not row:
            return jsonify({"error": "Medicine not found"}), 404
        conn.execute("UPDATE medicines SET quantity=0 WHERE id=?", (mid,))
        conn.commit()''',
    text, flags=re.DOTALL
)

# Export
text = re.sub(
    r'rows = list\(conn\.medicines\.find\(\)\.sort\("name", 1\)\)',
    '''rows = conn.execute("SELECT * FROM medicines ORDER BY name ASC").fetchall()''',
    text
)

# Reports Dashboard
text = re.sub(
    r'rows = list\(conn\.medicines\.find\(\{\s*"\$expr": \{"\$lt": \["\$quantity", "\$min_stock"\]\}\s*\}\)\)\s*low_stock = len\(rows\)',
    '''low_stock = conn.execute("SELECT COUNT(*) FROM medicines WHERE quantity < min_stock").fetchone()[0]''',
    text, flags=re.DOTALL
)

text = re.sub(
    r'pipeline = \[\s*\{"\$match": \{"timestamp": \{"\$gte": thirty_days_ago\}\}\},\s*\{"\$group": \{"_id": None, "total": \{"\$sum": "\$total_amount"\}\}\}\s*\]\s*result = list\(conn\.sales\.aggregate\(pipeline\)\)\s*rev_30 = result\[0\]\["total"\] if result else 0\s*pipeline = \[\s*\{"\$match": \{"timestamp": \{"\$gte": today\}\}\},\s*\{"\$group": \{"_id": None, "total": \{"\$sum": "\$total_amount"\}\}\}\s*\]\s*result = list\(conn\.sales\.aggregate\(pipeline\)\)\s*rev_today = result\[0\]\["total"\] if result else 0',
    '''rev_30 = conn.execute("SELECT SUM(total_amount) FROM sales WHERE timestamp >= ?", (thirty_days_ago,)).fetchone()[0] or 0
    rev_today = conn.execute("SELECT SUM(total_amount) FROM sales WHERE timestamp >= ?", (today,)).fetchone()[0] or 0''',
    text, flags=re.DOTALL
)

# Chatbot
text = re.sub(
    r'low_items = list\(conn\.medicines\.find\(\{\s*"\$expr": \{"\$lt": \["\$quantity", "\$min_stock"\]\}\s*\}, \{"name": 1, "quantity": 1\}\)\)\s*exp_items = list\(conn\.medicines\.find\(\{\s*"expiry_date": \{"\$nin": \[None, ""\], "\$lte": today\}\s*\}, \{"name": 1, "expiry_date": 1\}\)\)',
    '''low_items = [dict(r) for r in conn.execute("SELECT name, quantity FROM medicines WHERE quantity < min_stock").fetchall()]
        exp_items = [dict(r) for r in conn.execute("SELECT name, expiry_date FROM medicines WHERE expiry_date != '' AND expiry_date <= ?", (today,)).fetchall()]''',
    text, flags=re.DOTALL
)

# Sales pipeline
text = re.sub(
    r'pipeline = \[\s*\{"\$match": \{"timestamp": \{"\$gte": thirty_days_ago\}\}\},\s*\{"\$group": \{\s*"_id": \{"\$substr": \["\$timestamp", 0, 10\]\},\s*"revenue": \{"\$sum": "\$total_amount"\}\s*\}\},\s*\{"\$sort": \{"_id": 1\}\}\s*\]\s*rows = list\(conn\.sales\.aggregate\(pipeline\)\)\s*sales_data = \[\{"date": r\["_id"\], "revenue": r\["revenue"\]\} for r in rows\]\s*sales = list\(conn\.sales\.find\(\{"timestamp": \{"\$gte": thirty_days_ago\}\}, \{"items_json": 1\}\)\)',
    '''rows = conn.execute("""
        SELECT SUBSTR(timestamp, 1, 10) as date, SUM(total_amount) as revenue
        FROM sales
        WHERE timestamp >= ?
        GROUP BY SUBSTR(timestamp, 1, 10)
        ORDER BY date ASC
    """, (thirty_days_ago,)).fetchall()
    sales_data = [{"date": r["date"], "revenue": r["revenue"]} for r in rows]

    sales = conn.execute("SELECT items_json FROM sales WHERE timestamp >= ?", (thirty_days_ago,)).fetchall()''',
    text, flags=re.DOTALL
)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(text)
