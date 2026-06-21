"""
CodeCure — AI-Powered Smart Pharmacy Management System
Main Application (Modular Refactor)
"""
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from werkzeug.security import check_password_hash, generate_password_hash
import os, json, traceback, re, io, difflib, string
from datetime import datetime, date, timedelta
from werkzeug.exceptions import RequestEntityTooLarge
from PIL import Image

from config import Config
from models import get_db, init_db, log_activity, record_sale
from utils import (
    sanitize, sanitize_dict, validate_medicine_data,
    safe_int, safe_float, login_required, role_required,
    days_until_expiry, get_expiry_status
)
from utils_pdf import generate_a4_invoice, generate_thermal_invoice
import barcode_service
import intelligence_service

app = Flask(__name__)
app.config.from_object(Config)
from models_sqlalchemy import db, Medicine, Activity, Sale, Supplier, User, MedicineBatch
db.init_app(app)
app.secret_key = Config.SECRET_KEY
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# ─── DEMO USERS (will migrate to DB users table later) ────────────────────────

# USERS dictionary removed in favor of SQLAlchemy User model

# ─── ERROR HANDLER ─────────────────────────────────────────────────────────────

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, RequestEntityTooLarge):
        return jsonify({"error": "File exceeds the 5MB size limit."}), 413
    
    traceback.print_exc()
    if request.path.startswith("/api/"):
        return jsonify({"error": "Internal server error"}), 500
    return f"<pre>{traceback.format_exc()}</pre>", 500

# ─── AUTH ROUTES ───────────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def login():
    # Auto-create admin if users table is empty
    if User.query.count() == 0:
        import secrets
        import logging
        password = app.config.get("DEFAULT_ADMIN_PASSWORD")
        if not password:
            password = secrets.token_urlsafe(12)
            logging.warning(f"=== DEFAULT ADMIN PASSWORD GENERATED: {password} ===")
            logging.warning("Please copy this password. It will only be shown once!")
            
        admin = User(
            username="admin", 
            password_hash=generate_password_hash(password), 
            role="Admin", 
            is_active=True
        )
        db.session.add(admin)
        db.session.commit()

    if "user" in session:
        return _redirect_by_role(session["role"])
    
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        
        user = User.query.filter_by(username=username).first()
        if user and user.is_active and check_password_hash(user.password_hash, password):
            session["user"] = username
            session["role"] = user.role
            
            act = Activity(action="Login", detail=f"{username} logged in", user=username)
            db.session.add(act)
            db.session.commit()
            
            return _redirect_by_role(session["role"])
            
        if user and not user.is_active:
            error = "Account disabled. Please contact Admin."
        else:
            error = "Invalid credentials"
            
    return render_template("login.html", error=error)

def _redirect_by_role(role):
    """Redirect user to the appropriate dashboard based on their role."""
    role_routes = {
        "Admin": "admin_dashboard",
        "Pharmacist": "pharmacist_dashboard",
        "Cashier": "cashier_dashboard",
        "Doctor": "doctor_dashboard",
    }
    return redirect(url_for(role_routes.get(role, "dashboard")))

@app.route("/logout")
def logout():
    user = session.pop("user", "unknown")
    session.pop("role", None)
    session.pop("cart", None)
    log_activity("Logout", f"{user} logged out", user)
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", user=session["user"], role=session["role"])


# ─── ROLE-BASED DASHBOARDS ─────────────────────────────────────────────────────

@app.route("/admin")
@login_required
def admin_dashboard():
    return render_template("admin_dashboard.html", user=session["user"], role=session["role"])

@app.route("/pharmacist")
@login_required
def pharmacist_dashboard():
    return render_template("pharmacist_dashboard.html", user=session["user"], role=session["role"])

@app.route("/cashier")
@login_required
def cashier_dashboard():
    return render_template("cashier_dashboard.html", user=session["user"], role=session["role"])

@app.route("/doctor")
@login_required
def doctor_dashboard():
    return render_template("doctor_dashboard.html", user=session["user"], role=session["role"])

# ─── SMART SCANNER / AI VISION API ───────────────────────────────────────────

@app.route("/api/scan-medicine", methods=["POST"])
@role_required("Admin", "Pharmacist", "Cashier")
def api_scan_medicine():
    """Accept an uploaded medicine image, use Gemini Vision to analyze the
    packaging, and return extracted fields as structured JSON."""
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No image file provided"}), 400

    try:
        image = Image.open(file)
        # Ensure RGB for Gemini
        if image.mode not in ("RGB",):
            image = image.convert("RGB")
    except Exception:
        return jsonify({"error": "Invalid or corrupted image file"}), 400

    # ── Send image to Gemini Vision for analysis ──
    try:
        import google.generativeai as genai
        genai.configure(api_key=Config.GEMINI_API_KEY)
        vision_model = genai.GenerativeModel(Config.GEMINI_MODEL)

        prompt = (
            "You are a pharmacist AI analyzing an Indian medicine wrapper. "
            "Extract the following into strict JSON with no markdown formatting or backticks: "
            'name (the primary medicine name), '
            'category (guess the medical category, e.g., Analgesic, Antibiotic, etc.), '
            'expiry_date (Hunt for "EXP" or "Expiry". Format strictly as YYYY-MM-DD. '
            'If only MM/YY is given, assume the last day of that month), '
            'supplier (the manufacturer or pharmaceutical company name), '
            'and price (Hunt for "MRP" or "Rs.". Extract ONLY the float number, '
            'e.g., if it says "MRP Rs. 115.50", output 115.50). '
            'If any value is entirely unreadable, return null for that key.'
        )

        response = vision_model.generate_content([prompt, image])
        raw_text = response.text.strip()

        # Strip markdown code fences if the model wraps the JSON
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[-1]  # Remove first line
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3].strip()

        result = json.loads(raw_text)

        # Ensure all expected keys exist
        return jsonify({
            "name": result.get("name") or "",
            "category": result.get("category") or "",
            "expiry_date": result.get("expiry_date") or "",
            "supplier": result.get("supplier") or "",
            "price": result.get("price")
        })

    except json.JSONDecodeError:
        # AI returned non-JSON text — try to salvage what we can
        return jsonify({
            "name": raw_text[:100] if raw_text else "",
            "category": "",
            "expiry_date": "",
            "supplier": "",
            "price": None,
            "warning": "AI response was not valid JSON — partial data returned"
        })
    except Exception as e:
        error_msg = str(e).lower()
        if "api key not valid" in error_msg or "api_key_invalid" in error_msg:
            return jsonify({"error": "Vision analysis failed due to invalid AI configuration."}), 500
        elif "quota" in error_msg or "exhausted" in error_msg:
            return jsonify({"error": "AI service quota exceeded. Try again later."}), 500
        return jsonify({"error": "AI Vision analysis temporarily unavailable."}), 500

def normalize_med_name(name):
    if not name:
        return ""
    n = name.lower()
    n = n.translate(str.maketrans('', '', string.punctuation))
    n = " ".join(n.split())
    return n

# DEPRECATED (Phase UX-R1) - Prescription Scanner Decommissioned
@app.route("/api/scan-prescription", methods=["POST"])
@role_required("Admin", "Pharmacist", "Doctor")
def api_scan_prescription():
    return jsonify({"error": "Prescription scanner feature decommissioned."}), 410

"""
--- DEPRECATED CODE BELOW FOR ROLLBACK ---

@app.route("/api/scan-prescription", methods=["POST"])
@role_required("Admin", "Pharmacist", "Doctor")
def api_scan_prescription():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No image file provided"}), 400

    try:
        image = Image.open(file)
        if image.mode not in ("RGB",):
            image = image.convert("RGB")
    except Exception:
        return jsonify({"error": "Invalid or corrupted image file"}), 400

    try:
        import google.generativeai as genai
        genai.configure(api_key=Config.GEMINI_API_KEY)
        vision_model = genai.GenerativeModel(Config.GEMINI_MODEL)
        text_model = genai.GenerativeModel(Config.GEMINI_MODEL) # Pass 2 model

        # Pass 1: Raw Extraction
        prompt_pass1 = (
            "You are a pharmacist AI analyzing a doctor's prescription. "
            "Extract the medicines EXACTLY as written. Do not guess. "
            "If a word is uncertain or illegible, surround it with brackets and a question mark, like [Amphogel?]. "
            "Extract into a strict JSON array where each object MUST have: "
            "'medicine', 'dosage', 'frequency', 'duration', 'quantity', 'ocr_confidence' (0-100 integer score). "
            "Do not include markdown fences. Return ONLY the raw JSON array."
        )

        response_pass1 = vision_model.generate_content([prompt_pass1, image])
        raw_text_p1 = response_pass1.text.strip()
        if raw_text_p1.startswith("```"):
            raw_text_p1 = raw_text_p1.split("\n", 1)[-1]
            if raw_text_p1.endswith("```"):
                raw_text_p1 = raw_text_p1[:-3].strip()

        extracted_pass1 = json.loads(raw_text_p1)
        if not isinstance(extracted_pass1, list):
            extracted_pass1 = [extracted_pass1]

        inventory = Medicine.query.all()
        results = []
        found_count = 0
        not_found_count = 0
        est_cart_value = 0.0

        for med in extracted_pass1:
            raw_presc_name = med.get("medicine", "")
            if not raw_presc_name:
                continue

            # Local Matching: Top 20 Candidates
            norm_presc = normalize_med_name(raw_presc_name)
            candidate_scores = []
            
            for inv_med in inventory:
                inv_name = inv_med.name
                norm_inv = normalize_med_name(inv_name)
                ratio = difflib.SequenceMatcher(None, norm_presc, norm_inv).ratio()
                candidate_scores.append((ratio, inv_med.name))
                
            candidate_scores.sort(key=lambda x: x[0], reverse=True)
            top_20_candidates = [c[1] for c in candidate_scores[:20]]

            # Pass 2: Correction with Candidates
            prompt_pass2 = (
                f"Review this raw OCR extraction with uncertainty markers: '{raw_presc_name}'.\n"
                f"Here are the top 20 inventory candidates: {', '.join(top_20_candidates)}.\n"
                "If the raw text closely matches an inventory candidate, correct it to the candidate's exact name. "
                "Do not hallucinate names. If no candidate matches, keep the best guess without brackets.\n"
                "Return a strict JSON object with: 'corrected_medicine' (string) and 'match_confidence' (0-100 integer representing confidence in the correction).\n"
                "Return ONLY the raw JSON object."
            )
            
            response_pass2 = text_model.generate_content(prompt_pass2)
            raw_text_p2 = response_pass2.text.strip()
            if raw_text_p2.startswith("```"):
                raw_text_p2 = raw_text_p2.split("\n", 1)[-1]
                if raw_text_p2.endswith("```"):
                    raw_text_p2 = raw_text_p2[:-3].strip()
                    
            try:
                pass2_json = json.loads(raw_text_p2)
                corrected_name = pass2_json.get("corrected_medicine", raw_presc_name.replace("[", "").replace("?]", ""))
                match_confidence = pass2_json.get("match_confidence", 0)
            except:
                corrected_name = raw_presc_name.replace("[", "").replace("?]", "")
                match_confidence = 0

            # Verify against inventory again for strict ID assignment
            best_match = None
            best_local_score = -1
            all_scores = []
            
            norm_corrected = normalize_med_name(corrected_name)
            for inv_med in inventory:
                inv_name = inv_med.name
                norm_inv = normalize_med_name(inv_name)
                
                score = 0
                if corrected_name.lower() == inv_name.lower():
                    score = 100
                elif norm_corrected == norm_inv:
                    score = 100
                else:
                    ratio = difflib.SequenceMatcher(None, norm_corrected, norm_inv).ratio()
                    score = int(ratio * 100)
                
                all_scores.append((score, inv_med))
                if score > best_local_score:
                    best_local_score = score
                    best_match = inv_med

            # Combine Gemini confidence with local strictness
            if best_local_score < 80:
                final_score = best_local_score
                best_match = None # reject if it's too far from any inventory item
            else:
                final_score = max(match_confidence, best_local_score)

            if not best_match:
                found = False
                confidence_cat = "Manual Review Required"
            elif final_score >= 98:
                confidence_cat = "Auto Match"
                found = True
            elif final_score >= 90:
                confidence_cat = "Review Recommended"
                found = True
            else:
                confidence_cat = "Manual Review Required"
                found = False

            item_result = {
                "raw_extraction": {
                    "medicine": raw_presc_name,
                    "dosage": med.get("dosage", ""),
                    "frequency": med.get("frequency", ""),
                    "duration": med.get("duration", ""),
                    "quantity": med.get("quantity", "")
                },
                "corrected_extraction": corrected_name,
                "ocr_confidence": med.get("ocr_confidence", 0),
                "match_confidence": final_score,
                "found": found,
                "confidence_category": confidence_cat,
                "inventory_match": None,
                "alternatives": []
            }

            if found and best_match:
                item_result["inventory_match"] = {
                    "id": best_match.id,
                    "name": best_match.name,
                    "stock": best_match.quantity,
                    "price": best_match.price,
                    "expiry": best_match.expiry_date
                }
                found_count += 1
                est_cart_value += float(best_match.price) if best_match.price else 0.0
            else:
                not_found_count += 1
                all_scores.sort(key=lambda x: x[0], reverse=True)
                item_result["alternatives"] = [m[1].name for m in all_scores[:3]]
                
            results.append(item_result)
        
        summary = {
            "total_extracted": len(results),
            "found_count": found_count,
            "not_found_count": not_found_count,
            "estimated_value": est_cart_value
        }
        
        return jsonify({"summary": summary, "results": results})

    except json.JSONDecodeError:
        return jsonify({"error": "Failed to parse AI response. Prescription might be unreadable."}), 400
    except Exception as e:
        error_msg = str(e).lower()
        traceback.print_exc()
        if "quota" in error_msg or "exhausted" in error_msg:
            return jsonify({"error": "AI service quota exceeded. Try again later."}), 500
        return jsonify({"error": "Prescription analysis temporarily unavailable."}), 500


--- END DEPRECATED CODE ---
"""

# ─── STATS API ─────────────────────────────────────────────────────────────────

@app.route("/api/stats")
@login_required
def api_stats():
    today = date.today().isoformat()
    total = Medicine.query.count()
    expired = Medicine.query.filter(Medicine.expiry_date != None, Medicine.expiry_date != "", Medicine.expiry_date <= today).count()
    low = Medicine.query.filter(Medicine.quantity < Medicine.min_stock, db.or_(Medicine.expiry_date == None, Medicine.expiry_date == "", Medicine.expiry_date > today)).count()
    ok = Medicine.query.filter(Medicine.quantity >= Medicine.min_stock, db.or_(Medicine.expiry_date == None, Medicine.expiry_date == "", Medicine.expiry_date > today)).count()
    return jsonify({"total": total, "ok": ok, "low": low, "expired": expired})

# ─── MEDICINES CRUD ────────────────────────────────────────────────────────────

@app.route("/api/medicines", methods=["GET"])
@login_required
def api_medicines():
    filter_type = request.args.get("filter", "all")
    search = request.args.get("search", "").strip()
    sort_col = request.args.get("sort", "name")
    sort_dir = request.args.get("dir", "asc")
    page = safe_int(request.args.get("page", 1), default=1, minimum=1)
    per_page = safe_int(request.args.get("per_page", 50), default=50, minimum=1, maximum=200)
    today = date.today().isoformat()

    valid_cols = ["name", "category", "quantity", "expiry_date", "supplier", "price"]
    if sort_col not in valid_cols:
        sort_col = "name"
    
    query = Medicine.query

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                Medicine.name.ilike(search_term),
                Medicine.category.ilike(search_term),
                Medicine.supplier.ilike(search_term)
            )
        )

    if filter_type == "low":
        query = query.filter(Medicine.quantity < Medicine.min_stock)
    elif filter_type == "expiring":
        query = query.filter(Medicine.expiry_date > today, Medicine.expiry_date <= "2025-12-31")
    elif filter_type == "expired":
        query = query.filter(Medicine.expiry_date != None, Medicine.expiry_date != "", Medicine.expiry_date <= today)

    if sort_dir == "desc":
        query = query.order_by(getattr(Medicine, sort_col).desc())
    else:
        query = query.order_by(getattr(Medicine, sort_col).asc())

    total = query.count()
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    
    rows = []
    for r in items:
        rows.append({
            "id": str(r.id),
            "name": r.name,
            "category": r.category,
            "quantity": r.quantity,
            "min_stock": r.min_stock,
            "expiry_date": r.expiry_date,
            "supplier": r.supplier,
            "price": r.price,
            "created_at": r.created_at
        })
        
    return jsonify({
        "data": rows,
        "total": total, "page": page, "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    })

@app.route("/api/medicines", methods=["POST"])
@role_required("Admin", "Pharmacist")
def api_add_medicine():
    data = request.json or {}
    clean = sanitize_dict(data, ["name", "category", "supplier", "expiry_date"])
    errors = validate_medicine_data({**data, **clean})
    if errors:
        return jsonify({"error": ", ".join(errors)}), 400
    
    qty = safe_int(data.get("quantity", 0))
    if qty < 0:
        return jsonify({"error": "Quantity cannot be negative"}), 400
        
    try:
        med = Medicine(
            name=clean["name"],
            category=clean.get("category", ""),
            quantity=qty,
            min_stock=safe_int(data.get("min_stock", 10)),
            expiry_date=clean.get("expiry_date", ""),
            supplier=clean.get("supplier", ""),
            price=safe_float(data.get("price", 0))
        )
        db.session.add(med)
        
        act = Activity(action="Add Medicine", detail=clean["name"], user=session["user"])
        db.session.add(act)
        
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/api/medicines/<string:mid>", methods=["PUT"])
@role_required("Admin", "Pharmacist")
def api_update_medicine(mid):
    data = request.json or {}
    clean = sanitize_dict(data, ["name", "category", "supplier", "expiry_date"])
    errors = validate_medicine_data({**data, **clean})
    if errors:
        return jsonify({"error": ", ".join(errors)}), 400
        
    qty = safe_int(data.get("quantity", 0))
    if qty < 0:
        return jsonify({"error": "Quantity cannot be negative"}), 400
        
    try:
        med = Medicine.query.get(mid)
        if not med:
            return jsonify({"error": "Medicine not found"}), 404
            
        med.name = clean["name"]
        med.category = clean.get("category", "")
        med.quantity = qty
        med.min_stock = safe_int(data.get("min_stock", 10))
        med.expiry_date = clean.get("expiry_date", "")
        med.supplier = clean.get("supplier", "")
        med.price = safe_float(data.get("price", 0))
        
        act = Activity(action="Edit Medicine", detail=f"ID {mid} updated", user=session["user"])
        db.session.add(act)
        
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/api/medicines/<string:mid>", methods=["DELETE"])
@role_required("Admin")
def api_delete_medicine(mid):
    try:
        med = Medicine.query.get(mid)
        if not med:
            return jsonify({"error": "Medicine not found"}), 404
            
        name = med.name
        db.session.delete(med)
        
        act = Activity(action="Delete Medicine", detail=name, user=session["user"])
        db.session.add(act)
        
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/api/sales", methods=["GET"])
@role_required("Admin", "Pharmacist")
def api_sales():
    page = safe_int(request.args.get("page", 1), default=1, minimum=1)
    per_page = safe_int(request.args.get("per_page", 50), default=50, minimum=1, maximum=200)
    
    query = Sale.query.order_by(Sale.id.desc())
    total = query.count()
    sales = query.limit(per_page).offset((page - 1) * per_page).all()
    
    data = []
    for s in sales:
        data.append({
            "id": s.id,
            "invoice_id": s.invoice_id,
            "customer_name": s.customer_name,
            "total_amount": s.total_amount,
            "discount": getattr(s, 'discount', 0.0),
            "payment_method": getattr(s, 'payment_method', 'Cash'),
            "sold_by": s.sold_by,
            "timestamp": s.timestamp,
            "status": getattr(s, 'status', 'Paid')
        })
    return jsonify({"data": data, "page": page, "page_size": per_page, "total_records": total})

@app.route("/api/invoice/<invoice_id>/pdf", methods=["GET"])
@role_required("Admin", "Pharmacist", "Doctor")
def api_invoice_pdf(invoice_id):
    sale = Sale.query.filter_by(invoice_id=invoice_id).first()
    if not sale:
        return jsonify({"error": "Invoice not found"}), 404
        
    fmt = request.args.get("format", "a4")
    
    if fmt == "thermal":
        pdf_buffer = generate_thermal_invoice(sale, app.config)
    else:
        pdf_buffer = generate_a4_invoice(sale, app.config)
        
    filename = f"Invoice_{invoice_id}.pdf"
    
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

# ─── ALERTS ────────────────────────────────────────────────────────────────────

@app.route("/api/alerts")
@login_required
def api_alerts():
    today = date.today().isoformat()
    warn_30_date = (date.today() + timedelta(days=30)).isoformat()
    warn_60_date = (date.today() + timedelta(days=60)).isoformat()
    
    # We will generate alerts based on MedicineBatch
    batches = MedicineBatch.query.all()
    out = Medicine.query.filter(Medicine.quantity == 0).all()
    
    alerts = []
    
    # Empty medicines fallback
    for r in out:
        alerts.append({"id": str(r.id),"type":"out","severity":"critical","name":r.name,"detail":"Out of stock!"})
        
    for b in batches:
        m = Medicine.query.get(b.medicine_id)
        if not m: continue
        
        name_with_batch = f"{m.name} (Batch {b.batch_number})"
        
        if b.quantity <= 0:
            alerts.append({"id": str(m.id),"type":"out","severity":"warning","name":name_with_batch,"detail":"Batch is empty"})
            continue
            
        if b.expiry_date:
            if b.expiry_date < today:
                alerts.append({"id": str(m.id),"type":"expired","severity":"critical","name":name_with_batch,"detail":f"Expired on {b.expiry_date}"})
            elif b.expiry_date <= warn_30_date:
                alerts.append({"id": str(m.id),"type":"expiring","severity":"warning","name":name_with_batch,"detail":f"Expires in 30 days ({b.expiry_date})"})
            elif b.expiry_date <= warn_60_date:
                alerts.append({"id": str(m.id),"type":"expiring","severity":"notice","name":name_with_batch,"detail":f"Expires in 60 days ({b.expiry_date})"})
                
    # Also handle legacy medicines that have no batches but have low stock/expiry
    legacy_meds = Medicine.query.outerjoin(MedicineBatch).filter(MedicineBatch.id == None).all()
    for r in legacy_meds:
        if r.quantity < r.min_stock and r.quantity > 0:
            alerts.append({"id": str(r.id),"type":"low","severity":"warning","name":r.name,"detail":f"Only {r.quantity} left (min {r.min_stock})","quantity":r.quantity,"min_stock":r.min_stock})
        if r.expiry_date and r.expiry_date < today:
            alerts.append({"id": str(r.id),"type":"expired","severity":"critical","name":r.name,"detail":f"Expired on {r.expiry_date}"})
            
    return jsonify(alerts)

# ─── RESTOCK / DISCARD ACTIONS ─────────────────────────────────────────────────

@app.route("/api/medicines/<string:mid>/restock", methods=["POST"])
@role_required("Admin", "Pharmacist")
def api_restock_medicine(mid):
    """Restock a medicine to a safe level (default: min_stock * 2, or provided qty)."""
    data = request.json or {}
    try:
        med = Medicine.query.get(mid)
        if not med:
            return jsonify({"error": "Medicine not found"}), 404
            
        new_qty = safe_int(data.get("quantity", 0))
        if new_qty <= 0:
            new_qty = med.min_stock * 2  # Default: double the minimum
            
        med.quantity = new_qty
        
        act = Activity(action="Restock", detail=f"{med.name} restocked to {new_qty} units", user=session["user"])
        db.session.add(act)
        
        db.session.commit()
        return jsonify({"success": True, "name": med.name, "new_quantity": new_qty})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/api/medicines/<string:mid>/discard", methods=["POST"])
@role_required("Admin", "Pharmacist")
def api_discard_medicine(mid):
    """Discard a medicine by setting quantity to 0 (for expired/damaged items)."""
    try:
        med = Medicine.query.get(mid)
        if not med:
            return jsonify({"error": "Medicine not found"}), 404
            
        old_qty = med.quantity
        med.quantity = 0
        
        act = Activity(action="Discard", detail=f"{med.name} discarded ({old_qty} units removed)", user=session["user"])
        db.session.add(act)
        
        db.session.commit()
        return jsonify({"success": True, "name": med.name, "discarded_qty": old_qty})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/api/activity", methods=["GET"])
@login_required
def api_activity():
    activities = Activity.query.order_by(Activity.timestamp.desc()).limit(20).all()
    rows = []
    for r in activities:
        rows.append({
            "id": str(r.id),
            "action": r.action,
            "detail": r.detail,
            "user": r.user,
            "timestamp": r.timestamp
        })
    return jsonify(rows)

# ─── BILLING & POS ────────────────────────────────────────────────────────────

@app.route("/api/cart", methods=["GET"])
@login_required
def api_cart_get():
    cart = session.get("cart", [])
    cart_items = []
    for item in cart:
        m = Medicine.query.get(item["id"])
        if m and m.quantity >= item["qty"]:
            cart_items.append({
                "id": str(m.id), "name": m.name, "price": m.price,
                "qty": item["qty"], "subtotal": (m.price or 0) * item["qty"]
            })
    total = sum(i["subtotal"] for i in cart_items)
    return jsonify({"items": cart_items, "total": total})

@app.route("/api/cart", methods=["POST"])
@role_required("Admin", "Pharmacist", "Cashier")
def api_cart_add():
    data = request.json or {}
    mid = data.get("id")
    qty = safe_int(data.get("qty", 1), default=1, minimum=1)
    if not mid:
        return jsonify({"error": "Invalid item"}), 400
    try:
        m = Medicine.query.get(mid)
        if not m:
            return jsonify({"error": "Medicine not found"}), 404
        if m.quantity < qty:
            return jsonify({"error": f"Insufficient stock. Only {m.quantity} available."}), 400
        cart = session.get("cart", [])
        for item in cart:
            if str(item["id"]) == str(mid):
                item["qty"] = min(item["qty"] + qty, m.quantity)
                break
        else:
            cart.append({"id": str(mid), "qty": qty})
        session["cart"] = cart
        return jsonify({"success": True, "cart_count": len(cart)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/cart/<string:mid>", methods=["DELETE"])
@login_required
def api_cart_remove(mid):
    cart = session.get("cart", [])
    cart = [i for i in cart if i["id"] != mid]
    session["cart"] = cart
    return jsonify({"success": True})

@app.route("/api/cart/clear", methods=["POST"])
@login_required
def api_cart_clear():
    session["cart"] = []
    return jsonify({"success": True})

@app.route("/api/checkout", methods=["POST"])
@role_required("Admin", "Pharmacist", "Cashier")
def api_checkout():
    class FefoError(Exception):
        def __init__(self, payload):
            self.payload = payload

    cart = session.get("cart", [])
    if not cart:
        return jsonify({"error": "Cart is empty"}), 400
    
    # Sort cart items by ID to enforce deterministic lock ordering and prevent deadlocks
    cart = sorted(cart, key=lambda x: str(x["id"]))
    
    user = session["user"]
    invoice_items = []
    
    today_iso = date.today().isoformat()
    
    try:
        consumed_log_details = []
        
        for item in cart:
            mid, qty = item["id"], item["qty"]
            m = Medicine.query.with_for_update().filter_by(id=mid).first()
            if not m:
                raise Exception("Unknown medicine in cart")
                
            # Fetch batches with explicit row-level locking
            batches = MedicineBatch.query.filter_by(medicine_id=mid).with_for_update().all()
            
            if not batches:
                # ── LEGACY INVENTORY FALLBACK ──
                if m.quantity < qty:
                    raise Exception(f"Insufficient stock for {m.name}")
                m.quantity -= qty
                invoice_items.append({"name": m.name, "price": m.price, "qty": qty, "subtotal": (m.price or 0) * qty})
                consumed_log_details.append(f"{m.name}: {qty} (Legacy inventory without batch tracking.)")
                continue
            
            # ── FEFO BATCH LOGIC ──
            # Exclude expired batches (expiry_date < today)
            valid_batches = [b for b in batches if b.quantity > 0 and (not b.expiry_date or b.expiry_date >= today_iso)]
            
            # Sort by expiry ascending. Null/empty expiry_date sorted last.
            valid_batches.sort(key=lambda b: b.expiry_date if b.expiry_date else "9999-99-99")
            
            available_qty = sum(b.quantity for b in valid_batches)
            
            if available_qty < qty:
                total_qty = sum(b.quantity for b in batches)
                expired_qty = total_qty - available_qty
                if total_qty >= qty:
                    raise FefoError({
                        "medicine_name": m.name,
                        "requested_qty": qty,
                        "available_non_expired_qty": available_qty,
                        "expired_qty": expired_qty
                    })
                else:
                    raise Exception(f"Insufficient stock for {m.name}")
                    
            remaining_qty = qty
            consumed_this_item = []
            
            for b in valid_batches:
                if remaining_qty <= 0:
                    break
                deduct = min(remaining_qty, b.quantity)
                b.quantity -= deduct
                remaining_qty -= deduct
                consumed_this_item.append(f"Batch {b.batch_number} -> {deduct}")
                
            m.quantity -= qty
            
            invoice_items.append({"name": m.name, "price": m.price, "qty": qty, "subtotal": (m.price or 0) * qty})
            consumed_log_details.append(f"{m.name}\nConsumed:\n" + "\n".join(consumed_this_item))

        total = sum(i["subtotal"] for i in invoice_items)
        invoice_no = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        act = Activity(action="Sale Completed", detail=f"{invoice_no} - ₹{total:.2f}\n" + "\n\n".join(consumed_log_details), user=user)
        db.session.add(act)
        
        sale = Sale(invoice_id=invoice_no, customer_name="Walk-in", total_amount=total, discount=0, payment_method="Cash", sold_by=user, items_json=json.dumps(invoice_items), timestamp=datetime.utcnow().isoformat())
        db.session.add(sale)

        db.session.commit()
        
        session["cart"] = []
        return jsonify({
            "success": True, "invoice": invoice_no,
            "items": invoice_items, "total": total,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "cashier": user
        })
    except FefoError as e:
        db.session.rollback()
        return jsonify({"error": "FEFO Error", "fefo_details": e.payload}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

# ─── SCANNER API ───────────────────────────────────────────────────────────────

@app.route("/api/scan", methods=["POST"])
@login_required
def api_scan():
    data = request.json or {}
    barcode = data.get("barcode", "").strip()
    if not barcode:
        return jsonify({"error": "No barcode provided"}), 400
        
    result = barcode_service.resolve_scan(db, Medicine, barcode)
    return jsonify(result)

# ─── INVENTORY INTELLIGENCE API ────────────────────────────────────────────────

@app.route("/api/inventory/intelligence", methods=["GET"])
@login_required
def api_inventory_intelligence():
    try:
        data = intelligence_service.calculate_intelligence(db, Medicine, MedicineBatch, Sale)
        # Generate AI summary dynamically if requested or just include it
        # To speed up UI, maybe AI summary is a separate endpoint or we do it inline if fast enough.
        # Let's do it inline.
        ai_summary = intelligence_service.generate_ai_advisor_summary(data)
        data["ai_summary"] = ai_summary
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/export/intelligence")
@login_required
def api_export_intelligence():
    try:
        data = intelligence_service.calculate_intelligence(db, Medicine, MedicineBatch, Sale)
        import io, csv
        output = io.StringIO()
        writer = csv.writer(output)
        
        # We can export runouts
        writer.writerow(["--- RUNOUT PREDICTIONS ---"])
        writer.writerow(["Medicine ID", "Name", "Current Stock", "Avg Daily Sales", "Days to Runout", "Confidence"])
        for r in data["runouts"]:
            writer.writerow([r["id"], r["name"], r["current_stock"], r["avg_daily_sales"], r["days_to_runout"], r["confidence"]])
            
        writer.writerow([])
        writer.writerow(["--- REORDER RECOMMENDATIONS ---"])
        writer.writerow(["Medicine ID", "Name", "Current Stock", "Reorder Qty", "Days Remaining", "Priority", "Confidence"])
        for r in data["reorders"]:
            writer.writerow([r["id"], r["name"], r["current_stock"], r["reorder_qty"], r["days_remaining"], r["priority"], r["confidence"]])
            
        writer.writerow([])
        writer.writerow(["--- DEAD STOCK ---"])
        writer.writerow(["Medicine ID", "Name", "Current Stock", "Inventory Value"])
        for r in data["dead_stock"]:
            writer.writerow([r["id"], r["name"], r["current_stock"], r["inventory_value"]])
            
        writer.writerow([])
        writer.writerow(["--- EXPIRY RISKS ---"])
        writer.writerow(["Medicine ID", "Name", "Batch", "Expiry Date", "Units At Risk", "Est Loss"])
        for r in data["expiry_risks"]:
            writer.writerow([r["id"], r["name"], r["batch"], r["expiry_date"], r["units_at_risk"], r["estimated_loss"]])

        return output.getvalue(), 200, {
            "Content-Type": "text/csv",
            "Content-Disposition": "attachment;filename=inventory_intelligence.csv"
        }
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── EXPORTS & REPORTS ─────────────────────────────────────────────────────────

@app.route("/api/export/csv")
@login_required
def api_export_csv():
    rows = Medicine.query.order_by(Medicine.name.asc()).all()
    import io, csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Category", "Quantity", "Min Stock", "Expiry Date", "Supplier", "Price (₹)", "Stock Value (₹)"])
    for r in rows:
        stock_value = (r.quantity or 0) * (r.price or 0)
        writer.writerow([r.name, r.category, r.quantity, r.min_stock, r.expiry_date or "", r.supplier, f"{r.price or 0:.2f}", f"{stock_value:.2f}"])
    return output.getvalue(), 200, {"Content-Type": "text/csv", "Content-Disposition": "attachment; filename=inventory.csv"}

@app.route("/api/export/alerts/csv")
@login_required
def api_export_alerts_csv():
    today = date.today().isoformat()
    rows = Medicine.query.filter(
        db.or_(
            Medicine.quantity < Medicine.min_stock,
            db.and_(Medicine.expiry_date != None, Medicine.expiry_date != "", Medicine.expiry_date <= today)
        )
    ).order_by(Medicine.name.asc()).all()
    import io, csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Quantity", "Min Stock", "Expiry Date", "Alert Type"])
    for r in rows:
        atype = "Low Stock" if (r.quantity or 0) < (r.min_stock or 0) else "Expired"
        writer.writerow([r.name, r.quantity, r.min_stock, r.expiry_date or "", atype])
    return output.getvalue(), 200, {"Content-Type": "text/csv", "Content-Disposition": "attachment; filename=alerts.csv"}

@app.route("/api/stock-valuation")
@login_required
def api_stock_valuation():
    total = db.session.query(db.func.sum(Medicine.quantity * Medicine.price)).scalar()
    return jsonify({"stock_valuation": total or 0})

@app.route("/api/chart/category")
@login_required
def api_chart_category():
    results = db.session.query(Medicine.category, db.func.sum(Medicine.quantity)).group_by(Medicine.category).all()
    rows = [{"category": cat or "Uncategorized", "total": tot} for cat, tot in results]
    return jsonify(rows)

@app.route("/api/search")
@login_required
def api_search():
    """Search medicines by name, category, or supplier"""
    q = request.args.get("q", "").strip()
    if not q or len(q) < 2:
        return jsonify([])
    
    search_term = f"%{q}%"
    results = Medicine.query.filter(
        db.or_(
            Medicine.name.ilike(search_term),
            Medicine.category.ilike(search_term),
            Medicine.supplier.ilike(search_term)
        )
    ).order_by(Medicine.name.asc()).limit(15).all()
    
    rows = []
    for r in results:
        rows.append({
            "id": str(r.id),
            "name": r.name,
            "category": r.category,
            "quantity": r.quantity,
            "min_stock": r.min_stock,
            "expiry_date": r.expiry_date,
            "supplier": r.supplier,
            "price": r.price,
            "created_at": r.created_at
        })
    return jsonify({"data": rows, "page": page, "page_size": per_page, "total_records": total})

# ─── ANALYTICS API (NEW) ──────────────────────────────────────────────────────

@app.route("/api/analytics/sales")
@login_required
def api_analytics_sales():
    """Weekly sales data for charts."""
    thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
    sales = Sale.query.filter(Sale.timestamp >= thirty_days_ago).all()
    grouped = {}
    for s in sales:
        date_str = s.timestamp[:10] if s.timestamp else "Unknown"
        if date_str not in grouped:
            grouped[date_str] = {"count": 0, "revenue": 0}
        grouped[date_str]["count"] += 1
        grouped[date_str]["revenue"] += (s.total_amount or 0)
    
    rows = []
    for k, v in sorted(grouped.items()):
        rows.append({"sale_date": k, "count": v["count"], "revenue": v["revenue"]})
    return jsonify(rows)

@app.route("/api/analytics/top-medicines")
@login_required
def api_analytics_top():
    """Top selling medicines from sales data."""
    thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
    sales = Sale.query.filter(Sale.timestamp >= thirty_days_ago).all()
    counts = {}
    for s in sales:
        try:
            items = json.loads(s.items_json or "[]")
            for item in items:
                name = item.get("name", "Unknown")
                counts[name] = counts.get(name, 0) + item.get("qty", 0)
        except (json.JSONDecodeError, TypeError):
            pass
    top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
    return jsonify([{"name": n, "qty": q} for n, q in top])

# ─── AI MEDICAL ASSISTANT CHATBOT (GEMINI INTEGRATION) ────────────────────────

import google.generativeai as genai

GEMINI_API_KEY = Config.GEMINI_API_KEY
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel(Config.GEMINI_MODEL)
def get_inventory_context():
    """Return a compact inventory summary for the AI prompt.
    Only includes aggregate counts and lists of flagged items (low stock / expired)."""
    conn = get_db()
    today = date.today().isoformat()
    try:
        total = conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]
        low = conn.execute("SELECT COUNT(*) FROM medicines WHERE quantity < min_stock").fetchone()[0]
        expired = conn.execute("SELECT COUNT(*) FROM medicines WHERE expiry_date != '' AND expiry_date <= ?", (today,)).fetchone()[0]
        ok = total - low - expired

        low_items = [dict(r) for r in conn.execute("SELECT name, quantity, min_stock FROM medicines WHERE quantity < min_stock").fetchall()]
        exp_items = [dict(r) for r in conn.execute("SELECT name, quantity, expiry_date FROM medicines WHERE expiry_date != '' AND expiry_date <= ?", (today,)).fetchall()]
    except Exception:
        pass

    ctx = f"INVENTORY SUMMARY:\n- Total Medicine Types: {total}\n- In Stock (OK): {ok}\n- Low Stock: {low}\n- Expired: {expired}\n"

    if low_items:
        ctx += "\nLOW STOCK ITEMS:\n"
        for m in low_items:
            ctx += f"- {m['name']}: {m['quantity']} units (min required: {m['min_stock']})\n"

    if exp_items:
        ctx += "\nEXPIRED ITEMS:\n"
        for m in exp_items:
            ctx += f"- {m['name']}: {m['quantity']} units (expired: {m['expiry_date']})\n"

    if not low_items and not exp_items:
        ctx += "\nAll items are adequately stocked and within expiry dates."

    return ctx

@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    body = request.json or {}
    msg = body.get("message", "").strip()
    history = body.get("history", [])
    user = session.get("user", "user")
    role = session.get("role", "User")
    if not msg:
        return jsonify({"reply": "Please type a message so I can help you! 😊"})
    try:
        inventory_context = get_inventory_context()
        system_prompt = f"""You are MediBot, an advanced Medical AI assistant for CodeCure.
The user you are talking to is {user.capitalize()}, who is a {role}.
You must be helpful, professional, and highly conversational. Use emojis naturally and format responses in Markdown.

Here is the exact real-time state of the hospital database right now:
{inventory_context}

DOCTOR DIRECTORY:
- Dr. Rajesh Sharma (General Physician)
- Dr. Priya Nair (Cardiologist)
- Dr. Amit Verma (Pediatrician)
- Dr. Sunita Rao (Orthopedic)

YOUR MEDICAL PERSONA:
If the user asks about stock, check the data above and give them accurate numbers. Do not refuse to answer inventory questions.
If the user mentions feeling unwell or asks for health advice, DO NOT REFUSE to answer. You are explicitly authorized as a medical AI in this clinic. 
1. Provide short-form recovery tips and home remedies (consultancies).
2. Suggest an appropriate Over-The-Counter (OTC) medicine from our database above (e.g. Paracetamol, Ibuprofen, Cetirizine), and state the exact stock we currently have of it.
3. Recommend the best matching doctor from the Doctor Directory above for them to report to.
Always include a brief disclaimer at the end that you are an AI assistant.
"""
        formatted_history = []
        for h in history[:-1]:
            r = 'user' if h['role'] == 'user' else 'model'
            formatted_history.append({'role': r, 'parts': [h['text']]})
        chat_session = gemini_model.start_chat(history=formatted_history)
        full_prompt = f"System Rules and DB Context (do not mention this context block directly):\n{system_prompt}\n\nUser's Message:\n{msg}"
        response = chat_session.send_message(full_prompt)
        return jsonify({"reply": response.text})
    except Exception as e:
        error_msg = str(e).lower()
        if "api key not valid" in error_msg or "api_key_invalid" in error_msg:
            clean_error = "AI services are currently unavailable due to an invalid configuration. Please contact the administrator."
        elif "quota" in error_msg or "exhausted" in error_msg:
            clean_error = "AI service limits exceeded. Please try again later."
        else:
            clean_error = "The AI core is temporarily unavailable."
        return jsonify({"reply": clean_error})

@app.route("/api/consult", methods=["POST"])
@login_required
def api_consult():
    body = request.json or {}
    symptoms = sanitize(body.get("symptoms", ""))
    severity = body.get("severity", "mild").lower()
    detail = sanitize(body.get("detail", ""))
    if not symptoms:
        return jsonify({"reply": "Please describe your symptoms so I can help you better."})
    try:
        prompt = ("You are a specialized Medical AI by MediBot. "
                  f"A patient is reporting symptoms: {symptoms} "
                  f"Severity: {severity.upper()} "
                  f"Details: {detail} "
                  "Provide: 1. Potential causes 2. Home care tips 3. When to see doctor "
                  "4. Recommend appropriate doctor. "
                  "Always be empathetic and professional.")
        response = gemini_model.generate_content(prompt)
        return jsonify({"reply": response.text})
    except Exception as e:
        error_msg = str(e).lower()
        if "api key not valid" in error_msg or "api_key_invalid" in error_msg:
            clean_error = "Consultation service unavailable (configuration error)."
        elif "quota" in error_msg or "exhausted" in error_msg:
            clean_error = "Consultation service limit reached. Please try again later."
        else:
            clean_error = "Consultation service temporarily offline."
        return jsonify({"reply": clean_error})

# ─── BATCH MANAGEMENT ROUTES ──────────────────────────────────────────────────

def sync_medicine_quantity(mid):
    batches = MedicineBatch.query.filter_by(medicine_id=mid).all()
    total_qty = sum(b.quantity for b in batches) if batches else 0
    med = Medicine.query.with_for_update().get(mid)
    if med:
        if batches:
            med.quantity = total_qty
        db.session.commit()

@app.route("/api/medicines/<int:mid>/batches", methods=["GET"])
@role_required("Admin", "Pharmacist")
def api_get_batches(mid):
    batches = MedicineBatch.query.filter_by(medicine_id=mid).order_by(MedicineBatch.expiry_date.asc()).all()
    data = []
    for b in batches:
        data.append({
            "id": b.id,
            "medicine_id": b.medicine_id,
            "batch_number": b.batch_number,
            "manufacturing_date": b.manufacturing_date,
            "expiry_date": b.expiry_date,
            "quantity": b.quantity,
            "created_at": b.created_at
        })
    return jsonify(data)

@app.route("/api/medicines/<int:mid>/batches", methods=["POST"])
@role_required("Admin", "Pharmacist")
def api_create_batch(mid):
    data = request.json or {}
    batch_number = data.get("batch_number", "").strip()
    manufacturing_date = data.get("manufacturing_date", "")
    expiry_date = data.get("expiry_date", "")
    quantity = int(data.get("quantity", 0))
    
    if not batch_number:
        return jsonify({"error": "Batch number is required"}), 400
        
    try:
        med = Medicine.query.get(mid)
        if not med:
            return jsonify({"error": "Medicine not found"}), 404
            
        new_batch = MedicineBatch(
            medicine_id=mid,
            batch_number=batch_number,
            manufacturing_date=manufacturing_date,
            expiry_date=expiry_date,
            quantity=quantity
        )
        db.session.add(new_batch)
        db.session.commit()
        
        sync_medicine_quantity(mid)
        
        act = Activity(action="Add Batch", detail=f"{med.name} Batch {batch_number} (Qty: {quantity})", user=session["user"])
        db.session.add(act)
        db.session.commit()
        
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/api/batches/<int:bid>", methods=["PUT"])
@role_required("Admin", "Pharmacist")
def api_update_batch(bid):
    data = request.json or {}
    batch = MedicineBatch.query.get(bid)
    if not batch:
        return jsonify({"error": "Batch not found"}), 404
        
    try:
        batch.batch_number = data.get("batch_number", batch.batch_number)
        batch.manufacturing_date = data.get("manufacturing_date", batch.manufacturing_date)
        batch.expiry_date = data.get("expiry_date", batch.expiry_date)
        if "quantity" in data:
            batch.quantity = int(data["quantity"])
            
        db.session.commit()
        sync_medicine_quantity(batch.medicine_id)
        
        med = Medicine.query.get(batch.medicine_id)
        act = Activity(action="Edit Batch", detail=f"{med.name} Batch {batch.batch_number}", user=session["user"])
        db.session.add(act)
        db.session.commit()
        
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/api/batches/<int:bid>", methods=["DELETE"])
@role_required("Admin", "Pharmacist")
def api_delete_batch(bid):
    batch = MedicineBatch.query.get(bid)
    if not batch:
        return jsonify({"error": "Batch not found"}), 404
        
    try:
        mid = batch.medicine_id
        bnum = batch.batch_number
        med = Medicine.query.get(mid)
        db.session.delete(batch)
        db.session.commit()
        
        sync_medicine_quantity(mid)
        
        act = Activity(action="Delete Batch", detail=f"{med.name} Batch {bnum}", user=session["user"])
        db.session.add(act)
        db.session.commit()
        
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/api/batches/stats", methods=["GET"])
@role_required("Admin", "Pharmacist")
def api_batches_stats():
    today = date.today()
    in_30_days = (today + timedelta(days=30)).isoformat()
    in_60_days = (today + timedelta(days=60)).isoformat()
    today_iso = today.isoformat()
    
    batches = MedicineBatch.query.all()
    
    healthy = 0
    expiring_30 = 0
    expiring_60 = 0
    expired = 0
    empty = 0
    
    for b in batches:
        if b.quantity <= 0:
            empty += 1
            continue
            
        if b.expiry_date:
            if b.expiry_date < today_iso:
                expired += 1
            elif b.expiry_date <= in_30_days:
                expiring_30 += 1
            elif b.expiry_date <= in_60_days:
                expiring_60 += 1
            else:
                healthy += 1
        else:
            healthy += 1 # No expiry date is assumed healthy
            
    return jsonify({
        "healthy": healthy,
        "expiring_30": expiring_30,
        "expiring_60": expiring_60,
        "expired": expired,
        "empty": empty
    })

# ─── USER MANAGEMENT ROUTES ───────────────────────────────────────────────────

@app.route("/api/users", methods=["GET"])
@role_required("Admin")
def api_get_users():
    page = safe_int(request.args.get("page", 1), default=1, minimum=1)
    per_page = safe_int(request.args.get("per_page", 50), default=50, minimum=1, maximum=200)
    
    query = User.query
    total = query.count()
    users = query.limit(per_page).offset((page - 1) * per_page).all()
    
    data = []
    for u in users:
        data.append({
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "is_active": u.is_active,
            "last_login": u.last_login,
            "created_at": u.created_at
        })
    return jsonify({"data": data, "page": page, "page_size": per_page, "total_records": total})

@app.route("/api/users/stats", methods=["GET"])
@role_required("Admin")
def api_users_stats():
    users = User.query.all()
    total = len(users)
    active = sum(1 for u in users if u.is_active)
    disabled = total - active
    
    admins = sum(1 for u in users if u.role == "Admin")
    pharmacists = sum(1 for u in users if u.role == "Pharmacist")
    cashiers = sum(1 for u in users if u.role == "Cashier")
    doctors = sum(1 for u in users if u.role == "Doctor")
    
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    activities = Activity.query.filter(Activity.action == "Login", Activity.timestamp >= today_start).all()
    logged_in_users = set(a.user for a in activities)
    
    return jsonify({
        "total": total,
        "active": active,
        "disabled": disabled,
        "admins": admins,
        "pharmacists": pharmacists,
        "cashiers": cashiers,
        "doctors": doctors,
        "logged_in_today": len(logged_in_users)
    })

@app.route("/api/users", methods=["POST"])
@role_required("Admin")
def api_create_user():
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    role = data.get("role", "Pharmacist")
    
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
        
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 400
        
    try:
        new_user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role=role,
            is_active=1
        )
        db.session.add(new_user)
        
        act = Activity(action="User Creation", detail=f"Created user {username} ({role})", user=session["user"])
        db.session.add(act)
        
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/api/users/<int:uid>", methods=["PUT"])
@role_required("Admin")
def api_update_user(uid):
    data = request.json or {}
    new_username = data.get("username", "").strip()
    new_role = data.get("role")
    
    user = User.query.get(uid)
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    if session.get("user") == user.username and new_role and new_role != "Admin":
        return jsonify({"error": "Admin Self-Protection: You cannot remove your own Admin role"}), 403
        
    if new_username and new_username != user.username:
        if User.query.filter_by(username=new_username).first():
            return jsonify({"error": "Username already exists"}), 400
        user.username = new_username
        
    if new_role:
        user.role = new_role
        
    try:
        act = Activity(action="User Edit", detail=f"Updated user ID {uid} ({user.username})", user=session.get("user"))
        db.session.add(act)
        db.session.commit()
        
        if session.get("user") == user.username:
            session["user"] = new_username
            
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/api/users/<int:uid>/status", methods=["PUT"])
@role_required("Admin")
def api_user_status(uid):
    data = request.json or {}
    is_active = data.get("is_active")
    
    user = User.query.get(uid)
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    if session.get("user") == user.username and not is_active:
        return jsonify({"error": "Admin Self-Protection: You cannot disable your own account"}), 403
        
    try:
        user.is_active = 1 if is_active else 0
        action_name = "Account Enable" if is_active else "Account Disable"
        act = Activity(action=action_name, detail=f"Set {user.username} active={user.is_active}", user=session.get("user"))
        db.session.add(act)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/api/users/<int:uid>/reset_password", methods=["PUT"])
@role_required("Admin")
def api_user_reset_password(uid):
    data = request.json or {}
    password = data.get("password", "")
    confirm_password = data.get("confirm_password", "")
    
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
        
    if password != confirm_password:
        return jsonify({"error": "Passwords do not match"}), 400
        
    user = User.query.get(uid)
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    try:
        user.password_hash = generate_password_hash(password)
        act = Activity(action="Password Reset", detail=f"Reset password for {user.username}", user=session.get("user"))
        db.session.add(act)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/api/activity_logs", methods=["GET"])
@role_required("Admin")
def api_activity_logs():
    timeframe = request.args.get("timeframe", "all")
    query = Activity.query.order_by(Activity.id.desc())
    
    now = datetime.utcnow()
    if timeframe == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        query = query.filter(Activity.timestamp >= start_date.isoformat())
    elif timeframe == "week":
        start_date = now - timedelta(days=7)
        query = query.filter(Activity.timestamp >= start_date.isoformat())
    elif timeframe == "month":
        start_date = now - timedelta(days=30)
        query = query.filter(Activity.timestamp >= start_date.isoformat())
        
    logs = query.limit(500).all()
    
    data = []
    for log in logs:
        data.append({
            "id": log.id,
            "action": log.action,
            "detail": log.detail,
            "user": log.user,
            "timestamp": log.timestamp
        })
        
    return jsonify(data)

# ─── SUPPLIER MANAGEMENT API (Phase G8) ────────────────────────────────────────

@app.route("/api/suppliers", methods=["GET"])
@login_required
def api_get_suppliers():
    page = safe_int(request.args.get("page", 1), default=1, minimum=1)
    per_page = safe_int(request.args.get("per_page", 50), default=50, minimum=1, maximum=200)
    query = Supplier.query
    total = query.count()
    suppliers = query.limit(per_page).offset((page - 1) * per_page).all()
    data = [{
        "id": s.id,
        "supplier_name": s.supplier_name,
        "contact_person": getattr(s, "contact_person", ""),
        "phone": s.phone,
        "email": s.email,
        "address": s.address,
        "gst_number": s.gst_number,
        "is_active": s.is_active
    } for s in suppliers]
    return jsonify({"data": data, "page": page, "page_size": per_page, "total_records": total})

@app.route("/api/suppliers", methods=["POST"])
@role_required("Admin")
def api_add_supplier():
    data = request.json or {}
    name = data.get("supplier_name", "").strip()
    if not name:
        return jsonify({"error": "Supplier name is required"}), 400
        
    if Supplier.query.filter(Supplier.supplier_name.ilike(name)).first():
        return jsonify({"error": "Supplier already exists"}), 400
        
    s = Supplier(
        supplier_name=name,
        contact_person=data.get("contact_person", ""),
        phone=data.get("phone", ""),
        email=data.get("email", ""),
        address=data.get("address", ""),
        gst_number=data.get("gst_number", "")
    )
    db.session.add(s)
    act = Activity(action="Supplier Created", detail=f"Added supplier: {name}", user=session.get("user"))
    db.session.add(act)
    db.session.commit()
    return jsonify({"success": True, "id": s.id})

@app.route("/api/suppliers/<int:sid>", methods=["PUT"])
@role_required("Admin")
def api_update_supplier(sid):
    s = Supplier.query.get_or_404(sid)
    data = request.json or {}
    if "supplier_name" in data:
        name = data["supplier_name"].strip()
        existing = Supplier.query.filter(Supplier.supplier_name.ilike(name), Supplier.id != sid).first()
        if existing:
            return jsonify({"error": "Supplier name already in use"}), 400
        s.supplier_name = name
    if "contact_person" in data:
        s.contact_person = data["contact_person"]
    if "phone" in data:
        s.phone = data["phone"]
    if "email" in data:
        s.email = data["email"]
    if "address" in data:
        s.address = data["address"]
    if "gst_number" in data:
        s.gst_number = data["gst_number"]
    if "is_active" in data:
        s.is_active = int(data["is_active"])
        
    act = Activity(action="Supplier Updated", detail=f"Updated supplier: {s.supplier_name}", user=session.get("user"))
    db.session.add(act)
    db.session.commit()
    return jsonify({"success": True})

# ─── PURCHASE ORDER API (Phase G8) ─────────────────────────────────────────────

import po_service

@app.route("/api/purchase-orders", methods=["GET"])
@login_required
def api_get_pos():
    page = safe_int(request.args.get("page", 1), default=1, minimum=1)
    per_page = safe_int(request.args.get("per_page", 50), default=50, minimum=1, maximum=200)
    query = PurchaseOrder.query.order_by(PurchaseOrder.id.desc())
    total = query.count()
    pos = query.limit(per_page).offset((page - 1) * per_page).all()
    # Eager fetch suppliers to attach names
    suppliers = {s.id: s.supplier_name for s in Supplier.query.all()}
    
    data = [{
        "id": p.id,
        "po_number": p.po_number,
        "supplier_id": p.supplier_id,
        "supplier_name": suppliers.get(p.supplier_id, "Unknown"),
        "created_by": p.created_by,
        "status": p.status,
        "expected_delivery_date": p.expected_delivery_date,
        "notes": p.notes,
        "created_at": p.created_at
    } for p in pos]
    return jsonify({"data": data, "page": page, "page_size": per_page, "total_records": total})

@app.route("/api/purchase-orders/from-intelligence", methods=["POST"])
@role_required("Admin")
def api_po_from_intelligence():
    data = request.json or {}
    supplier_id = data.get("supplier_id")
    items = data.get("items", []) # list of dicts: medicine_id, reorder_qty
    if not supplier_id or not items:
        return jsonify({"error": "Supplier ID and items required"}), 400
        
    try:
        po = po_service.generate_draft_from_intelligence(db, PurchaseOrder, PurchaseOrderItem, supplier_id, items, session.get("user"))
        act = Activity(action="PO Created", detail=f"Generated Draft PO {po.po_number} from Intelligence", user=session.get("user"))
        db.session.add(act)
        db.session.commit()
        return jsonify({"success": True, "po_id": po.id, "po_number": po.po_number})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@app.route("/api/purchase-orders/<int:po_id>/status", methods=["PUT"])
@role_required("Admin")
def api_po_status(po_id):
    data = request.json or {}
    target = data.get("status")
    po = PurchaseOrder.query.get_or_404(po_id)
    
    if not po_service.validate_transition(po.status, target):
        return jsonify({"error": f"Invalid state transition from {po.status} to {target}"}), 400
        
    po.status = target
    act = Activity(action=f"PO {target}", detail=f"Status changed to {target} for {po.po_number}", user=session.get("user"))
    db.session.add(act)
    db.session.commit()
    return jsonify({"success": True, "status": po.status})

@app.route("/api/purchase-orders/<int:po_id>/receive", methods=["POST"])
@role_required("Admin")
def api_po_receive(po_id):
    data = request.json or {}
    item_id = data.get("item_id")
    received_qty = safe_int(data.get("received_qty", 0))
    batch_number = data.get("batch_number", "").strip()
    mfg_date = data.get("manufacturing_date", "")
    exp_date = data.get("expiry_date", "")
    
    if not all([item_id, received_qty > 0, batch_number]):
        return jsonify({"error": "Item ID, positive received quantity, and batch number required"}), 400
        
    try:
        po = po_service.receive_po_item(db, app, PurchaseOrder, PurchaseOrderItem, MedicineBatch, po_id, item_id, received_qty, batch_number, mfg_date, exp_date)
        act = Activity(action="Batch Created Through PO", detail=f"Received {received_qty} units on {po.po_number}", user=session.get("user"))
        db.session.add(act)
        db.session.commit()
        return jsonify({"success": True, "po_status": po.status})
    except ValueError as ve:
        db.session.rollback()
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/api/purchase-orders/<int:po_id>/pdf", methods=["GET"])
@login_required
def api_po_pdf(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    supplier = Supplier.query.get(po.supplier_id)
    items = PurchaseOrderItem.query.filter_by(po_id=po.id).all()
    med_ids = [i.medicine_id for i in items]
    medicines = Medicine.query.filter(Medicine.id.in_(med_ids)).all()
    medicine_map = {m.id: m.name for m in medicines}
    
    try:
        pdf_bytes = po_service.generate_po_pdf(po, supplier, items, medicine_map)
        from flask import make_response
        response = make_response(pdf_bytes.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename={po.po_number}.pdf'
        return response
    except Exception as e:
        return f"Error generating PDF: {str(e)}", 500

@app.route("/api/purchase-orders/<int:po_id>/items", methods=["GET"])
@login_required
def api_get_po_items(po_id):
    items = PurchaseOrderItem.query.filter_by(po_id=po_id).all()
    med_ids = [i.medicine_id for i in items]
    medicines = Medicine.query.filter(Medicine.id.in_(med_ids)).all()
    medicine_map = {m.id: m.name for m in medicines}
    
    data = [{
        "id": i.id,
        "medicine_id": i.medicine_id,
        "medicine_name": medicine_map.get(i.medicine_id, "Unknown"),
        "requested_qty": i.requested_qty,
        "received_qty": i.received_qty,
        "expected_unit_cost": i.expected_unit_cost,
        "line_total": i.line_total
    } for i in items]
    return jsonify(data)

@app.route("/api/procurement/analytics", methods=["GET"])
@role_required("Admin")
def api_procurement_analytics():
    # Open Purchase Orders
    open_pos = PurchaseOrder.query.filter(PurchaseOrder.status.in_(["Draft", "Pending", "Approved", "Ordered", "Partially Received"])).all()
    
    # Calculate Outstanding Value
    outstanding_val = 0.0
    for po in open_pos:
        items = PurchaseOrderItem.query.filter_by(po_id=po.id).all()
        for i in items:
            remaining = i.requested_qty - i.received_qty
            if remaining > 0:
                outstanding_val += (remaining * i.expected_unit_cost)
                
    # Orders this month
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0).isoformat()
    month_orders = PurchaseOrder.query.filter(PurchaseOrder.created_at >= month_start).count()
    
    # Top Suppliers
    page = safe_int(request.args.get("page", 1), default=1, minimum=1)
    per_page = safe_int(request.args.get("per_page", 50), default=50, minimum=1, maximum=200)
    query = Supplier.query
    total = query.count()
    suppliers = query.limit(per_page).offset((page - 1) * per_page).all()
    supplier_orders = {}
    for po in PurchaseOrder.query.all():
        supplier_orders[po.supplier_id] = supplier_orders.get(po.supplier_id, 0) + 1
        
    top_suppliers = []
    for sid, count in sorted(supplier_orders.items(), key=lambda x: x[1], reverse=True)[:5]:
        sup = next((s for s in suppliers if s.id == sid), None)
        if sup:
            top_suppliers.append({"name": sup.supplier_name, "orders": count})
            
    return jsonify({
        "open_orders": len(open_pos),
        "outstanding_value": round(outstanding_val, 2),
        "orders_this_month": month_orders,
        "avg_lead_time": 4, # Mocked for now
        "top_suppliers": top_suppliers
    })

# ─── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()

    # ── ngrok tunnel for temporary public access ──
    # Only run in main process, not Flask reloader subprocess, and ONLY in debug mode
    if app.config["DEBUG"] and not os.environ.get("WERKZEUG_RUN_MAIN"):
        try:
            from pyngrok import ngrok, conf
            ngrok_token = os.environ.get("NGROK_AUTHTOKEN", "")
            if ngrok_token:
                conf.get_default().auth_token = ngrok_token
                public_url = ngrok.connect(5000)
                print("\n" + "=" * 60)
                print("[LIVE] Your temporary live website link: " + str(public_url))
                print("=" * 60 + "\n")
            else:
                print("\n[INFO] To enable public URL, set NGROK_AUTHTOKEN env variable.")
                print("[INFO] Get your free token at: https://dashboard.ngrok.com/signup\n")
        except ImportError:
            print("\n[TIP] Install pyngrok (pip install pyngrok) for a public URL")
        except Exception as e:
            print("\n[WARN] ngrok tunnel failed: " + str(e))

    app.run(debug=app.config["DEBUG"])
