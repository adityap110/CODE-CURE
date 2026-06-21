import os
import re

file_path = r'c:\Users\adity\OneDrive\Desktop\Codecure\app.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. /api/suppliers
content = re.sub(
    r'suppliers = Supplier\.query\.all\(\)',
    r'page = safe_int(request.args.get("page", 1), default=1, minimum=1)\n    per_page = safe_int(request.args.get("per_page", 50), default=50, minimum=1, maximum=200)\n    query = Supplier.query\n    total = query.count()\n    suppliers = query.limit(per_page).offset((page - 1) * per_page).all()',
    content
)
content = re.sub(
    r'return jsonify\(data\)(?=\s*@app\.route\("/api/suppliers", methods=\["POST"\]\))',
    r'return jsonify({"data": data, "page": page, "page_size": per_page, "total_records": total})',
    content
)

# 2. /api/purchase-orders
content = re.sub(
    r'pos = PurchaseOrder\.query\.order_by\(PurchaseOrder\.id\.desc\(\)\)\.all\(\)',
    r'page = safe_int(request.args.get("page", 1), default=1, minimum=1)\n    per_page = safe_int(request.args.get("per_page", 50), default=50, minimum=1, maximum=200)\n    query = PurchaseOrder.query.order_by(PurchaseOrder.id.desc())\n    total = query.count()\n    pos = query.limit(per_page).offset((page - 1) * per_page).all()',
    content
)
content = re.sub(
    r'return jsonify\(data\)(?=\s*@app\.route\("/api/purchase-orders/from-intelligence")',
    r'return jsonify({"data": data, "page": page, "page_size": per_page, "total_records": total})',
    content
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated app.py with pagination for suppliers and purchase-orders")
