"""
CodeCure — Centralized Configuration
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "codecure_secret_2025")
    
    # MongoDB Configuration
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
    MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "codecure_db")
    
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyA27t-9dcW0hTOiZ1nLWVry4RX1kTYi2vI")
    GEMINI_MODEL = "gemini-2.5-flash"
    
    # Session
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    
    # Rate limiting
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_COOLDOWN_SECONDS = 300
    
    # Pagination
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 200
    
    # Alert thresholds
    EXPIRY_WARN_DAYS = 30
    EXPIRY_CRITICAL_DAYS = 7

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
