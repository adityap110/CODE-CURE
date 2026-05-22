"""
CodeCure — Utility Functions
Input validation, sanitization, and shared helpers.
"""
import re
import html
from datetime import datetime, date, timedelta
from functools import wraps
from flask import session, jsonify, request, redirect, url_for


# ── Input Sanitization ───────────────────────────────────────────────────────

def sanitize(text):
    """Strip and escape HTML entities from user input."""
    if not isinstance(text, str):
        return text
    return html.escape(text.strip())


def sanitize_dict(data, keys):
    """Sanitize specific keys in a dictionary."""
    result = {}
    for k in keys:
        val = data.get(k, "")
        result[k] = sanitize(val) if isinstance(val, str) else val
    return result


# ── Validation ───────────────────────────────────────────────────────────────

def validate_medicine_data(data):
    """Validate medicine data for add/edit operations. Returns list of errors."""
    errors = []
    name = data.get("name", "")
    if not isinstance(name, str) or not name.strip():
        errors.append("Medicine name is required")
    elif len(name) > 255:
        errors.append("Medicine name too long (max 255 chars)")

    try:
        qty = int(data.get("quantity", 0))
        if qty < 0:
            errors.append("Quantity cannot be negative")
    except (ValueError, TypeError):
        errors.append("Quantity must be a number")

    try:
        min_s = int(data.get("min_stock", 10))
        if min_s < 0:
            errors.append("Min stock cannot be negative")
    except (ValueError, TypeError):
        errors.append("Min stock must be a number")

    try:
        price = float(data.get("price", 0))
        if price < 0:
            errors.append("Price cannot be negative")
    except (ValueError, TypeError):
        errors.append("Price must be a valid number")

    expiry = data.get("expiry_date", "")
    if expiry:
        try:
            datetime.strptime(expiry, "%Y-%m-%d")
        except ValueError:
            errors.append("Invalid expiry date format (use YYYY-MM-DD)")

    return errors


def safe_int(val, default=0, minimum=None, maximum=None):
    """Safely convert to int with optional bounds."""
    try:
        result = int(val)
        if minimum is not None:
            result = max(result, minimum)
        if maximum is not None:
            result = min(result, maximum)
        return result
    except (ValueError, TypeError):
        return default


def safe_float(val, default=0.0):
    """Safely convert to float."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# ── Auth Decorators ──────────────────────────────────────────────────────────

def login_required(f):
    """Decorator: Require user to be logged in."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """Decorator: Require specific role(s)."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user" not in session:
                return jsonify({"error": "Unauthorized"}), 401
            if session.get("role") not in roles:
                return jsonify({"error": "Permission denied"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── Date Helpers ─────────────────────────────────────────────────────────────

def days_until_expiry(expiry_str):
    """Calculate days until expiry from an ISO date string."""
    if not expiry_str:
        return None
    try:
        exp = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        return (exp - date.today()).days
    except ValueError:
        return None


def get_expiry_status(expiry_str):
    """Return expiry status: 'expired', 'critical', 'warning', or 'ok'."""
    days = days_until_expiry(expiry_str)
    if days is None:
        return "ok"
    if days <= 0:
        return "expired"
    if days <= 7:
        return "critical"
    if days <= 30:
        return "warning"
    return "ok"
