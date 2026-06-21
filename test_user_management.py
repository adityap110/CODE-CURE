import unittest
from app import app, db, User, Activity

class TestUserManagement(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app.test_client()
        with app.app_context():
            db.create_all()
            # The app auto-creates an admin on first request if empty.
            # We'll just trigger it by making a GET to /
            self.app.get('/')
            
    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_admin_created(self):
        with app.app_context():
            admin = User.query.filter_by(username="admin").first()
            self.assertIsNotNone(admin)
            self.assertEqual(admin.role, "Admin")
            self.assertTrue(admin.is_active)

    def test_create_user(self):
        # We need an admin session to create a user.
        with self.app.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['role'] = 'Admin'

        response = self.app.post('/api/users', json={
            "username": "new_pharmacist",
            "password": "securepassword",
            "role": "Pharmacist"
        })
        self.assertEqual(response.status_code, 200)
        
        with app.app_context():
            user = User.query.filter_by(username="new_pharmacist").first()
            self.assertIsNotNone(user)
            self.assertEqual(user.role, "Pharmacist")
            
            # Check activity
            act = Activity.query.filter_by(action="User Creation").first()
            self.assertIsNotNone(act)

    def test_edit_user(self):
        with self.app.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['role'] = 'Admin'
            
        self.app.post('/api/users', json={"username": "testuser", "password": "pw", "role": "Doctor"})
        
        with app.app_context():
            user = User.query.filter_by(username="testuser").first()
            uid = user.id
            
        response = self.app.put(f'/api/users/{uid}', json={
            "username": "updateduser",
            "role": "Pharmacist"
        })
        self.assertEqual(response.status_code, 200)
        
        with app.app_context():
            user = User.query.get(uid)
            self.assertEqual(user.username, "updateduser")
            self.assertEqual(user.role, "Pharmacist")

    def test_admin_self_protection(self):
        with self.app.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['role'] = 'Admin'
            
        with app.app_context():
            admin = User.query.filter_by(username="admin").first()
            uid = admin.id
            
        # Try to disable self
        response = self.app.put(f'/api/users/{uid}/status', json={"is_active": 0})
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"Admin Self-Protection", response.data)
        
        # Try to change own role
        response = self.app.put(f'/api/users/{uid}', json={"role": "Pharmacist"})
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"Admin Self-Protection", response.data)

    def test_reset_password(self):
        with self.app.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['role'] = 'Admin'
            
        self.app.post('/api/users', json={"username": "testuser", "password": "pw", "role": "Doctor"})
        with app.app_context():
            user = User.query.filter_by(username="testuser").first()
            uid = user.id
            old_hash = user.password_hash
            
        # Reset password
        response = self.app.put(f'/api/users/{uid}/reset_password', json={
            "password": "newpassword123",
            "confirm_password": "newpassword123"
        })
        self.assertEqual(response.status_code, 200)
        
        with app.app_context():
            user = User.query.get(uid)
            self.assertNotEqual(old_hash, user.password_hash)

if __name__ == '__main__':
    unittest.main()
