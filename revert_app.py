import re

with open('app.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Remove BSON imports
text = text.replace("from bson.objectid import ObjectId\n", "")
text = text.replace("from bson.errors import InvalidId\n", "")

# 2. Change route params back to int
text = re.sub(r'/(<string:mid>)', r'/<int:mid>', text)
text = re.sub(r'except InvalidId:\s+return jsonify\(\{"error": "Invalid [^"]+"\}\), 400\s+', '', text)

# 3. Replace db = get_db() with conn = get_db() globally
text = text.replace('db = get_db()', 'conn = get_db()')

# 4. Fix api_stats
stats_old = """    total = db.medicines.count_documents({})
    ok = db.medicines.count_documents({
        "$expr": {"$gte": ["$quantity", "$min_stock"]},
        "$or": [{"expiry_date": {"$in": [None, ""]}}, {"expiry_date": {"$gt": today}}]
    })
    low = db.medicines.count_documents({
        "$expr": {"$lt": ["$quantity", "$min_stock"]},
        "$or": [{"expiry_date": {"$in": [None, ""]}}, {"expiry_date": {"$gt": today}}]
    })
    expired = db.medicines.count_documents({
        "expiry_date": {"$nin": [None, ""], "$lte": today}
    })"""
stats_new = """    total   = conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]
    ok      = conn.execute("SELECT COUNT(*) FROM medicines WHERE quantity >= min_stock AND (expiry_date IS NULL OR expiry_date = '' OR expiry_date > ?)", (today,)).fetchone()[0]
    low     = conn.execute("SELECT COUNT(*) FROM medicines WHERE quantity < min_stock AND (expiry_date IS NULL OR expiry_date = '' OR expiry_date > ?)", (today,)).fetchone()[0]
    expired = conn.execute("SELECT COUNT(*) FROM medicines WHERE expiry_date != '' AND expiry_date <= ?", (today,)).fetchone()[0]"""
text = text.replace(stats_old, stats_new)

# 5. Fix api_medicines GET
get_meds_old = """    sort_dir_mongo = -1 if sort_dir == "desc" else 1

    conn = get_db()
    query_parts = []
    if search:
        query_parts.append({
            "$or": [
                {"name": {"$regex": search, "$options": "i"}},
                {"category": {"$regex": search, "$options": "i"}},
                {"supplier": {"$regex": search, "$options": "i"}}
            ]
        })

    if filter_type == "low":
        query_parts.append({"$expr": {"$lt": ["$quantity", "$min_stock"]}})
    elif filter_type == "expiring":
        query_parts.append({"expiry_date": {"$gt": today, "$lte": "2025-12-31"}})
    elif filter_type == "expired":
        query_parts.append({"expiry_date": {"$nin": [None, ""], "$lte": today}})
        
    query = {"$and": query_parts} if query_parts else {}

    total = conn.medicines.count_documents(query)
    cursor = conn.medicines.find(query).sort(sort_col, sort_dir_mongo).skip((page-1)*per_page).limit(per_page)
    rows = []
    for r in cursor:
        r["id"] = str(r["_id"])
        del r["_id"]
        rows.append(r)"""
get_meds_new = """    sort_dir = "DESC" if sort_dir == "desc" else "ASC"

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
        where = "WHERE expiry_date != '' AND expiry_date <= ?" + base_where
        params = [today] + params
    else:
        where = "WHERE 1=1" + base_where

    total = conn.execute(f"SELECT COUNT(*) FROM medicines {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM medicines {where} ORDER BY {sort_col} {sort_dir} LIMIT ? OFFSET ?",
        params + [per_page, (page-1)*per_page]
    ).fetchall()
    rows = [dict(r) for r in rows]"""
text = text.replace(get_meds_old, get_meds_new)

# 6. Fix api_medicines POST
post_meds_old = """        conn.medicines.insert_one({
            "name": clean["name"],
            "category": clean.get("category", ""),
            "quantity": safe_int(data.get("quantity", 0)),
            "min_stock": safe_int(data.get("min_stock", 10)),
            "expiry_date": clean.get("expiry_date", ""),
            "supplier": clean.get("supplier", ""),
            "price": safe_float(data.get("price", 0)),
            "created_at": datetime.utcnow().isoformat()
        })"""
post_meds_new = """        conn.execute(
            "INSERT INTO medicines (name,category,quantity,min_stock,expiry_date,supplier,price,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (clean["name"], clean.get("category",""), safe_int(data.get("quantity",0)),
             safe_int(data.get("min_stock",10)), clean.get("expiry_date",""),
             clean.get("supplier",""), safe_float(data.get("price",0)), datetime.utcnow().isoformat())
        )
        conn.commit()"""
text = text.replace(post_meds_old, post_meds_new)

# 7. Fix api_medicines PUT
put_meds_old = """        conn.medicines.update_one(
            {"_id": ObjectId(mid)},
            {"$set": {
                "name": clean["name"],
                "category": clean.get("category", ""),
                "quantity": safe_int(data.get("quantity", 0)),
                "min_stock": safe_int(data.get("min_stock", 10)),
                "expiry_date": clean.get("expiry_date", ""),
                "supplier": clean.get("supplier", ""),
                "price": safe_float(data.get("price", 0))
            }}
        )"""
put_meds_new = """        conn.execute(
            "UPDATE medicines SET name=?,category=?,quantity=?,min_stock=?,expiry_date=?,supplier=?,price=? WHERE id=?",
            (clean["name"], clean.get("category",""), safe_int(data.get("quantity",0)),
             safe_int(data.get("min_stock",10)), clean.get("expiry_date",""),
             clean.get("supplier",""), safe_float(data.get("price",0)), mid)
        )
        conn.commit()"""
text = text.replace(put_meds_old, put_meds_new)

# 8. Fix api_medicines DELETE
del_meds_old = """        row = conn.medicines.find_one_and_delete({"_id": ObjectId(mid)})
        if row:
            log_activity("Delete Medicine", row["name"], session["user"])
        return jsonify({"success": True})"""
del_meds_new = """        row = conn.execute("SELECT name FROM medicines WHERE id=?", (mid,)).fetchone()
        if not row:
            return jsonify({"error": "Medicine not found"}), 404
        conn.execute("DELETE FROM medicines WHERE id=?", (mid,))
        conn.commit()
        log_activity("Delete Medicine", row["name"], session["user"])
        return jsonify({"success": True})"""
text = text.replace(del_meds_old, del_meds_new)

# 9. Fix Alerts
alerts_old = """    low = list(conn.medicines.find({"$expr": {"$lt": ["$quantity", "$min_stock"]}}))
    expired = list(conn.medicines.find({"expiry_date": {"$nin": [None, ""], "$lte": today}}))
    expiring = list(conn.medicines.find({"expiry_date": {"$gt": today, "$lte": warn_date}}))
    out = list(conn.medicines.find({"quantity": 0}))
    
    alerts = []
    for r in out:
        alerts.append({"id": str(r["_id"]),"type":"out","severity":"critical","name":r["name"],"detail":"Out of stock!"})
    for r in expired:
        alerts.append({"id": str(r["_id"]),"type":"expired","severity":"critical","name":r["name"],"detail":f"Expired on {r['expiry_date']}"})
    for r in low:
        if r["quantity"] > 0:
            alerts.append({"id": str(r["_id"]),"type":"low","severity":"warning","name":r["name"],"detail":f"Only {r['quantity']} left (min {r['min_stock']})","quantity":r["quantity"],"min_stock":r["min_stock"]})
    for r in expiring:
        d = days_until_expiry(r["expiry_date"])
        alerts.append({"id": str(r["_id"]),"type":"expiring","severity":"warning","name":r["name"],"detail":f"Expires in {d} day(s)"})"""
alerts_new = """    low     = conn.execute("SELECT id,name,quantity,min_stock FROM medicines WHERE quantity < min_stock").fetchall()
    expired = conn.execute("SELECT id,name,expiry_date FROM medicines WHERE expiry_date != '' AND expiry_date <= ?", (today,)).fetchall()
    expiring = conn.execute("SELECT id,name,expiry_date FROM medicines WHERE expiry_date > ? AND expiry_date <= ?", (today, warn_date)).fetchall()
    out     = conn.execute("SELECT id,name FROM medicines WHERE quantity = 0").fetchall()
    
    alerts = []
    for r in out:
        alerts.append({"id":r["id"],"type":"out","severity":"critical","name":r["name"],"detail":"Out of stock!"})
    for r in expired:
        alerts.append({"id":r["id"],"type":"expired","severity":"critical","name":r["name"],"detail":f"Expired on {r['expiry_date']}"})
    for r in low:
        if r["quantity"] > 0:
            alerts.append({"id":r["id"],"type":"low","severity":"warning","name":r["name"],"detail":f"Only {r['quantity']} left (min {r['min_stock']})","quantity":r["quantity"],"min_stock":r["min_stock"]})
    for r in expiring:
        d = days_until_expiry(r["expiry_date"])
        alerts.append({"id":r["id"],"type":"expiring","severity":"warning","name":r["name"],"detail":f"Expires in {d} day(s)"})"""
text = text.replace(alerts_old, alerts_new)

# 10. Fix Restock
restock_old = """        row = conn.medicines.find_one({"_id": ObjectId(mid)})
        if not row:
            return jsonify({"error": "Medicine not found"}), 404
        new_qty = safe_int(data.get("quantity", 0))
        if new_qty <= 0:
            new_qty = row["min_stock"] * 2  # Default: double the minimum
        conn.medicines.update_one({"_id": ObjectId(mid)}, {"$set": {"quantity": new_qty}})
        log_activity("Restock", f"{row['name']} restocked to {new_qty} units", session["user"])
        return jsonify({"success": True, "name": row["name"], "new_quantity": new_qty})"""
restock_new = """        row = conn.execute("SELECT name, min_stock FROM medicines WHERE id=?", (mid,)).fetchone()
        if not row:
            return jsonify({"error": "Medicine not found"}), 404
        new_qty = safe_int(data.get("quantity", 0))
        if new_qty <= 0:
            new_qty = row["min_stock"] * 2  # Default: double the minimum
        conn.execute("UPDATE medicines SET quantity=? WHERE id=?", (new_qty, mid))
        conn.commit()
        log_activity("Restock", f"{row['name']} restocked to {new_qty} units", session["user"])
        return jsonify({"success": True, "name": row["name"], "new_quantity": new_qty})"""
text = text.replace(restock_old, restock_new)

# 11. Fix Discard
discard_old = """        row = conn.medicines.find_one({"_id": ObjectId(mid)})
        if not row:
            return jsonify({"error": "Medicine not found"}), 404
        conn.medicines.update_one({"_id": ObjectId(mid)}, {"$set": {"quantity": 0}})
        log_activity("Discard", f"{row['name']} discarded ({row['quantity']} units removed)", session["user"])
        return jsonify({"success": True, "name": row["name"], "discarded_qty": row["quantity"]})"""
discard_new = """        row = conn.execute("SELECT name, quantity FROM medicines WHERE id=?", (mid,)).fetchone()
        if not row:
            return jsonify({"error": "Medicine not found"}), 404
        conn.execute("UPDATE medicines SET quantity=0 WHERE id=?", (mid,))
        conn.commit()
        log_activity("Discard", f"{row['name']} discarded ({row['quantity']} units removed)", session["user"])
        return jsonify({"success": True, "name": row["name"], "discarded_qty": row["quantity"]})"""
text = text.replace(discard_old, discard_new)

# 12. Fix api_activity
act_old = """    rows = list(conn.activity.find().sort("timestamp", -1).limit(20))
    for r in rows:
        r["id"] = str(r["_id"])
        del r["_id"]"""
act_new = """    rows = [dict(r) for r in conn.execute("SELECT * FROM activity ORDER BY timestamp DESC LIMIT 20").fetchall()]"""
text = text.replace(act_old, act_new)

# 13. Fix Cart Get
cart_get_old = """        try:
            m = conn.medicines.find_one({"_id": ObjectId(item["id"])})
            if m and m["quantity"] >= item["qty"]:
                cart_items.append({
                    "id": str(m["_id"]), "name": m["name"], "price": m["price"],
                    "qty": item["qty"], "subtotal": m["price"] * item["qty"]
                })
        except:
            pass"""
cart_get_new = """        m = conn.execute("SELECT id, name, price, quantity FROM medicines WHERE id=?", (item["id"],)).fetchone()
        if m and m["quantity"] >= item["qty"]:
            cart_items.append({
                "id": m["id"], "name": m["name"], "price": m["price"],
                "qty": item["qty"], "subtotal": m["price"] * item["qty"]
            })"""
text = text.replace(cart_get_old, cart_get_new)

# 14. Fix Cart Add
cart_add_old = """        m = conn.medicines.find_one({"_id": ObjectId(mid)})
        if not m:
            return jsonify({"error": "Medicine not found"}), 404
        if m["quantity"] < qty:
            return jsonify({"error": f"Insufficient stock. Only {m['quantity']} available."}), 400"""
cart_add_new = """        m = conn.execute("SELECT quantity FROM medicines WHERE id=?", (mid,)).fetchone()
        if not m:
            return jsonify({"error": "Medicine not found"}), 404
        if m["quantity"] < qty:
            return jsonify({"error": f"Insufficient stock. Only {m['quantity']} available."}), 400"""
text = text.replace(cart_add_old, cart_add_new)

# 15. Fix Checkout
chk_old = """            m = conn.medicines.find_one({"_id": ObjectId(mid)})
            if not m or m["quantity"] < qty:
                return jsonify({"error": f"Insufficient stock for {m['name'] if m else 'unknown'}"}), 400
            conn.medicines.update_one({"_id": ObjectId(mid)}, {"$inc": {"quantity": -qty}})"""
chk_new = """            m = conn.execute("SELECT name, price, quantity FROM medicines WHERE id=?", (mid,)).fetchone()
            if not m or m["quantity"] < qty:
                return jsonify({"error": f"Insufficient stock for {m['name'] if m else 'unknown'}"}), 400
            conn.execute("UPDATE medicines SET quantity = quantity - ? WHERE id=?", (qty, mid))"""
text = text.replace(chk_old, chk_new)

# 16. Fix API Export
exp_old = """    rows = list(conn.medicines.find().sort("name", 1))"""
exp_new = """    rows = conn.execute("SELECT * FROM medicines ORDER BY name ASC").fetchall()"""
text = text.replace(exp_old, exp_new)
text = text.replace('        row_dict = dict(r)\n        row_dict["id"] = str(row_dict.pop("_id"))', '        row_dict = dict(r)')

# 17. Fix Reports Dashboard
rep_old = """    thirty_days_ago = (date.today() - timedelta(days=30)).isoformat()
    
    pipeline = [
        {"$match": {"timestamp": {"$gte": thirty_days_ago}}},
        {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}}
    ]
    result = list(conn.sales.aggregate(pipeline))
    rev_30 = result[0]["total"] if result else 0

    pipeline = [
        {"$match": {"timestamp": {"$gte": today}}},
        {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}}
    ]
    result = list(conn.sales.aggregate(pipeline))
    rev_today = result[0]["total"] if result else 0

    rows = list(conn.medicines.find({
        "$expr": {"$lt": ["$quantity", "$min_stock"]}
    }))
    low_stock = len(rows)"""
rep_new = """    thirty_days_ago = (date.today() - timedelta(days=30)).isoformat()
    
    rev_30 = conn.execute("SELECT SUM(total_amount) FROM sales WHERE timestamp >= ?", (thirty_days_ago,)).fetchone()[0] or 0
    rev_today = conn.execute("SELECT SUM(total_amount) FROM sales WHERE timestamp >= ?", (today,)).fetchone()[0] or 0
    low_stock = conn.execute("SELECT COUNT(*) FROM medicines WHERE quantity < min_stock").fetchone()[0]"""
text = text.replace(rep_old, rep_new)

# 18. Fix Sales Report
sales_old = """    pipeline = [
        {"$match": {"timestamp": {"$gte": thirty_days_ago}}},
        {"$group": {
            "_id": {"$substr": ["$timestamp", 0, 10]},
            "revenue": {"$sum": "$total_amount"}
        }},
        {"$sort": {"_id": 1}}
    ]
    rows = list(conn.sales.aggregate(pipeline))
    sales_data = [{"date": r["_id"], "revenue": r["revenue"]} for r in rows]

    sales = list(conn.sales.find({"timestamp": {"$gte": thirty_days_ago}}, {"items_json": 1}))"""
sales_new = """    rows = conn.execute('''
        SELECT SUBSTR(timestamp, 1, 10) as date, SUM(total_amount) as revenue
        FROM sales
        WHERE timestamp >= ?
        GROUP BY SUBSTR(timestamp, 1, 10)
        ORDER BY date ASC
    ''', (thirty_days_ago,)).fetchall()
    sales_data = [{"date": r["date"], "revenue": r["revenue"]} for r in rows]

    sales = conn.execute("SELECT items_json FROM sales WHERE timestamp >= ?", (thirty_days_ago,)).fetchall()"""
text = text.replace(sales_old, sales_new)

# 19. Fix Chatbot logic
chat_old = """    total = conn.medicines.count_documents({})
    low = conn.medicines.count_documents({"$expr": {"$lt": ["$quantity", "$min_stock"]}})
    expired = conn.medicines.count_documents({"expiry_date": {"$nin": [None, ""], "$lte": today}})
    
    low_items = list(conn.medicines.find({
        "$expr": {"$lt": ["$quantity", "$min_stock"]}
    }, {"name": 1, "quantity": 1}))
    
    exp_items = list(conn.medicines.find({
        "expiry_date": {"$nin": [None, ""], "$lte": today}
    }, {"name": 1, "expiry_date": 1}))"""
chat_new = """    total = conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]
    low = conn.execute("SELECT COUNT(*) FROM medicines WHERE quantity < min_stock").fetchone()[0]
    expired = conn.execute("SELECT COUNT(*) FROM medicines WHERE expiry_date != '' AND expiry_date <= ?", (today,)).fetchone()[0]
    
    low_items = conn.execute("SELECT name, quantity FROM medicines WHERE quantity < min_stock").fetchall()
    exp_items = conn.execute("SELECT name, expiry_date FROM medicines WHERE expiry_date != '' AND expiry_date <= ?", (today,)).fetchall()"""
text = text.replace(chat_old, chat_new)

# Also fix the general "from config import Config" and "from models import ..."
# The models import should be get_db, init_db, log_activity, record_sale
# That's already there!

# Commit the transaction after checkout
text = text.replace('conn.execute("UPDATE medicines SET quantity = quantity - ? WHERE id=?", (qty, mid))', 'conn.execute("UPDATE medicines SET quantity = quantity - ? WHERE id=?", (qty, mid))\n        conn.commit()')

# Write back
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Done replacing PyMongo with SQLite.")
