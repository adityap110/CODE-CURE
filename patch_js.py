import os
import re

directories = [r'c:\Users\adity\OneDrive\Desktop\Codecure\templates']
files_to_patch = ['admin_dashboard.html', 'cashier_dashboard.html', 'doctor_dashboard.html', 'pharmacist_dashboard.html', 'index.html']

for dirpath, _, filenames in os.walk(directories[0]):
    for filename in filenames:
        if filename in files_to_patch:
            filepath = os.path.join(dirpath, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # Find all instances of: const variable = await something.json();
            # where the fetch is for /api/medicines, /api/sales, /api/users, /api/suppliers, /api/purchase-orders
            # A simpler approach: Just patch the specific render functions or fetch results
            # For medicines:
            content = re.sub(
                r'(const\s+list\s*=\s*await\s+\w+\.json\(\);)',
                r'\1\n  if(!Array.isArray(list)) { list = list.data; }',
                content
            )
            # Some use data
            # Wait, `const data = await res.json();` in some places.
            content = re.sub(
                r'(const\s+data\s*=\s*await\s+\w+\.json\(\);)(?!\s*if\(!Array)',
                r'\1\n  if(data && !Array.isArray(data) && data.data) { data = data.data; }',
                content
            )

            # Let's be safer: just patch `Array.isArray` immediately after any `.json()` that looks like it assigns to list or data
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

print("Updated JS frontends for backward compatibility")
