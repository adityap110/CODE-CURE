from app import app, db
from models_sqlalchemy import Medicine, Supplier, MedicineBatch
from datetime import datetime, timedelta

def populate():
    with app.app_context():
        # Add Suppliers
        suppliers = [
            Supplier(supplier_name="Sun Pharma", contact_person="John Doe", phone="1234567890", email="contact@sunpharma.com", address="Mumbai, India", gst_number="GST123"),
            Supplier(supplier_name="Cipla Ltd", contact_person="Jane Smith", phone="0987654321", email="sales@cipla.com", address="Pune, India", gst_number="GST456"),
            Supplier(supplier_name="Dr. Reddy's", contact_person="Alan Wake", phone="1122334455", email="support@drreddys.com", address="Hyderabad, India", gst_number="GST789"),
            Supplier(supplier_name="GSK Medical", contact_person="Sarah Connor", phone="5544332211", email="info@gsk.com", address="London, UK", gst_number="GST101"),
            Supplier(supplier_name="Pfizer Inc.", contact_person="Neo", phone="9988776655", email="sales@pfizer.com", address="New York, USA", gst_number="GST102")
        ]
        
        for s in suppliers:
            if not Supplier.query.filter_by(supplier_name=s.supplier_name).first():
                db.session.add(s)
        
        db.session.commit()
        
        # Helper dates
        now = datetime.now()
        exp_6m = (now + timedelta(days=180)).strftime("%Y-%m-%d")
        exp_1y = (now + timedelta(days=365)).strftime("%Y-%m-%d")
        exp_2y = (now + timedelta(days=730)).strftime("%Y-%m-%d")
        exp_near = (now + timedelta(days=15)).strftime("%Y-%m-%d")
        
        # Add Medicines
        meds = [
            # Analgesics / Antipyretics
            {"name": "Paracetamol 500mg", "cat": "Analgesic", "qty": 500, "min": 100, "price": 1.5, "sup": "Sun Pharma", "exp": exp_1y, "batch": "PAR123"},
            {"name": "Dolo 650", "cat": "Analgesic", "qty": 800, "min": 200, "price": 2.0, "sup": "Sun Pharma", "exp": exp_2y, "batch": "DOL456"},
            {"name": "Ibuprofen 400mg", "cat": "NSAID", "qty": 300, "min": 50, "price": 3.0, "sup": "Cipla Ltd", "exp": exp_1y, "batch": "IBU789"},
            
            # Antibiotics
            {"name": "Amoxicillin 500mg", "cat": "Antibiotic", "qty": 200, "min": 50, "price": 8.0, "sup": "GSK Medical", "exp": exp_near, "batch": "AMX001"},
            {"name": "Azithromycin 250mg", "cat": "Antibiotic", "qty": 150, "min": 40, "price": 12.0, "sup": "Pfizer Inc.", "exp": exp_6m, "batch": "AZI002"},
            {"name": "Cefixime 200mg", "cat": "Antibiotic", "qty": 100, "min": 30, "price": 15.0, "sup": "Dr. Reddy's", "exp": exp_1y, "batch": "CEF003"},
            
            # Cardiology
            {"name": "Amlodipine 5mg", "cat": "Cardiology", "qty": 400, "min": 100, "price": 5.0, "sup": "Sun Pharma", "exp": exp_2y, "batch": "AML004"},
            {"name": "Atorvastatin 10mg", "cat": "Cardiology", "qty": 250, "min": 80, "price": 9.5, "sup": "Cipla Ltd", "exp": exp_1y, "batch": "ATO005"},
            {"name": "Rosuvastatin 20mg", "cat": "Cardiology", "qty": 180, "min": 50, "price": 18.0, "sup": "Dr. Reddy's", "exp": exp_6m, "batch": "ROS006"},
            
            # Diabetes
            {"name": "Metformin 500mg", "cat": "Anti-diabetic", "qty": 600, "min": 150, "price": 4.0, "sup": "GSK Medical", "exp": exp_2y, "batch": "MET007"},
            {"name": "Glimepiride 1mg", "cat": "Anti-diabetic", "qty": 300, "min": 80, "price": 6.5, "sup": "Pfizer Inc.", "exp": exp_1y, "batch": "GLI008"},
            
            # Respiratory / Allergy
            {"name": "Cetirizine 10mg", "cat": "Antihistamine", "qty": 450, "min": 100, "price": 2.5, "sup": "Cipla Ltd", "exp": exp_2y, "batch": "CET009"},
            {"name": "Levocetirizine 5mg", "cat": "Antihistamine", "qty": 350, "min": 80, "price": 3.5, "sup": "Sun Pharma", "exp": exp_1y, "batch": "LEV010"},
            {"name": "Salbutamol Inhaler", "cat": "Bronchodilator", "qty": 50, "min": 15, "price": 125.0, "sup": "GSK Medical", "exp": exp_1y, "batch": "SAL011"},
            
            # Gastrointestinal
            {"name": "Pantoprazole 40mg", "cat": "Antacid", "qty": 500, "min": 100, "price": 7.0, "sup": "Dr. Reddy's", "exp": exp_1y, "batch": "PAN012"},
            {"name": "Domperidone 10mg", "cat": "Antiemetic", "qty": 200, "min": 50, "price": 4.5, "sup": "Cipla Ltd", "exp": exp_6m, "batch": "DOM013"},
            
            # Vitamins / Supplements
            {"name": "Vitamin C 500mg", "cat": "Supplement", "qty": 1000, "min": 200, "price": 1.5, "sup": "Sun Pharma", "exp": exp_2y, "batch": "VIT014"},
            {"name": "Calcium + Vitamin D3", "cat": "Supplement", "qty": 400, "min": 100, "price": 8.0, "sup": "Pfizer Inc.", "exp": exp_1y, "batch": "CAL015"}
        ]
        
        for m_data in meds:
            # Check if exists
            existing_med = Medicine.query.filter_by(name=m_data["name"]).first()
            if not existing_med:
                med = Medicine(
                    name=m_data["name"],
                    category=m_data["cat"],
                    quantity=m_data["qty"],
                    min_stock=m_data["min"],
                    price=m_data["price"],
                    supplier=m_data["sup"],
                    expiry_date=m_data["exp"]
                )
                db.session.add(med)
                db.session.flush() # To get the med ID
                
                # Add a batch for FEFO tracking
                batch = MedicineBatch(
                    medicine_id=med.id,
                    batch_number=m_data["batch"],
                    manufacturing_date=(now - timedelta(days=60)).strftime("%Y-%m-%d"),
                    expiry_date=m_data["exp"],
                    quantity=m_data["qty"]
                )
                db.session.add(batch)
        
        db.session.commit()
        print("Inventory successfully populated with realistic data!")

if __name__ == "__main__":
    populate()
