from app import app
from models_sqlalchemy import db, Sale
import json
import os

def test():
    app.testing = True
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['role'] = 'Admin'
            
        with app.app_context():
            sale = Sale.query.first()
            if not sale:
                sale = Sale(
                    invoice_id="INV-TEST-001",
                    customer_name="Test Customer",
                    total_amount=100.0,
                    sold_by="admin",
                    items_json=json.dumps([{"name": "Paracetamol", "qty": 10, "price": 10.0}])
                )
                db.session.add(sale)
                db.session.commit()
            
            invoice_id = sale.invoice_id
            
        # Test A4 PDF
        res = client.get(f'/api/invoice/{invoice_id}/pdf?format=a4')
        if res.status_code == 200 and res.headers.get('Content-Type') == 'application/pdf':
            print(f"A4 PDF generated successfully. Bytes: {len(res.data)}")
            with open('test_a4.pdf', 'wb') as f:
                f.write(res.data)
        else:
            print(f"A4 PDF failed: {res.status_code}")
            
        # Test Thermal PDF
        res = client.get(f'/api/invoice/{invoice_id}/pdf?format=thermal')
        if res.status_code == 200 and res.headers.get('Content-Type') == 'application/pdf':
            print(f"Thermal PDF generated successfully. Bytes: {len(res.data)}")
            with open('test_thermal.pdf', 'wb') as f:
                f.write(res.data)
        else:
            print(f"Thermal PDF failed: {res.status_code}")

if __name__ == '__main__':
    test()
