import unittest
import json
from datetime import datetime, timedelta, date
from app import app, db, User, Medicine, MedicineBatch, Activity, Sale

class TestBatchManagement(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app.test_client()
        with app.app_context():
            db.create_all()
            self.app.get('/')  # Triggers admin creation
            
            # Create test medicine
            med1 = Medicine(name="Paracetamol 500mg", quantity=100, price=10)
            med2 = Medicine(name="LegacyMed", quantity=50, price=20)
            db.session.add(med1)
            db.session.add(med2)
            db.session.commit()
            
            self.med1_id = med1.id
            self.med2_id = med2.id

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def login(self):
        with self.app.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['role'] = 'Admin'
            sess['cart'] = []

    def test_add_batch_and_sync(self):
        self.login()
        res = self.app.post(f'/api/medicines/{self.med1_id}/batches', json={
            "batch_number": "B001",
            "quantity": 30,
            "expiry_date": (date.today() + timedelta(days=60)).isoformat()
        })
        self.assertEqual(res.status_code, 200)
        
        with app.app_context():
            med = Medicine.query.get(self.med1_id)
            self.assertEqual(med.quantity, 30) # Synced to batch total
            b = MedicineBatch.query.filter_by(medicine_id=self.med1_id).first()
            self.assertIsNotNone(b)
            self.assertEqual(b.quantity, 30)

    def test_fefo_checkout(self):
        self.login()
        # Add 3 batches
        # B1: Expires in 10 days (qty 10)
        # B2: Expires in 20 days (qty 20)
        # B3: Expired (qty 50)
        today = date.today()
        b1_exp = (today + timedelta(days=10)).isoformat()
        b2_exp = (today + timedelta(days=20)).isoformat()
        b3_exp = (today - timedelta(days=5)).isoformat()
        
        self.app.post(f'/api/medicines/{self.med1_id}/batches', json={"batch_number": "B2", "quantity": 20, "expiry_date": b2_exp})
        self.app.post(f'/api/medicines/{self.med1_id}/batches', json={"batch_number": "B3", "quantity": 50, "expiry_date": b3_exp})
        self.app.post(f'/api/medicines/{self.med1_id}/batches', json={"batch_number": "B1", "quantity": 10, "expiry_date": b1_exp})
        
        # Total unexpired qty is 30. Total qty is 80.
        with app.app_context():
            med = Medicine.query.get(self.med1_id)
            self.assertEqual(med.quantity, 80)
            
        # Try checking out 25
        with self.app.session_transaction() as sess:
            sess['cart'] = [{"id": self.med1_id, "qty": 25}]
            
        res = self.app.post('/api/checkout')
        self.assertEqual(res.status_code, 200)
        
        with app.app_context():
            med = Medicine.query.get(self.med1_id)
            self.assertEqual(med.quantity, 55) # 80 - 25 = 55
            
            b1 = MedicineBatch.query.filter_by(batch_number="B1").first()
            b2 = MedicineBatch.query.filter_by(batch_number="B2").first()
            b3 = MedicineBatch.query.filter_by(batch_number="B3").first()
            
            # FEFO logic: B1 (10) consumed, B2 (20) consumed 15, B3 (expired) untouched.
            self.assertEqual(b1.quantity, 0)
            self.assertEqual(b2.quantity, 5)
            self.assertEqual(b3.quantity, 50)
            
            # Check activity log for consumption details
            act = Activity.query.filter_by(action="Sale Completed").first()
            self.assertIn("Batch B1 -> 10", act.detail)
            self.assertIn("Batch B2 -> 15", act.detail)
            self.assertNotIn("Batch B3", act.detail)

    def test_legacy_checkout(self):
        self.login()
        # med2 has no batches. Qty is 50.
        with self.app.session_transaction() as sess:
            sess['cart'] = [{"id": self.med2_id, "qty": 10}]
            
        res = self.app.post('/api/checkout')
        self.assertEqual(res.status_code, 200)
        
        with app.app_context():
            med = Medicine.query.get(self.med2_id)
            self.assertEqual(med.quantity, 40)
            
            act = Activity.query.filter_by(action="Sale Completed").first()
            self.assertIn("Legacy inventory without batch tracking", act.detail)

    def test_expired_only_checkout_fails(self):
        self.login()
        # Create an expired batch
        b3_exp = (date.today() - timedelta(days=5)).isoformat()
        self.app.post(f'/api/medicines/{self.med1_id}/batches', json={"batch_number": "B3", "quantity": 50, "expiry_date": b3_exp})
        
        with self.app.session_transaction() as sess:
            sess['cart'] = [{"id": self.med1_id, "qty": 10}]
            
        res = self.app.post('/api/checkout')
        self.assertEqual(res.status_code, 400)
        self.assertIn(b"all batches are expired", res.data)

if __name__ == '__main__':
    unittest.main()
