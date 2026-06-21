import json
from app import app
from models_sqlalchemy import db, Medicine, Activity, Sale

app.testing = True

def run_tests():
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user'] = 'cashier'
            sess['role'] = 'Cashier'
            sess['cart'] = []
            
        print('\n--- 1. Single Item Checkout ---')
        with app.app_context():
            med1 = Medicine(name='CheckMed1', quantity=100, price=10)
            db.session.add(med1)
            db.session.commit()
            mid1 = str(med1.id)
            
        with client.session_transaction() as sess:
            sess['cart'] = [{'id': mid1, 'qty': 2}]
            
        res1 = client.post('/api/checkout')
        print(f'Status: {res1.status_code}')
        data1 = res1.get_json()
        print(f'Success: {data1.get("success")}, Total: {data1.get("total")}')
        
        with app.app_context():
            med = Medicine.query.get(mid1)
            print(f'Inventory After: {med.quantity} (Expected 98)')
            sale = Sale.query.filter_by(invoice_id=data1['invoice']).first()
            print(f'Sale Recorded: {sale is not None}')
            act = Activity.query.filter_by(action='Sale Completed').order_by(Activity.id.desc()).first()
            print(f'Activity Logged: {act is not None}')
            
        print('\n--- 2. Multi-Item Checkout ---')
        with app.app_context():
            med2 = Medicine(name='CheckMed2', quantity=50, price=5)
            db.session.add(med2)
            db.session.commit()
            mid2 = str(med2.id)
            
        with client.session_transaction() as sess:
            sess['cart'] = [{'id': mid1, 'qty': 3}, {'id': mid2, 'qty': 10}]
            
        res2 = client.post('/api/checkout')
        print(f'Status: {res2.status_code}')
        data2 = res2.get_json()
        print(f'Total: {data2.get("total")} (Expected: 3*10 + 10*5 = 80)')
        
        with app.app_context():
            m1 = Medicine.query.get(mid1)
            m2 = Medicine.query.get(mid2)
            print(f'Inv Med1: {m1.quantity} (Expected 95), Inv Med2: {m2.quantity} (Expected 40)')

        print('\n--- 3. Insufficient Stock (Rollback Test) ---')
        with client.session_transaction() as sess:
            sess['cart'] = [{'id': mid1, 'qty': 1}, {'id': mid2, 'qty': 100}]
            
        res3 = client.post('/api/checkout')
        print(f'Status: {res3.status_code} (Expected 400)')
        print(f'Response: {res3.get_json()}')
        
        with app.app_context():
            m1 = Medicine.query.get(mid1)
            m2 = Medicine.query.get(mid2)
            print(f'Inv Med1: {m1.quantity} (Expected 95 - NO CHANGE)')
            print(f'Inv Med2: {m2.quantity} (Expected 40 - NO CHANGE)')
            
        print('\n--- 4. Invalid Medicine Scenario ---')
        with client.session_transaction() as sess:
            sess['cart'] = [{'id': '99999', 'qty': 1}]
            
        res4 = client.post('/api/checkout')
        print(f'Status: {res4.status_code} (Expected 400)')
        print(f'Response: {res4.get_json()}')

if __name__ == '__main__':
    run_tests()
