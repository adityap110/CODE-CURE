import os, re
basedir = r'c:\Users\adity\OneDrive\Desktop\Codecure\templates'
for f in os.listdir(basedir):
    if not f.endswith('.html'): continue
    path = os.path.join(basedir, f)
    with open(path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Replace empty-icon emoji blocks with the logo
    new_content, n = re.subn(
        r'<div class="empty-state">\s*<div class="empty-icon">.*?</div>\s*Loading.*?</div>',
        r'<div class="empty-state"><img src="{{ url_for(\'static\', filename=\'images/logo_icon.png\') }}" class="loading-brand-icon logo-sm" style="margin-bottom:12px;" alt="CC+"><br>Loading CodeCure...</div>',
        content,
        flags=re.DOTALL
    )
    
    # Also replace standard table loading text
    new_content2, n2 = re.subn(
        r'>Loading…</td>',
        r'><div style="display:flex; justify-content:center; align-items:center; gap:8px;"><img src="{{ url_for(\'static\', filename=\'images/logo_icon.png\') }}" class="loading-brand-icon logo-xs"> Loading CodeCure...</div></td>',
        new_content
    )
    new_content2, n3 = re.subn(
        r'>Loading batches...</td>',
        r'><div style="display:flex; justify-content:center; align-items:center; gap:8px;"><img src="{{ url_for(\'static\', filename=\'images/logo_icon.png\') }}" class="loading-brand-icon logo-xs"> Loading CodeCure...</div></td>',
        new_content2
    )
    
    if n > 0 or n2 > 0 or n3 > 0:
        with open(path, 'w', encoding='utf-8') as file:
            file.write(new_content2)
        print(f'Replaced {n + n2 + n3} loading states in {f}')
