import os

def modify_dashboard():
    path = r'c:\Users\adity\OneDrive\Desktop\Codecure\templates\admin_dashboard.html'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    new_sections = """

<div class="section" id="sec-suppliers">
  <div class="card">
    <div class="card-header">
      <div class="card-title">🏢 Supplier Management</div>
      <button class="btn btn-primary" onclick="openSupplierModal()">＋ Add Supplier</button>
    </div>
    <div class="card-body" style="padding:0; overflow-x:auto;">
      <table style="width:100%;border-collapse:collapse;font-size:.85rem;">
        <thead><tr>
          <th style="background:var(--glow-soft);color:var(--accent2);padding:12px;text-align:left;">Supplier Name</th>
          <th style="background:var(--glow-soft);color:var(--accent2);padding:12px;text-align:left;">Contact Person</th>
          <th style="background:var(--glow-soft);color:var(--accent2);padding:12px;text-align:left;">Phone / Email</th>
          <th style="background:var(--glow-soft);color:var(--accent2);padding:12px;text-align:left;">Status</th>
          <th style="background:var(--glow-soft);color:var(--accent2);padding:12px;text-align:right;">Actions</th>
        </tr></thead>
        <tbody id="tbody-suppliers"><tr><td colspan="5" class="empty-state">Loading...</td></tr></tbody>
      </table>
    </div>
  </div>
</div><!-- /sec-suppliers -->

<div class="section" id="sec-pos">
  <!-- Analytics -->
  <div class="overview-grid" style="margin-bottom:24px;">
    <div class="ov-card" style="padding:16px;">
      <div class="ov-num" id="po-open-count" style="font-size:1.8rem;">—</div>
      <div class="ov-label">Open Purchase Orders</div>
    </div>
    <div class="ov-card" style="padding:16px;">
      <div class="ov-num" id="po-outstanding-val" style="font-size:1.8rem; color:var(--red);">—</div>
      <div class="ov-label">Outstanding Value</div>
    </div>
    <div class="ov-card" style="padding:16px;">
      <div class="ov-num" id="po-month-orders" style="font-size:1.8rem; color:var(--green);">—</div>
      <div class="ov-label">Orders This Month</div>
    </div>
    <div class="ov-card" style="padding:16px;">
      <div class="ov-num" id="po-top-supplier" style="font-size:1.4rem; color:var(--accent-secondary);">—</div>
      <div class="ov-label">Top Supplier</div>
    </div>
  </div>

  <div class="card">
    <div class="card-header">
      <div class="card-title">📦 Purchase Orders</div>
    </div>
    <div class="card-body" style="padding:0; overflow-x:auto;">
      <table style="width:100%;border-collapse:collapse;font-size:.85rem;">
        <thead><tr>
          <th style="background:var(--glow-soft);color:var(--accent2);padding:12px;text-align:left;">PO Number</th>
          <th style="background:var(--glow-soft);color:var(--accent2);padding:12px;text-align:left;">Date</th>
          <th style="background:var(--glow-soft);color:var(--accent2);padding:12px;text-align:left;">Supplier</th>
          <th style="background:var(--glow-soft);color:var(--accent2);padding:12px;text-align:left;">Status</th>
          <th style="background:var(--glow-soft);color:var(--accent2);padding:12px;text-align:right;">Actions</th>
        </tr></thead>
        <tbody id="tbody-pos"><tr><td colspan="5" class="empty-state">Loading...</td></tr></tbody>
      </table>
    </div>
  </div>
</div><!-- /sec-pos -->

"""
    content = content.replace('</div><!-- /sec-users -->', '</div><!-- /sec-users -->\n' + new_sections)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    modify_dashboard()
    print("Dashboard sections added.")
