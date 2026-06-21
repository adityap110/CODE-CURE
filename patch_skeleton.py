import os

file_path = r'c:\Users\adity\OneDrive\Desktop\Codecure\templates\admin_dashboard.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Users: 5 columns
content = content.replace(
    '<td colspan="5" style="text-align:center;color:var(--muted);padding:30px">Loading…</td>',
    '<td colspan="5"><div class="skeleton" style="width:100%;height:40px;margin-bottom:10px;"></div><div class="skeleton" style="width:100%;height:40px;margin-bottom:10px;"></div><div class="skeleton" style="width:100%;height:40px;"></div></td>'
)

# Suppliers: 5 columns
content = content.replace(
    '<td colspan="5" class="empty-state">Loading...</td>',
    '<td colspan="5"><div class="skeleton" style="width:100%;height:40px;margin-bottom:10px;"></div><div class="skeleton" style="width:100%;height:40px;margin-bottom:10px;"></div><div class="skeleton" style="width:100%;height:40px;"></div></td>'
)

# Sales History: 6 columns
content = content.replace(
    '<td colspan="6" style="text-align:center;color:var(--muted);padding:30px">Loading…</td>',
    '<td colspan="6"><div class="skeleton" style="width:100%;height:40px;margin-bottom:10px;"></div><div class="skeleton" style="width:100%;height:40px;margin-bottom:10px;"></div><div class="skeleton" style="width:100%;height:40px;"></div></td>'
)

# Inventory Intelligence? Let's check how it's defined. Wait, what are the tables inside Intelligence?
# I'll just write the updated content back for now.
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated admin_dashboard.html")
