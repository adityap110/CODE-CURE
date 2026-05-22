"""
CodeCure — Database Models & Helpers
MongoDB Backend for Vercel Serverless Deployment
"""
from pymongo import MongoClient, ASCENDING, DESCENDING
import os
from datetime import datetime, date
from config import Config

# We will cache the MongoClient to reuse across serverless function invocations
_client = None

def get_db():
    """Get a MongoDB database instance."""
    global _client
    if _client is None:
        _client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=5000)
    return _client[Config.MONGO_DB_NAME]


def init_db():
    """Initialize MongoDB collections, indexes, and seed demo data if empty."""
    db = get_db()

    # Create Indexes
    db.medicines.create_index([("name", ASCENDING)])
    db.medicines.create_index([("category", ASCENDING)])
    db.medicines.create_index([("expiry_date", ASCENDING)])
    db.medicines.create_index([("name", "text"), ("category", "text"), ("supplier", "text")])
    
    db.activity.create_index([("timestamp", DESCENDING)])
    
    db.sales.create_index([("timestamp", DESCENDING)])
    db.sales.create_index([("invoice_id", ASCENDING)], unique=True)
    
    db.users.create_index([("username", ASCENDING)], unique=True)

    # Seed demo medicines if empty
    if db.medicines.count_documents({}) == 0:
        demo_medicines = [
            {"name": "Paracetamol 500mg", "category": "Analgesic", "quantity": 150, "min_stock": 20, "expiry_date": "2025-12-01", "supplier": "MedCo", "price": 2.50, "created_at": datetime.utcnow().isoformat()},
            {"name": "Amoxicillin 250mg", "category": "Antibiotic", "quantity": 8, "min_stock": 15, "expiry_date": "2025-09-15", "supplier": "PharmEx", "price": 12.00, "created_at": datetime.utcnow().isoformat()},
            {"name": "Pantoprazole 40mg", "category": "Antacid", "quantity": 60, "min_stock": 10, "expiry_date": "2026-03-20", "supplier": "HealthPlus", "price": 5.75, "created_at": datetime.utcnow().isoformat()},
            {"name": "Cetirizine 10mg",   "category": "Antihistamine", "quantity": 3, "min_stock": 10, "expiry_date": "2024-06-01", "supplier": "MedCo", "price": 3.00, "created_at": datetime.utcnow().isoformat()},
            {"name": "Metformin 500mg",   "category": "Antidiabetic", "quantity": 200, "min_stock": 30, "expiry_date": "2026-01-10", "supplier": "DiaCare", "price": 1.80, "created_at": datetime.utcnow().isoformat()},
            {"name": "Atorvastatin 10mg", "category": "Statin", "quantity": 45, "min_stock": 20, "expiry_date": "2026-07-22", "supplier": "CardioMed", "price": 8.50, "created_at": datetime.utcnow().isoformat()},
            {"name": "Vitamin C 500mg",   "category": "Vitamin", "quantity": 12, "min_stock": 25, "expiry_date": "2025-11-30", "supplier": "NutriLife", "price": 4.00, "created_at": datetime.utcnow().isoformat()},
            {"name": "Ibuprofen 400mg",   "category": "Analgesic", "quantity": 90, "min_stock": 15, "expiry_date": "2026-02-14", "supplier": "PharmEx", "price": 3.25, "created_at": datetime.utcnow().isoformat()}
        ]
        db.medicines.insert_many(demo_medicines)
        log_activity("System Init", "Demo data loaded", "system")


def log_activity(action, detail, user="system"):
    """Log an activity event to the database."""
    db = get_db()
    db.activity.insert_one({
        "action": action,
        "detail": detail,
        "user": user,
        "timestamp": datetime.utcnow().isoformat()
    })


def record_sale(invoice_id, total, items_json, sold_by, customer="Walk-in", payment="Cash", discount=0):
    """Record a completed sale to the sales table."""
    db = get_db()
    db.sales.insert_one({
        "invoice_id": invoice_id,
        "customer_name": customer,
        "total_amount": total,
        "discount": discount,
        "payment_method": payment,
        "sold_by": sold_by,
        "items_json": items_json,
        "timestamp": datetime.utcnow().isoformat()
    })
