import unittest
from app import app, db
from models_sqlalchemy import Medicine, MedicineBatch
import barcode_service

class BarcodeScannerTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        db.create_all()
        
        # Seed test data
        m1 = Medicine(name="Paracetamol 500mg", category="Painkiller", quantity=100, price=10.0, min_stock=20)
        m2 = Medicine(name="Ibuprofen 400mg", category="Painkiller", quantity=50, price=15.0, min_stock=10)
        m3 = Medicine(name="Paracetamol Syrup", category="Painkiller", quantity=30, price=25.0, min_stock=10)
        
        db.session.add_all([m1, m2, m3])
        db.session.commit()
        
        self.m1_id = m1.id
        self.m2_id = m2.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_parse_batch_qr(self):
        # Valid payload
        payload = "BATCH:Paracetamol 500mg|B001|2026-10-01"
        res = barcode_service.parse_batch_qr(payload)
        self.assertIsNotNone(res)
        self.assertEqual(res['name'], "Paracetamol 500mg")
        self.assertEqual(res['batch_number'], "B001")
        self.assertEqual(res['expiry_date'], "2026-10-01")

        # Invalid prefix
        invalid = "QR:Paracetamol|B001"
        self.assertIsNone(barcode_service.parse_batch_qr(invalid))

    def test_lookup_medicine_exact_id(self):
        # Numeric string matches ID
        matches = barcode_service.lookup_medicine(db, Medicine, str(self.m1_id))
        self.assertTrue(len(matches) >= 1)
        # Should contain the medicine with id m1_id
        self.assertTrue(any(m.id == self.m1_id for m in matches))

    def test_lookup_medicine_name_partial(self):
        # Searching for "Paracetamol" should yield 2 results (500mg and Syrup)
        matches = barcode_service.lookup_medicine(db, Medicine, "Paracetamol")
        self.assertEqual(len(matches), 2)

    def test_lookup_medicine_not_found(self):
        matches = barcode_service.lookup_medicine(db, Medicine, "Nonexistent")
        self.assertEqual(len(matches), 0)

    def test_resolve_scan_batch_success(self):
        payload = "BATCH:Paracetamol 500mg|B001|2026-10-01"
        res = barcode_service.resolve_scan(db, Medicine, payload)
        self.assertIn('type', res)
        self.assertEqual(res['type'], 'batch')
        self.assertEqual(res['medicine']['name'], "Paracetamol 500mg")
        self.assertEqual(res['batch_data']['batch_number'], "B001")

    def test_resolve_scan_batch_not_found(self):
        payload = "BATCH:Unknown Med|B001|2026-10-01"
        res = barcode_service.resolve_scan(db, Medicine, payload)
        self.assertIn('error', res)
        self.assertIn('not found', res['error'])

    def test_resolve_scan_single_medicine(self):
        res = barcode_service.resolve_scan(db, Medicine, "Ibuprofen")
        self.assertEqual(res.get('type'), 'medicine')
        self.assertEqual(res['medicine']['name'], "Ibuprofen 400mg")

    def test_resolve_scan_multiple_matches(self):
        res = barcode_service.resolve_scan(db, Medicine, "Paracetamol")
        self.assertEqual(res.get('type'), 'multiple_matches')
        self.assertEqual(len(res['matches']), 2)

    def test_resolve_scan_unrecognized(self):
        res = barcode_service.resolve_scan(db, Medicine, "123XYZ")
        self.assertIn('error', res)
        self.assertEqual(res['error'], "Barcode not recognized")

if __name__ == '__main__':
    unittest.main()
