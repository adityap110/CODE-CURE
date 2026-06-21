import re

with open('app.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Make sure we start from a clean slate where the variable is 'conn'
text = text.replace('db.medicines', 'conn.medicines')
text = text.replace('db.sales', 'conn.sales')
text = text.replace('db.activity', 'conn.activity')
text = text.replace('db.users', 'conn.users')
text = text.replace('db = get_db()', 'conn = get_db()')

# 5. Fix api_medicines GET
text = re.sub(
    r'total = conn\.medicines\.count_documents\(query\).*?rows\.append\(r\)',
    '''total = conn.execute(f"SELECT COUNT(*) FROM medicines {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM medicines {where} ORDER BY {sort_col} {sort_dir} LIMIT ? OFFSET ?",
        params + [per_page, (page-1)*per_page]
    ).fetchall()
    rows = [dict(r) for r in rows]''',
    text, flags=re.DOTALL
)

# 6. Fix api_medicines POST
text = re.sub(
    r'conn\.medicines\.insert_one\(\{.*?"created_at": datetime\.utcnow\(\)\.isoformat\(\)\s*\}\)',
    '''conn.execute(
            "INSERT INTO medicines (name,category,quantity,min_stock,expiry_date,supplier,price,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (clean["name"], clean.get("category",""), safe_int(data.get("quantity",0)),
             safe_int(data.get("min_stock",10)), clean.get("expiry_date",""),
             clean.get("supplier",""), safe_float(data.get("price",0)), datetime.utcnow().isoformat())
        )
        conn.commit()''',
    text, flags=re.DOTALL
)

# 7. Fix api_medicines PUT
text = re.sub(
    r'conn\.medicines\.update_one\(\s*\{"_id": ObjectId\(mid\)\},\s*\{"\$set": \{.*?\}\s*\)\s*',
    '''conn.execute(
            "UPDATE medicines SET name=?,category=?,quantity=?,min_stock=?,expiry_date=?,supplier=?,price=? WHERE id=?",
            (clean["name"], clean.get("category",""), safe_int(data.get("quantity",0)),
             safe_int(data.get("min_stock",10)), clean.get("expiry_date",""),
             clean.get("supplier",""), safe_float(data.get("price",0)), mid)
        )
        conn.commit()\n''',
    text, flags=re.DOTALL
)

# 8. Fix api_medicines DELETE
text = re.sub(
    r'row = conn\.medicines\.find_one_and_delete\(\{"_id": ObjectId\(mid\)\}\)\s*if row:\s*log_activity\("Delete Medicine", row\["name"\], session\["user"\]\)\s*return jsonify\(\{"success": True\}\)',
    '''row = conn.execute("SELECT name FROM medicines WHERE id=?", (mid,)).fetchone()
        if not row:
            return jsonify({"error": "Medicine not found"}), 404
        conn.execute("DELETE FROM medicines WHERE id=?", (mid,))
        conn.commit()
        log_activity("Delete Medicine", row["name"], session["user"])
        return jsonify({"success": True})''',
    text, flags=re.DOTALL
)

# 10. Fix Restock
text = re.sub(
    r'row = conn\.medicines\.find_one\(\{"_id": ObjectId\(mid\)\}\)\s*if not row:.*?conn\.medicines\.update_one\(\{"_id": ObjectId\(mid\)\}, \{"\$set": \{"quantity": new_qty\}\}\)',
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

# 11. Fix Discard
text = re.sub(
    r'row = conn\.medicines\.find_one\(\{"_id": ObjectId\(mid\)\}\)\s*if not row:.*?conn\.medicines\.update_one\(\{"_id": ObjectId\(mid\)\}, \{"\$set": \{"quantity": 0\}\}\)',
    '''row = conn.execute("SELECT name, quantity FROM medicines WHERE id=?", (mid,)).fetchone()
        if not row:
            return jsonify({"error": "Medicine not found"}), 404
        conn.execute("UPDATE medicines SET quantity=0 WHERE id=?", (mid,))
        conn.commit()''',
    text, flags=re.DOTALL
)

# 13. Fix Cart Get
text = re.sub(
    r'm = conn\.medicines\.find_one\(\{"_id": ObjectId\(item\["id"\]\)\}\)',
    'm = conn.execute("SELECT id, name, price, quantity FROM medicines WHERE id=?", (item["id"],)).fetchone()',
    text
)

# 14. Fix Cart Add
text = re.sub(
    r'm = conn\.medicines\.find_one\(\{"_id": ObjectId\(mid\)\}\)',
    'm = conn.execute("SELECT quantity FROM medicines WHERE id=?", (mid,)).fetchone()',
    text
)

# 15. Fix Checkout
text = re.sub(
    r'conn\.medicines\.update_one\(\{"_id": ObjectId\(mid\)\}, \{"\$inc": \{"quantity": -qty\}\}\)',
    '''conn.execute("UPDATE medicines SET quantity = quantity - ? WHERE id=?", (qty, mid))
            conn.commit()''',
    text
)

# 19. Fix Chatbot logic
text = re.sub(
    r'total = conn\.medicines\.count_documents\(\{\}\)\s*low = conn\.medicines\.count_documents\(\{"\$expr": \{"\$lt": \["\$quantity", "\$min_stock"\]\}\}\)\s*expired = conn\.medicines\.count_documents\(\{"expiry_date": \{"\$nin": \[None, ""\], "\$lte": today\}\}\)',
    '''total = conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]
        low = conn.execute("SELECT COUNT(*) FROM medicines WHERE quantity < min_stock").fetchone()[0]
        expired = conn.execute("SELECT COUNT(*) FROM medicines WHERE expiry_date != '' AND expiry_date <= ?", (today,)).fetchone()[0]''',
    text, flags=re.DOTALL
)

# Clean up remaining bson imports
text = text.replace("from bson.objectid import ObjectId\n", "")
text = text.replace("from bson.errors import InvalidId\n", "")
text = re.sub(r'except InvalidId:\s*return jsonify\(\{"error": "Invalid [^"]+"\}\), 400', '', text)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(text)
