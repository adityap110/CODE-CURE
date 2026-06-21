from app import app
from models_sqlalchemy import db, User
from werkzeug.security import generate_password_hash

def fix_users():
    app.app_context().push()
    
    # Enable Admin and set password to 1234
    admin = User.query.filter_by(username="admin").first()
    if not admin:
        admin = User(username="admin", role="Admin")
        db.session.add(admin)
    admin.password_hash = generate_password_hash("1234")
    admin.is_active = True
    
    # Create missing demo users
    demo_users = [
        {"username": "pharmacist", "role": "Pharmacist"},
        {"username": "cashier", "role": "Cashier"},
        {"username": "doctor", "role": "Doctor"},
    ]
    
    for du in demo_users:
        u = User.query.filter_by(username=du["username"]).first()
        if not u:
            u = User(username=du["username"], role=du["role"])
            db.session.add(u)
        u.password_hash = generate_password_hash("1234")
        u.is_active = True
        
    db.session.commit()
    print("All demo users restored with password 1234 and set to active.")

if __name__ == "__main__":
    fix_users()
