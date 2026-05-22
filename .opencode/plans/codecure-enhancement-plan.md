# CodeCure — Enhancement & Deployment Plan

## Changes Overview

### 1. Security Fix — `app.py` (Line 516)
**Replace hardcoded API key with environment variable:**
```python
# OLD (line 516):
GEMINI_API_KEY = "AIzaSyA27t-9dcW0hTOiZ1nLWVry4RX1kTYi2vI"

# NEW:
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY not set. Chatbot will not function.")
```

---

### 2. New CSS Animations — `templates/index.html`

**Add these CSS rules before the closing `</style>` tag (~line 856):**

```css
/* ═══ ENHANCED FLUID ANIMATIONS ═══ */

/* Skeleton loader */
.skeleton {
  background: linear-gradient(90deg, var(--slate) 25%, var(--slate2) 50%, var(--slate) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 8px;
}
@keyframes skeletonShimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.skeleton-row { height: 44px; margin-bottom: 8px; border-radius: 8px; }
.skeleton-text { height: 14px; margin-bottom: 8px; border-radius: 6px; width: 80%; }
.skeleton-text.short { width: 40%; }

/* Staggered table row entrance */
@keyframes rowSlideIn {
  from { opacity: 0; transform: translateX(-12px); }
  to { opacity: 1; transform: translateX(0); }
}
.med-row-animate {
  animation: rowSlideIn 0.4s cubic-bezier(.16,1,.3,1) both;
}

/* Enhanced section transitions */
.section.slide-left { animation: slideLeftIn 0.5s cubic-bezier(.16,1,.3,1) both; }
.section.slide-right { animation: slideRightIn 0.5s cubic-bezier(.16,1,.3,1) both; }
.section.fade-scale { animation: fadeScale 0.5s cubic-bezier(.16,1,.3,1) both; }

@keyframes slideLeftIn {
  from { opacity: 0; transform: translateX(30px); }
  to { opacity: 1; transform: translateX(0); }
}
@keyframes slideRightIn {
  from { opacity: 0; transform: translateX(-30px); }
  to { opacity: 1; transform: translateX(0); }
}
@keyframes fadeScale {
  from { opacity: 0; transform: scale(0.97); }
  to { opacity: 1; transform: scale(1); }
}

/* Page-enter animation for dashboard */
@keyframes pageEnter {
  from { opacity: 0; transform: translateY(20px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.content { animation: pageEnter 0.6s 0.2s cubic-bezier(.16,1,.3,1) both; }

/* Smooth chart container */
.chart-container {
  transition: all 0.5s cubic-bezier(.16,1,.3,1);
}
.chart-container:hover {
  transform: scale(1.01);
}

/* Notification badge bounce */
@keyframes badgeBounce {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.2); }
}
.nav-badge.update {
  animation: badgeBounce 0.4s ease;
}

/* Card hover glow sweep */
.card::after {
  content: '';
  position: absolute;
  top: 0; left: -100%;
  width: 50%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.03), transparent);
  transition: left 0.6s ease;
  pointer-events: none;
}
.card:hover::after {
  left: 100%;
}
.card { position: relative; overflow: hidden; }

/* Loading spinner for buttons */
@keyframes spin {
  to { transform: rotate(360deg); }
}
.btn-loading {
  pointer-events: none;
  opacity: 0.7;
}
.btn-loading::before {
  content: '';
  display: inline-block;
  width: 14px; height: 14px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  margin-right: 8px;
}
```

---

### 3. Enhanced JavaScript — `templates/index.html`

**Replace the `showSection` function (~line 1390) with:**
```javascript
let lastSection = 'dashboard';
const sectionOrder = ['dashboard', 'inventory', 'alerts', 'reports', 'billing'];

function showSection(name, el) {
  const currentEl = document.querySelector('.section.active');
  const currentIndex = sectionOrder.indexOf(lastSection);
  const newIndex = sectionOrder.indexOf(name);

  document.querySelectorAll('.section').forEach(s => {
    s.classList.remove('active', 'slide-left', 'slide-right', 'fade-scale');
  });

  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const target = document.getElementById('sec-'+name);
  target.classList.add('active');

  // Directional transition
  if (newIndex > currentIndex) {
    target.classList.add('slide-left');
  } else if (newIndex < currentIndex) {
    target.classList.add('slide-right');
  } else {
    target.classList.add('fade-scale');
  }

  if(el) el.classList.add('active');
  document.getElementById('page-title').textContent =
    {dashboard:'Dashboard',inventory:'Inventory Management',alerts:'Active Alerts',reports:'Reports & Analytics',billing:'Billing & POS'}[name];

  lastSection = name;

  if(name==='inventory') loadMedicines('all', document.querySelector('.filter-tab'));
  if(name==='alerts')    loadAlerts();
  if(name==='reports')   loadReports();
  if(name==='dashboard') { loadStats(); loadDashAlerts(); loadActivity(); loadCategoryChart(); }
  closeSidebar();
}
```

**Replace the `loadMedicines` table rendering (~line 1528) with staggered animation:**
```javascript
  document.getElementById('med-tbody').innerHTML = meds.map((m,i)=>{
    let status='ok', label='✅ OK';
    if(m.expiry_date && m.expiry_date <= today){ status='expired'; label='🚨 Expired'; }
    else if(m.quantity < m.min_stock){ status='low'; label='⚠️ Low'; }
    return `<tr class="med-row-animate" style="animation-delay:${i * 0.04}s">
      <td>${startIdx + i}</td>
      <td style="font-weight:600;color:var(--white)">${m.name}</td>
      <td>${m.category||'—'}</td>
      <td>${m.quantity}</td>
      <td>${m.expiry_date||'—'}</td>
      <td>${m.supplier||'—'}</td>
      <td>₹${parseFloat(m.price||0).toFixed(2)}</td>
      <td><span class="badge ${status}">${label}</span></td>
      ${canEdit?`<td>
        <button class="btn btn-edit btn-sm" onclick='openEdit(${JSON.stringify(m)})'>✏️</button>
        ${canDel?`<button class="btn btn-danger btn-sm" onclick="delMed(${m.id},'${m.name.replace(/'/g,"\\'")}')">🗑️</button>`:''}
      </td>`:''}
    </tr>`;
  }).join('');
```

**Add skeleton loader function (add before `// ── INIT ──`):**
```javascript
function showSkeletonLoader(rows = 5) {
  let html = '';
  for (let i = 0; i < rows; i++) {
    html += `<tr><td colspan="9" style="padding:4px 14px;">
      <div style="display:flex;gap:14px;align-items:center;">
        <div class="skeleton" style="width:30px;height:18px;"></div>
        <div class="skeleton" style="flex:1;height:18px;"></div>
        <div class="skeleton" style="width:80px;height:18px;"></div>
        <div class="skeleton" style="width:50px;height:18px;"></div>
        <div class="skeleton" style="width:70px;height:18px;"></div>
        <div class="skeleton" style="width:90px;height:18px;"></div>
        <div class="skeleton" style="width:60px;height:18px;"></div>
        <div class="skeleton" style="width:70px;height:24px;border-radius:12px;"></div>
      </div>
    </td></tr>`;
  }
  document.getElementById('med-tbody').innerHTML = html;
}
```

**Call skeleton loader at start of `loadMedicines`:**
```javascript
async function loadMedicines(filter, tabEl, isSearch) {
  if (!isSearch) { showSkeletonLoader(5); }
  // ... rest of function
}
```

**Enhanced number counter (replace the existing counter code):**
```javascript
function animateValue(obj, start, end, duration) {
  let startTimestamp = null;
  const step = (timestamp) => {
    if (!startTimestamp) startTimestamp = timestamp;
    const progress = Math.min((timestamp - startTimestamp) / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 4);
    obj.textContent = Math.floor(ease * (end - start) + start);
    if (progress < 1) requestAnimationFrame(step);
    else obj.textContent = end;
  };
  requestAnimationFrame(step);
}

// Reset counters when returning to dashboard
function resetAndAnimateStats() {
  document.querySelectorAll('.stat-num').forEach(el => {
    const val = parseInt(el.textContent) || 0;
    if (val > 0) {
      el.textContent = '0';
      animateValue(el, 0, val, 1800);
    }
  });
}
```

**Call `resetAndAnimateStats()` in `loadStats()` after setting values:**
```javascript
async function loadStats() {
  const r = await fetch('/api/stats'); const d = await r.json();
  document.getElementById('s-total').textContent = d.total;
  document.getElementById('s-ok').textContent    = d.ok;
  document.getElementById('s-low').textContent   = d.low;
  document.getElementById('s-exp').textContent   = d.expired;
  resetAndAnimateStats();
}
```

---

### 4. Google App Engine — New File `app.yaml`

```yaml
runtime: python311
instance_class: F1

entrypoint: gunicorn wsgi:application --bind 0.0.0.0:$PORT

env_variables:
  SECRET_KEY: "codecure-secret-key-change-this"
  # Set your Gemini API key here OR use gcloud secrets
  # GEMINI_API_KEY: "your-api-key-here"

automatic_scaling:
  min_instances: 0
  max_instances: 2
  target_cpu_utilization: 0.65

handlers:
  - url: /static
    static_dir: static
  - url: /.*
    script: auto
```

---

### 5. New File — `.gcloudignore`

```
# Ignore these files during deployment
venv/
__pycache__/
*.pyc
.env
codecure.db
.git/
*.md
test_models.py
update_app.py
```

---

### 6. Updated `requirements.txt`

Add this line at the end:
```
gunicorn==25.2.0
google-generativeai
```
(Already present — just verify it matches)

---

## Deployment Steps for Google App Engine

### Step 1: Install Google Cloud SDK
1. Download from: https://cloud.google.com/sdk/docs/install
2. Run in terminal:
```bash
gcloud init
```

### Step 2: Create a Google Cloud Project
```bash
gcloud projects create codecure-yourname --name="CodeCure Medical Inventory"
gcloud config set project codecure-yourname
```

### Step 3: Enable App Engine
```bash
gcloud app create --region=us-central
```

### Step 4: Set Environment Variables
```bash
gcloud secrets create gemini-api-key --data-file=-
# Paste your API key, then press Ctrl+D
```

Or add directly in `app.yaml` (less secure but simpler for demo).

### Step 5: Deploy
```bash
gcloud app deploy
```

### Step 6: View Your App
```bash
gcloud app browse
```

Your app will be live at: `https://codecure-yourname.uc.r.appspot.com`

---

## Quick Summary of All Changes

| File | Change |
|------|--------|
| `app.py` | Move Gemini API key to env var |
| `templates/index.html` | Add 8 new animation CSS classes, skeleton loaders, staggered rows, directional transitions, animated counters |
| `app.yaml` | NEW — Google App Engine config |
| `.gcloudignore` | NEW — Deployment ignore file |
| `.env.example` | NEW — Template for environment variables |
