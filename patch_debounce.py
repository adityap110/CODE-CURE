import os
import re

def update_file(filepath, replacements):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for old, new in replacements:
        content = content.replace(old, new)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def main():
    admin_path = r'c:\Users\adity\OneDrive\Desktop\Codecure\templates\admin_dashboard.html'
    ph_path = r'c:\Users\adity\OneDrive\Desktop\Codecure\templates\pharmacist_dashboard.html'

    # Admin Dashboard
    admin_replacements = [
        ('oninput="filterAdminInventory()"', 'oninput="debouncedFilterAdminInventory()"'),
        ('oninput="filterAdminSales()"', 'oninput="debouncedFilterAdminSales()"'),
        ('oninput="filterAdminUsers()"', 'oninput="debouncedFilterAdminUsers()"'),
        ('function filterAdminInventory()', 'const debouncedFilterAdminInventory = debounce(filterAdminInventory, 300);\nfunction filterAdminInventory()'),
        ('function filterAdminSales()', 'const debouncedFilterAdminSales = debounce(filterAdminSales, 300);\nfunction filterAdminSales()'),
        ('function filterAdminUsers()', 'const debouncedFilterAdminUsers = debounce(filterAdminUsers, 300);\nfunction filterAdminUsers()')
    ]
    update_file(admin_path, admin_replacements)

    # Pharmacist Dashboard
    ph_replacements = [
        ('oninput="filterPhInventory()"', 'oninput="debouncedFilterPhInventory()"'),
        ('function filterPhInventory()', 'const debouncedFilterPhInventory = debounce(filterPhInventory, 300);\nfunction filterPhInventory()')
    ]
    update_file(ph_path, ph_replacements)

if __name__ == '__main__':
    main()
    print("Debounce applied.")
