with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip_until = -1
for i, line in enumerate(lines):
    if i < skip_until:
        continue
        
    if 'total = conn.medicines.count_documents({})' in line:
        new_lines.append(line.replace('conn.medicines.count_documents({})', 'conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]'))
        
    elif 'low = list(conn.medicines.find({"$expr": {"$lt": ["$quantity", "$min_stock"]}}))' in line:
        new_lines.append('    low = conn.execute("SELECT id,name,quantity,min_stock FROM medicines WHERE quantity < min_stock").fetchall()\n')
    elif 'expired = list(conn.medicines.find({"expiry_date": {"$nin": [None, ""], "$lte": today}}))' in line:
        new_lines.append('    expired = conn.execute("SELECT id,name,expiry_date FROM medicines WHERE expiry_date != \'\' AND expiry_date <= ?", (today,)).fetchall()\n')
    elif 'expiring = list(conn.medicines.find({"expiry_date": {"$gt": today, "$lte": warn_date}}))' in line:
        new_lines.append('    expiring = conn.execute("SELECT id,name,expiry_date FROM medicines WHERE expiry_date > ? AND expiry_date <= ?", (today, warn_date)).fetchall()\n')
    elif 'out = list(conn.medicines.find({"quantity": 0}))' in line:
        new_lines.append('    out = conn.execute("SELECT id,name FROM medicines WHERE quantity = 0").fetchall()\n')
        
    elif 'row = conn.medicines.find_one({"_id": ObjectId(mid)})' in line:
        if 'quantity' in lines[i+1]: # Discard
            new_lines.append('        row = conn.execute("SELECT name, quantity FROM medicines WHERE id=?", (mid,)).fetchone()\n')
        elif i+2 < len(lines) and 'new_qty' in lines[i+2] or i+3 < len(lines) and 'new_qty' in lines[i+3]: # Restock
            new_lines.append('        row = conn.execute("SELECT name, min_stock FROM medicines WHERE id=?", (mid,)).fetchone()\n')
        else: # Generic
            new_lines.append('        row = conn.execute("SELECT * FROM medicines WHERE id=?", (mid,)).fetchone()\n')
            
    elif 'conn.medicines.update_one({"_id": ObjectId(mid)}, {"$set": {"quantity": new_qty}})' in line:
        new_lines.append('        conn.execute("UPDATE medicines SET quantity=? WHERE id=?", (new_qty, mid))\n        conn.commit()\n')
        
    elif 'conn.medicines.update_one({"_id": ObjectId(mid)}, {"$set": {"quantity": 0}})' in line:
        new_lines.append('        conn.execute("UPDATE medicines SET quantity=0 WHERE id=?", (mid,))\n        conn.commit()\n')
        
    elif 'rows = list(conn.medicines.find().sort("name", 1))' in line:
        new_lines.append('    rows = conn.execute("SELECT * FROM medicines ORDER BY name ASC").fetchall()\n')
        
    elif 'rows = list(conn.medicines.find({' in line and i+1 < len(lines) and '"$expr": {"$lt": ["$quantity", "$min_stock"]}' in lines[i+1]:
        new_lines.append('    low_stock = conn.execute("SELECT COUNT(*) FROM medicines WHERE quantity < min_stock").fetchone()[0]\n')
        skip_until = i + 3
        
    elif 'pipeline = [' in line and i+1 < len(lines) and 'thirty_days_ago' in lines[i+1]:
        if i+3 < len(lines) and '"revenue"' in lines[i+3]: # Sales
            new_lines.append('''    rows = conn.execute("""
        SELECT SUBSTR(timestamp, 1, 10) as date, SUM(total_amount) as revenue
        FROM sales
        WHERE timestamp >= ?
        GROUP BY SUBSTR(timestamp, 1, 10)
        ORDER BY date ASC
    """, (thirty_days_ago,)).fetchall()
    sales_data = [{"date": r["date"], "revenue": r["revenue"]} for r in rows]
    sales = conn.execute("SELECT items_json FROM sales WHERE timestamp >= ?", (thirty_days_ago,)).fetchall()\n''')
            skip_until = i + 10
        else: # Dashboard
            new_lines.append('    rev_30 = conn.execute("SELECT SUM(total_amount) FROM sales WHERE timestamp >= ?", (thirty_days_ago,)).fetchone()[0] or 0\n')
            new_lines.append('    rev_today = conn.execute("SELECT SUM(total_amount) FROM sales WHERE timestamp >= ?", (today,)).fetchone()[0] or 0\n')
            skip_until = i + 11
            
    elif 'm = conn.medicines.find_one({"_id": ObjectId(item["id"])})' in line:
        new_lines.append('            m = conn.execute("SELECT id, name, price, quantity FROM medicines WHERE id=?", (item["id"],)).fetchone()\n')
        
    elif 'm = conn.medicines.find_one({"_id": ObjectId(mid)})' in line:
        if i+2 < len(lines) and 'qty' in lines[i+2] and 'update_one' in lines[i+3]: # Checkout
            new_lines.append('            m = conn.execute("SELECT name, price, quantity FROM medicines WHERE id=?", (mid,)).fetchone()\n')
        else: # Cart add
            new_lines.append('        m = conn.execute("SELECT quantity FROM medicines WHERE id=?", (mid,)).fetchone()\n')
            
    elif 'conn.medicines.update_one({"_id": ObjectId(mid)}, {"$inc": {"quantity": -qty}})' in line:
        new_lines.append('            conn.execute("UPDATE medicines SET quantity = quantity - ? WHERE id=?", (qty, mid))\n            conn.commit()\n')
        
    elif 'low = conn.medicines.count_documents({"$expr": {"$lt": ["$quantity", "$min_stock"]}})' in line:
        new_lines.append('        low = conn.execute("SELECT COUNT(*) FROM medicines WHERE quantity < min_stock").fetchone()[0]\n')
        
    elif 'expired = conn.medicines.count_documents({"expiry_date": {"$nin": [None, ""], "$lte": today}})' in line:
        new_lines.append('        expired = conn.execute("SELECT COUNT(*) FROM medicines WHERE expiry_date != \'\' AND expiry_date <= ?", (today,)).fetchone()[0]\n')
        
    elif 'low_items = list(conn.medicines.find({' in line and i+1 < len(lines) and '"$expr": {"$lt": ["$quantity", "$min_stock"]}' in lines[i+1]:
        new_lines.append('        low_items = [dict(r) for r in conn.execute("SELECT name, quantity FROM medicines WHERE quantity < min_stock").fetchall()]\n')
        skip_until = i + 3
        
    elif 'exp_items = list(conn.medicines.find({' in line and i+1 < len(lines) and '"expiry_date": {"$nin": [None, ""], "$lte": today}' in lines[i+1]:
        new_lines.append('        exp_items = [dict(r) for r in conn.execute("SELECT name, expiry_date FROM medicines WHERE expiry_date != \'\' AND expiry_date <= ?", (today,)).fetchall()]\n')
        skip_until = i + 3

    elif 'r["id"] = str(r["_id"])' in line or 'del r["_id"]' in line:
        continue # Skip

    else:
        new_lines.append(line)

code = ''.join(new_lines)
code = code.replace("from bson.objectid import ObjectId\n", "")
code = code.replace("from bson.errors import InvalidId\n", "")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(code)

print('Success')
