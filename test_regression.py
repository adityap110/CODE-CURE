import json
from app import app
from models_sqlalchemy import db, Medicine, Activity, Sale

app.testing = True

def run_tests():
    errors = []
    routes_covered = []

    def check(name, res, expected_status=200):
        routes_covered.append(name)
        if res.status_code != expected_status:
            errors.append(f"{name} FAILED: expected {expected_status}, got {res.status_code}. Content: {res.get_data(as_text=True)[:200]}")
        else:
            print(f"{name} PASSED")

    with app.test_client() as client:
        # 1. Auth Setup
        with client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['role'] = 'Admin'

        # Inventory Routes
        print("Testing Inventory Routes...")
        res = client.get('/api/medicines')
        check('GET /api/medicines', res)

        # Create Medicine
        res = client.post('/api/medicines', json={'name': 'RegTestMed', 'quantity': 10, 'min_stock': 5})
        check('POST /api/medicines', res)

        # Get mid
        with app.app_context():
            med = Medicine.query.filter_by(name='RegTestMed').first()
            mid = str(med.id) if med else "1"

        # Edit
        res = client.put(f'/api/medicines/{mid}', json={'name': 'RegTestMed', 'quantity': 20, 'min_stock': 5})
        check('PUT /api/medicines/<mid>', res)

        # Restock
        res = client.post(f'/api/medicines/{mid}/restock', json={'quantity': 50})
        check('POST /api/medicines/<mid>/restock', res)

        # Discard
        res = client.post(f'/api/medicines/{mid}/discard')
        check('POST /api/medicines/<mid>/discard', res)

        # Delete
        res = client.delete(f'/api/medicines/{mid}')
        check('DELETE /api/medicines/<mid>', res)

        # Sales/Cart Routes
        print("Testing Sales Routes...")
        res = client.get('/api/cart')
        check('GET /api/cart', res)

        with app.app_context():
            med2 = Medicine(name='RegCartMed', quantity=100, price=10)
            db.session.add(med2)
            db.session.commit()
            mid2 = str(med2.id)

        res = client.post('/api/cart', json={'id': mid2, 'qty': 2})
        check('POST /api/cart (add)', res)

        res = client.delete(f'/api/cart/{mid2}')
        check('DELETE /api/cart/<mid>', res)

        res = client.post('/api/cart', json={'id': mid2, 'qty': 2})
        res = client.post('/api/cart/clear')
        check('POST /api/cart/clear', res)

        # Checkout
        res = client.post('/api/cart', json={'id': mid2, 'qty': 1})
        res = client.post('/api/checkout')
        check('POST /api/checkout', res)

        # Analytics
        print("Testing Analytics Routes...")
        res = client.get('/api/stock-valuation')
        check('GET /api/stock-valuation', res)

        res = client.get('/api/chart/category')
        check('GET /api/chart/category', res)

        res = client.get('/api/analytics/sales')
        check('GET /api/analytics/sales', res)

        res = client.get('/api/analytics/top-medicines')
        check('GET /api/analytics/top-medicines', res)

        # Reporting
        print("Testing Reporting Routes...")
        res = client.get('/api/export/csv')
        check('GET /api/export/csv', res)

        res = client.get('/api/export/alerts/csv')
        check('GET /api/export/alerts/csv', res)

        # Admin
        print("Testing Admin Routes...")
        res = client.get('/api/activity')
        check('GET /api/activity', res)

        res = client.get('/api/alerts')
        check('GET /api/alerts', res)

        res = client.get('/api/search?q=a')
        check('GET /api/search', res)

        # Clean up
        with app.app_context():
            Medicine.query.filter_by(name='RegCartMed').delete()
            db.session.commit()

    print("\n=== SUMMARY ===")
    print(f"Total Routes Covered: {len(routes_covered)}")
    if not errors:
        print("All routes PASSED without errors.")
    else:
        print(f"Encountered {len(errors)} errors:")
        for e in errors:
            print("  - " + e)

if __name__ == '__main__':
    run_tests()
