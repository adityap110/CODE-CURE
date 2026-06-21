import os
import re

file_path = r'c:\Users\adity\OneDrive\Desktop\Codecure\templates\admin_dashboard.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace data.runouts.length with (data.runouts.data || data.runouts).length
tables = ['runouts', 'reorders', 'slow_moving', 'dead_stock', 'expiry_risks']

for t in tables:
    content = re.sub(
        rf'data\.{t}\.length',
        f'(data.{t}.data || data.{t}).length',
        content
    )
    content = re.sub(
        rf'data\.{t}\.map',
        f'(data.{t}.data || data.{t}).map',
        content
    )

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated admin_dashboard.html intelligence mapping")
