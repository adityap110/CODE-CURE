from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Medicine(db.Model):
    __tablename__ = 'medicines'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    category = db.Column(db.String)
    quantity = db.Column(db.Integer, default=0)
    min_stock = db.Column(db.Integer, default=10)
    expiry_date = db.Column(db.String)
    supplier = db.Column(db.String)
    price = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.String, default=lambda: datetime.utcnow().isoformat())

class Activity(db.Model):
    __tablename__ = 'activity'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    action = db.Column(db.String)
    detail = db.Column(db.String)
    user = db.Column(db.String)
    timestamp = db.Column(db.String, default=lambda: datetime.utcnow().isoformat())

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String, unique=True, nullable=False)
    password_hash = db.Column(db.String, nullable=False)
    role = db.Column(db.String, nullable=False, default='Pharmacist')
    last_login = db.Column(db.String)
    profile_image = db.Column(db.String)
    is_active = db.Column(db.Integer, default=1)
    created_at = db.Column(db.String, default=lambda: datetime.utcnow().isoformat())

class Sale(db.Model):
    __tablename__ = 'sales'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    invoice_id = db.Column(db.String, unique=True, nullable=False)
    customer_name = db.Column(db.String, default='Walk-in')
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    payment_method = db.Column(db.String, default='Cash')
    sold_by = db.Column(db.String, nullable=False)
    items_json = db.Column(db.String)
    timestamp = db.Column(db.String, default=lambda: datetime.utcnow().isoformat())

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    supplier_name = db.Column(db.String, nullable=False)
    contact_person = db.Column(db.String)
    phone = db.Column(db.String)
    email = db.Column(db.String)
    address = db.Column(db.String)
    gst_number = db.Column(db.String)
    is_active = db.Column(db.Integer, default=1)
    created_at = db.Column(db.String, default=lambda: datetime.utcnow().isoformat())

class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    po_number = db.Column(db.String, unique=True, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    created_by = db.Column(db.String, nullable=False)
    status = db.Column(db.String, default='Draft') # Draft, Pending, Approved, Ordered, Partially Received, Received, Cancelled
    expected_delivery_date = db.Column(db.String)
    notes = db.Column(db.String)
    created_at = db.Column(db.String, default=lambda: datetime.utcnow().isoformat())

class PurchaseOrderItem(db.Model):
    __tablename__ = 'purchase_order_items'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    po_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id', ondelete='CASCADE'), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id'), nullable=False)
    requested_qty = db.Column(db.Integer, nullable=False)
    received_qty = db.Column(db.Integer, default=0)
    expected_unit_cost = db.Column(db.Float, default=0.0)
    line_total = db.Column(db.Float, default=0.0)

class MedicineBatch(db.Model):
    __tablename__ = 'medicine_batches'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id', ondelete='CASCADE'), nullable=False)
    batch_number = db.Column(db.String, nullable=False)
    manufacturing_date = db.Column(db.String)
    expiry_date = db.Column(db.String)
    quantity = db.Column(db.Integer, default=0)
    created_at = db.Column(db.String, default=lambda: datetime.utcnow().isoformat())
