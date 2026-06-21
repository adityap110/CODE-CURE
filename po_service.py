import json
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import io
import uuid

def generate_po_number(PurchaseOrder):
    today = datetime.utcnow().strftime("%Y%m%d")
    count = PurchaseOrder.query.filter(PurchaseOrder.po_number.like(f"PO-{today}-%")).count()
    return f"PO-{today}-{count+1:04d}"

def get_po_status_hierarchy():
    return ["Draft", "Pending", "Approved", "Ordered", "Partially Received", "Received", "Cancelled"]

def validate_transition(current, target):
    hierarchy = get_po_status_hierarchy()
    if target == "Cancelled":
        return True
    
    try:
        curr_idx = hierarchy.index(current)
        target_idx = hierarchy.index(target)
    except ValueError:
        return False
        
    # Strictly sequential
    if target_idx == curr_idx + 1:
        return True
    # Can also transition Partially Received -> Partially Received (e.g., another partial delivery)
    if current == "Partially Received" and target == "Partially Received":
        return True
        
    return False

def generate_draft_from_intelligence(db, PurchaseOrder, PurchaseOrderItem, supplier_id, reorder_items, created_by):
    """
    reorder_items: list of dicts { "medicine_id": 1, "reorder_qty": 50 }
    """
    po_number = generate_po_number(PurchaseOrder)
    po = PurchaseOrder(
        po_number=po_number,
        supplier_id=supplier_id,
        created_by=created_by,
        status="Draft",
        notes="Generated from Inventory Intelligence AI"
    )
    db.session.add(po)
    db.session.flush() # get po.id
    
    for item in reorder_items:
        poi = PurchaseOrderItem(
            po_id=po.id,
            medicine_id=item['medicine_id'],
            requested_qty=item['reorder_qty'],
            expected_unit_cost=0.0, # to be updated by admin later or fetched from med
            line_total=0.0
        )
        db.session.add(poi)
    
    db.session.commit()
    return po

def receive_po_item(db, app, PurchaseOrder, PurchaseOrderItem, MedicineBatch, po_id, item_id, received_qty, batch_number, mfg_date, exp_date):
    """
    Processes the receipt of goods.
    Enforces partial receipt protection.
    """
    po = PurchaseOrder.query.get(po_id)
    if not po:
        raise ValueError("Purchase Order not found")
        
    if po.status not in ["Ordered", "Partially Received"]:
        raise ValueError(f"Cannot receive items for PO in status: {po.status}")
        
    poi = PurchaseOrderItem.query.get(item_id)
    if not poi or poi.po_id != po.id:
        raise ValueError("Purchase Order Item not found")
        
    if received_qty <= 0:
        raise ValueError("Received quantity must be positive")
        
    remaining = poi.requested_qty - poi.received_qty
    if received_qty > remaining:
        raise ValueError(f"Cannot over-receive. Max allowed: {remaining}, attempted: {received_qty}")
        
    poi.received_qty += received_qty
    
    # Create batch
    batch = MedicineBatch(
        medicine_id=poi.medicine_id,
        batch_number=batch_number,
        manufacturing_date=mfg_date,
        expiry_date=exp_date,
        quantity=received_qty
    )
    db.session.add(batch)
    db.session.flush()
    
    # Update global quantity using app's sync
    # We must import sync_medicine_quantity dynamically to avoid circular imports if app.py imports this
    from app import sync_medicine_quantity
    
    # Check overall PO status
    all_items = PurchaseOrderItem.query.filter_by(po_id=po.id).all()
    all_received = True
    for item in all_items:
        if item.received_qty < item.requested_qty:
            all_received = False
            break
            
    if all_received:
        po.status = "Received"
    else:
        po.status = "Partially Received"
        
    db.session.commit()
    
    # Run sync safely
    sync_medicine_quantity(poi.medicine_id)
    
    return po

def generate_po_pdf(po, supplier, items, medicine_map):
    output = io.BytesIO()
    c = canvas.Canvas(output, pagesize=A4)
    width, height = A4
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "PURCHASE ORDER")
    
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 70, f"PO Number: {po.po_number}")
    c.drawString(50, height - 85, f"Date: {po.created_at[:10]}")
    c.drawString(50, height - 100, f"Status: {po.status}")
    c.drawString(50, height - 115, f"Created By: {po.created_by}")
    
    if po.expected_delivery_date:
        c.drawString(50, height - 130, f"Expected Delivery: {po.expected_delivery_date}")
        
    # Supplier Info
    c.setFont("Helvetica-Bold", 12)
    c.drawString(350, height - 50, "SUPPLIER")
    c.setFont("Helvetica", 10)
    c.drawString(350, height - 70, supplier.supplier_name)
    if getattr(supplier, 'contact_person', None):
        c.drawString(350, height - 85, f"Attn: {supplier.contact_person}")
    c.drawString(350, height - 100, f"Phone: {supplier.phone or 'N/A'}")
    c.drawString(350, height - 115, f"Email: {supplier.email or 'N/A'}")
    
    # Table Header
    y = height - 180
    c.setFont("Helvetica-Bold", 10)
    c.setFillColorRGB(0.9, 0.9, 0.9)
    c.rect(50, y-5, 500, 20, fill=1)
    c.setFillColorRGB(0, 0, 0)
    
    c.drawString(60, y, "Item Description")
    c.drawString(300, y, "Requested Qty")
    c.drawString(400, y, "Unit Cost")
    c.drawString(480, y, "Total")
    
    y -= 20
    c.setFont("Helvetica", 10)
    
    grand_total = 0.0
    for item in items:
        med_name = medicine_map.get(item.medicine_id, "Unknown Medicine")
        c.drawString(60, y, med_name[:35])
        c.drawString(300, y, str(item.requested_qty))
        c.drawString(400, y, f"${item.expected_unit_cost:.2f}")
        c.drawString(480, y, f"${item.line_total:.2f}")
        grand_total += item.line_total
        y -= 20
        if y < 100:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 10)
            
    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(380, y, "Grand Total:")
    c.drawString(480, y, f"${grand_total:.2f}")
    
    if po.notes:
        y -= 40
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y, "Notes / Terms:")
        y -= 15
        c.setFont("Helvetica", 10)
        c.drawString(50, y, po.notes[:80])
        
    c.save()
    output.seek(0)
    return output
