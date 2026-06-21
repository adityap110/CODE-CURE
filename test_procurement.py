import unittest
import json
from datetime import datetime, timedelta
from app import app, db
from models_sqlalchemy import Medicine, Supplier, PurchaseOrder, PurchaseOrderItem, MedicineBatch
import po_service

class ProcurementTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        db.create_all()
        
        self.med = Medicine(name="Aspirin", quantity=10, min_stock=50, price=5.0)
        self.sup = Supplier(supplier_name="Global Pharma", contact_person="John", phone="12345", email="j@gp.com")
        db.session.add(self.med)
        db.session.add(self.sup)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_po_generation_and_receiving(self):
        # 1. Generate PO from Intelligence
        items = [{"medicine_id": self.med.id, "reorder_qty": 100}]
        po = po_service.generate_draft_from_intelligence(db, PurchaseOrder, PurchaseOrderItem, self.sup.id, items, "Admin")
        
        self.assertEqual(po.status, "Draft")
        self.assertEqual(po.po_number.startswith("PO-"), True)
        
        # 2. State transition
        self.assertTrue(po_service.validate_transition("Draft", "Pending"))
        self.assertTrue(po_service.validate_transition("Pending", "Approved"))
        self.assertTrue(po_service.validate_transition("Approved", "Ordered"))
        
        po.status = "Ordered"
        db.session.commit()
        
        poi = PurchaseOrderItem.query.filter_by(po_id=po.id).first()
        self.assertEqual(poi.requested_qty, 100)
        self.assertEqual(poi.received_qty, 0)
        
        # 3. Receive Partial
        po_service.receive_po_item(db, app, PurchaseOrder, PurchaseOrderItem, MedicineBatch, po.id, poi.id, 40, "BATCH001", "2026-01-01", "2028-01-01")
        self.assertEqual(poi.received_qty, 40)
        self.assertEqual(po.status, "Partially Received")
        
        # Verify batch was created and global inventory updated
        batch = MedicineBatch.query.filter_by(batch_number="BATCH001").first()
        self.assertIsNotNone(batch)
        self.assertEqual(batch.quantity, 40)
        
        med = Medicine.query.get(self.med.id)
        self.assertEqual(med.quantity, 40) # Since the original 10 wasn't in a batch, sync_medicine_quantity will reset to sum of batches (which is 40). Note: sync ignores base quantity, respects batches only.
        
        # 4. Receive remainder
        po_service.receive_po_item(db, app, PurchaseOrder, PurchaseOrderItem, MedicineBatch, po.id, poi.id, 60, "BATCH002", "2026-01-01", "2028-01-01")
        self.assertEqual(poi.received_qty, 100)
        self.assertEqual(po.status, "Received")
        
        med = Medicine.query.get(self.med.id)
        self.assertEqual(med.quantity, 100)
        
        # 5. Over-receive protection
        with self.assertRaises(ValueError):
            po_service.receive_po_item(db, app, PurchaseOrder, PurchaseOrderItem, MedicineBatch, po.id, poi.id, 10, "BATCH003", "2026-01-01", "2028-01-01")

if __name__ == '__main__':
    unittest.main()
