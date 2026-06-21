from app import app, db
from models_sqlalchemy import Medicine

with app.app_context():
    meds = [
        Medicine(name="Amlodipine 5mg", category="Cardiology", min_stock=10, quantity=50, price=5.0),
        Medicine(name="Amlodipine 10mg", category="Cardiology", min_stock=10, quantity=50, price=8.0),
        Medicine(name="Cefotaxime", category="Antibiotic", min_stock=5, quantity=20, price=15.0),
        Medicine(name="Cefuroxime", category="Antibiotic", min_stock=5, quantity=20, price=18.0),
        Medicine(name="Dolo 650", category="Analgesic", min_stock=20, quantity=100, price=2.0),
        Medicine(name="Dolo 500", category="Analgesic", min_stock=20, quantity=100, price=1.5)
    ]
    for m in meds:
        if not Medicine.query.filter_by(name=m.name).first():
            db.session.add(m)
    db.session.commit()
    print("Test medicines added.")
