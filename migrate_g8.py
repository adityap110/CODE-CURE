from app import app, db
from models_sqlalchemy import Supplier, PurchaseOrder, PurchaseOrderItem
import sqlite3

with app.app_context():
    # Attempt to add contact_person to suppliers if it doesn't exist
    try:
        conn = sqlite3.connect('codecure.db')
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE suppliers ADD COLUMN contact_person VARCHAR")
        conn.commit()
        conn.close()
        print("Added contact_person to suppliers.")
    except Exception as e:
        print("contact_person might already exist or error:", e)
    
    # Create new tables
    db.create_all()
    print("Database schema updated successfully.")
