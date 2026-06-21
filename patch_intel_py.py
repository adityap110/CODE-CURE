import os
import re

file_path = r'c:\Users\adity\OneDrive\Desktop\Codecure\intelligence_service.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update query calls
content = content.replace(
    'medicines = Medicine.query.all()',
    'medicines = Medicine.query.yield_per(1000)'
)
content = content.replace(
    'batches = MedicineBatch.query.filter(MedicineBatch.quantity > 0).all()',
    'batches = MedicineBatch.query.filter(MedicineBatch.quantity > 0).yield_per(1000)'
)

# 2. Add page/page_size parameters
content = re.sub(
    r'def calculate_intelligence\(db_session, Medicine, MedicineBatch, Sale\):',
    r'def calculate_intelligence(db_session, Medicine, MedicineBatch, Sale, page=1, page_size=100):',
    content
)

# 3. Paginate results right before health score
paginate_logic = """
    # Paginate lists to preserve memory and network transfer
    for key in ["runouts", "reorders", "slow_moving", "dead_stock", "expiry_risks"]:
        total_records = len(results[key])
        start = (page - 1) * page_size
        end = start + page_size
        sliced_data = results[key][start:end]
        results[key] = {
            "data": sliced_data,
            "page": page,
            "page_size": page_size,
            "total_records": total_records
        }

    # Calculate Health Score
"""

content = content.replace(
    '    # Calculate Health Score',
    paginate_logic
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated intelligence_service.py")
