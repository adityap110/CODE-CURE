import os
import unittest
from app import app, db
from models_sqlalchemy import User, Medicine

class CartTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app_context = app.app_context()
        self.app_context.push()
        db.create_all()
        admin = User(username="admin", password_hash="hash", role="Admin", is_active=True)
        med = Medicine(name="Test Med", category="Test", quantity=5, price=10)
        db.session.add(admin)
        db.session.add(med)
        db.session.commit()
        
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_cart_auto_increment(self):
        with self.client.session_transaction() as sess:
            sess["user"] = "admin"
            sess["role"] = "Admin"

        # First scan (add to cart)
        resp = self.client.post('/api/cart', json={"id": 1, "qty": 1})
        self.assertTrue(resp.json['success'])
        self.assertEqual(resp.json['cart_count'], 1)

        # Second scan (should increment, not add duplicate)
        resp2 = self.client.post('/api/cart', json={"id": "1", "qty": 1})
        self.assertTrue(resp2.json['success'])
        self.assertEqual(resp2.json['cart_count'], 1) # Should still be 1 row

        # Check cart state
        with self.client.session_transaction() as sess:
            cart = sess["cart"]
            self.assertEqual(len(cart), 1)
            self.assertEqual(cart[0]["qty"], 2)

if __name__ == '__main__':
    unittest.main()
