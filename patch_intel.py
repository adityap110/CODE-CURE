import os

file_path = r'c:\Users\adity\OneDrive\Desktop\Codecure\templates\admin_dashboard.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Runouts
content = content.replace(
    '<tbody id="intel-tbody-runouts"></tbody>',
    '<tbody id="intel-tbody-runouts"><tr><td colspan="5"><div class="skeleton" style="width:100%;height:30px;margin-bottom:8px;"></div><div class="skeleton" style="width:100%;height:30px;"></div></td></tr></tbody>'
)

# Reorders
content = content.replace(
    '<tbody id="intel-tbody-reorders"></tbody>',
    '<tbody id="intel-tbody-reorders"><tr><td colspan="6"><div class="skeleton" style="width:100%;height:30px;margin-bottom:8px;"></div><div class="skeleton" style="width:100%;height:30px;"></div></td></tr></tbody>'
)

# Slow
content = content.replace(
    '<tbody id="intel-tbody-slow"></tbody>',
    '<tbody id="intel-tbody-slow"><tr><td colspan="3"><div class="skeleton" style="width:100%;height:30px;margin-bottom:8px;"></div><div class="skeleton" style="width:100%;height:30px;"></div></td></tr></tbody>'
)

# Dead
content = content.replace(
    '<tbody id="intel-tbody-dead"></tbody>',
    '<tbody id="intel-tbody-dead"><tr><td colspan="3"><div class="skeleton" style="width:100%;height:30px;margin-bottom:8px;"></div><div class="skeleton" style="width:100%;height:30px;"></div></td></tr></tbody>'
)

# Expiry
content = content.replace(
    '<tbody id="intel-tbody-expiry"></tbody>',
    '<tbody id="intel-tbody-expiry"><tr><td colspan="5"><div class="skeleton" style="width:100%;height:30px;margin-bottom:8px;"></div><div class="skeleton" style="width:100%;height:30px;"></div></td></tr></tbody>'
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated admin_dashboard.html intelligence tables")
