"""
CodeCure — Centralized Configuration
"""
import os
import secrets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    # Check if we are running in production
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")

    # Use highly secure random if none provided
    _secret = os.environ.get("SECRET_KEY")
    if FLASK_ENV == "production" and not _secret:
        raise RuntimeError("CRITICAL ERROR: SECRET_KEY environment variable is mandatory in production!")
    SECRET_KEY = _secret or secrets.token_hex(32)
    
    # SQLAlchemy Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'codecure.db')}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Legacy SQLite Configuration
    DB_PATH = os.path.join(BASE_DIR, "codecure.db")
    
    # Security Requirements
    DEBUG = (FLASK_ENV != "production")
    
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = (FLASK_ENV == "production")
    
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    
    DEFAULT_ADMIN_PASSWORD = os.environ.get("DEFAULT_ADMIN_PASSWORD", "")
    
    # Rate limiting
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_COOLDOWN_SECONDS = 300
    
    # Pagination
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 200
    
    # Upload limits
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024 # 5MB limit
    
    
    # Alert thresholds
    EXPIRY_WARN_DAYS = 30
    EXPIRY_CRITICAL_DAYS = 7

    # Pharmacy Branding
    PHARMACY_NAME = os.environ.get("PHARMACY_NAME", "CodeCure Pharmacy")
    PHARMACY_ADDRESS = os.environ.get("PHARMACY_ADDRESS", "123 Health Ave, Wellness City")
    PHARMACY_PHONE = os.environ.get("PHARMACY_PHONE", "+1 (555) 123-4567")
    PHARMACY_GST = os.environ.get("PHARMACY_GST", "GSTIN1234567890")
    PHARMACY_LOGO = os.environ.get("PHARMACY_LOGO", "")
