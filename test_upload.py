import os
import unittest
from app import app, db
from models_sqlalchemy import User

class UploadTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app_context = app.app_context()
        self.app_context.push()
        db.create_all()
        admin = User(username="admin", password_hash="hash", role="Admin", is_active=True)
        db.session.add(admin)
        db.session.commit()
        
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_upload_limits(self):
        with self.client.session_transaction() as sess:
            sess["user"] = "admin"
            sess["role"] = "Admin"

        # 1MB file
        data_1mb = b"0" * (1 * 1024 * 1024)
        resp = self.client.post('/api/scan-prescription', data={
            'file': (data_1mb, '1mb.jpg')
        })
        self.assertNotEqual(resp.status_code, 413)

        # 4MB file
        data_4mb = b"0" * (4 * 1024 * 1024)
        resp = self.client.post('/api/scan-prescription', data={
            'file': (data_4mb, '4mb.jpg')
        })
        self.assertNotEqual(resp.status_code, 413)

        # 6MB file
        data_6mb = b"0" * (6 * 1024 * 1024)
        resp = self.client.post('/api/scan-prescription', data={
            'file': (data_6mb, '6mb.jpg')
        })
        self.assertEqual(resp.status_code, 413)
        self.assertIn(b"File exceeds the 5MB size limit", resp.data)

if __name__ == '__main__':
    unittest.main()
