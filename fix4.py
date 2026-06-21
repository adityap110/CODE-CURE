import re

with open('app.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. /api/reports/alerts-print
text = re.sub(
    r'rows = list\(conn\.medicines\.find\(\{\s*"\$or": \[\s*\{"\$expr": \{"\$lt": \["\$quantity", "\$min_stock"\]\}\},\s*\{"expiry_date": \{"\$nin": \[None, ""\], "\$lte": today\}\}\s*\]\s*\}\)\.sort\("name", 1\)\)',
    '''rows = [dict(r) for r in conn.execute("SELECT * FROM medicines WHERE quantity < min_stock OR (expiry_date != '' AND expiry_date <= ?) ORDER BY name ASC", (today,)).fetchall()]''',
    text, flags=re.DOTALL
)

# 2. /api/stats/valuation
text = re.sub(
    r'pipeline = \[\s*\{"\$group": \{"_id": None, "total": \{"\$sum": \{"\$multiply": \["\$price", "\$quantity"\]\}\}\}\}\s*\]\s*result = list\(conn\.medicines\.aggregate\(pipeline\)\)\s*total = result\[0\]\["total"\] if result else 0',
    '''total = conn.execute("SELECT SUM(price * quantity) FROM medicines").fetchone()[0] or 0''',
    text, flags=re.DOTALL
)

# 3. /api/chart/category
text = re.sub(
    r'pipeline = \[\s*\{"\$group": \{"_id": "\$category", "count": \{"\$sum": 1\}\}\}\s*\]\s*rows = list\(conn\.medicines\.aggregate\(pipeline\)\)',
    '''rows = [{"_id": r["category"], "count": r["count"]} for r in conn.execute("SELECT category, COUNT(*) as count FROM medicines GROUP BY category").fetchall()]''',
    text, flags=re.DOTALL
)

# 4. /api/search
text = re.sub(
    r'rows = list\(conn\.medicines\.find\(\{\s*"\$or": \[\s*\{"name": \{"\$regex": q, "\$options": "i"\}\},\s*\{"category": \{"\$regex": q, "\$options": "i"\}\},\s*\{"supplier": \{"\$regex": q, "\$options": "i"\}\}\s*\]\s*\}\)\.limit\(10\)\)',
    '''q_like = f"%{q}%"
    rows = [dict(r) for r in conn.execute("SELECT * FROM medicines WHERE name LIKE ? OR category LIKE ? OR supplier LIKE ? LIMIT 10", (q_like, q_like, q_like)).fetchall()]''',
    text, flags=re.DOTALL
)

# 5. Fix except InvalidId
text = re.sub(
    r'except InvalidId:\s*return jsonify\(\{"error": "Invalid [^"]+"\}\), 400',
    '',
    text
)

# Additional cleanup for missing ObjectId import that causes NameError if eval'd
text = text.replace("ObjectId(mid)", "mid")
text = text.replace("ObjectId(item['id'])", "item['id']")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(text)
