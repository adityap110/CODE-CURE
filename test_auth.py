import json
from app import app
from models_sqlalchemy import db, User

app.testing = True

def run_tests():
    with app.app_context():
        # Clean DB for fresh test
        User.query.delete()
        db.session.commit()

    with app.test_client() as client:
        print("\n--- 1. Testing Default Admin Creation ---")
        # Hit the login page to trigger creation
        res1 = client.get('/')
        print(f"Status GET /: {res1.status_code}")
        
        with app.app_context():
            admin = User.query.filter_by(username='admin').first()
            print(f"Admin auto-created: {admin is not None}")
            if admin:
                print(f"Admin Role: {admin.role}, Active: {admin.is_active}")

        print("\n--- 2. Testing Valid Login ---")
        res2 = client.post('/', data={'username': 'admin', 'password': '1234'}, follow_redirects=False)
        print(f"Status POST /: {res2.status_code} (Expected 302 Redirect to /admin)")
        with client.session_transaction() as sess:
            print(f"Session User: {sess.get('user')} (Expected 'admin')")
            print(f"Session Role: {sess.get('role')} (Expected 'Admin')")

        print("\n--- 3. Testing Invalid Credentials ---")
        res3 = client.post('/', data={'username': 'admin', 'password': 'wrongpassword'})
        print(f"Status POST / (invalid pass): {res3.status_code} (Expected 200)")
        html = res3.get_data(as_text=True)
        print(f"Error shown: {'Invalid credentials' in html}")

        print("\n--- 4. Testing Disabled Account ---")
        with app.app_context():
            admin = User.query.filter_by(username='admin').first()
            admin.is_active = False
            db.session.commit()
            
        res4 = client.post('/', data={'username': 'admin', 'password': '1234'})
        print(f"Status POST / (disabled acc): {res4.status_code}")
        html4 = res4.get_data(as_text=True)
        print(f"Error shown: {'Account disabled' in html4}")
        
if __name__ == '__main__':
    run_tests()
