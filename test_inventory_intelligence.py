import unittest
from datetime import datetime, timedelta
import json
from app import app, db
from models_sqlalchemy import Medicine, MedicineBatch, Sale
import intelligence_service

class InventoryIntelligenceTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        db.create_all()
        
        # Seed test data
        self.now = datetime.utcnow()
        day_10 = self.now - timedelta(days=10)
        day_40 = self.now - timedelta(days=40)
        day_70 = self.now - timedelta(days=70)
        
        # Fast moving med (Paracetamol) - Runout risk
        m1 = Medicine(name="Paracetamol", quantity=20, min_stock=50, price=10.0)
        
        # Slow moving med (Vitamin C) - Dead stock / Slow moving
        m2 = Medicine(name="Vitamin C", quantity=200, min_stock=10, price=5.0)
        
        # Med with expiring batch (Amoxicillin)
        m3 = Medicine(name="Amoxicillin", quantity=100, min_stock=20, price=20.0)
        
        db.session.add_all([m1, m2, m3])
        db.session.commit()
        
        # Batches
        b1 = MedicineBatch(medicine_id=m3.id, batch_number="EXP1", expiry_date=(self.now + timedelta(days=5)).strftime("%Y-%m-%d"), quantity=50)
        b2 = MedicineBatch(medicine_id=m3.id, batch_number="EXP2", expiry_date=(self.now + timedelta(days=100)).strftime("%Y-%m-%d"), quantity=50)
        
        db.session.add_all([b1, b2])
        
        # Sales
        # Paracetamol sold heavily recently
        s1 = Sale(invoice_id="INV1", items_json=json.dumps([{"name": "Paracetamol", "qty": 30}]), timestamp=day_10.isoformat(), sold_by="Admin")
        s2 = Sale(invoice_id="INV2", items_json=json.dumps([{"name": "Paracetamol", "qty": 10}]), timestamp=day_40.isoformat(), sold_by="Admin")
        s3 = Sale(invoice_id="INV3", items_json=json.dumps([{"name": "Paracetamol", "qty": 5}]), timestamp=day_70.isoformat(), sold_by="Admin")
        
        # Amoxicillin sold moderately
        s4 = Sale(invoice_id="INV4", items_json=json.dumps([{"name": "Amoxicillin", "qty": 10}]), timestamp=day_10.isoformat(), sold_by="Admin")
        
        # Vitamin C has no sales
        
        db.session.add_all([s1, s2, s3, s4])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_calculate_intelligence(self):
        res = intelligence_service.calculate_intelligence(db, Medicine, MedicineBatch, Sale)
        
        # Verify runout
        runouts = [r for r in res["runouts"]["data"] if r["name"] == "Paracetamol"]
        self.assertTrue(len(runouts) > 0)
        para_runout = runouts[0]
        self.assertTrue(para_runout["avg_daily_sales"] > 0)
        self.assertTrue(para_runout["days_to_runout"] < 30)
        
        # Verify Reorder (Paracetamol needs reorder due to low stock and high runout)
        reorders = [r for r in res["reorders"]["data"] if r["name"] == "Paracetamol"]
        self.assertTrue(len(reorders) > 0)
        para_reorder = reorders[0]
        self.assertTrue(para_reorder["reorder_qty"] > 0)
        
        # Verify Dead Stock (Vitamin C has 0 sales in 90 days but has stock)
        dead_stock = [r for r in res["dead_stock"]["data"] if r["name"] == "Vitamin C"]
        self.assertTrue(len(dead_stock) > 0)
        self.assertEqual(dead_stock[0]["inventory_value"], 1000.0) # 200 * 5.0
        
        # Verify Expiry Loss
        # Amoxicillin sells ~10/30 = 0.33 per day (weighted). Expiry in 5 days means ~1.6 sold.
        # Batch EXP1 has 50. So 48+ should be lost.
        expiry_risks = [r for r in res["expiry_risks"]["data"] if r["name"] == "Amoxicillin"]
        self.assertTrue(len(expiry_risks) > 0)
        
    def test_ai_advisor(self):
        # We don't actually hit the API without a key, but verify the function doesn't crash
        res = intelligence_service.calculate_intelligence(db, Medicine, MedicineBatch, Sale)
        summary = intelligence_service.generate_ai_advisor_summary(res)
        self.assertIsInstance(summary, str)

if __name__ == '__main__':
    unittest.main()
