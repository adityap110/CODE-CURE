import re
from sqlalchemy import or_

def parse_batch_qr(payload):
    """
    Parses a batch QR payload.
    Expected format: BATCH:Medicine Name|BatchNumber|ExpiryDate
    Returns dict or None if invalid.
    """
    if not payload.startswith("BATCH:"):
        return None
        
    data = payload[6:] # Strip "BATCH:"
    parts = data.split("|")
    if len(parts) >= 3:
        return {
            "name": parts[0].strip(),
            "batch_number": parts[1].strip(),
            "expiry_date": parts[2].strip()
        }
    return None

def lookup_medicine(app_context_db, MedicineModel, barcode):
    """
    Looks up a medicine given a generic barcode string.
    If the string is numeric, we see if it exactly matches a Medicine ID.
    Otherwise we do an exact or ilike search on the Medicine Name.
    """
    barcode = barcode.strip()
    if not barcode:
        return []
        
    query_conditions = []
    
    # If numeric, maybe it's an exact ID lookup (temporary infrastructure trick)
    if barcode.isdigit():
        query_conditions.append(MedicineModel.id == int(barcode))
        
    # Also search by name (exact or ilike)
    query_conditions.append(MedicineModel.name.ilike(f"%{barcode}%"))
    
    matches = MedicineModel.query.filter(or_(*query_conditions)).all()
    return matches

def resolve_scan(app_context_db, MedicineModel, barcode):
    """
    Resolves the scanned string into a structured response for the UI.
    """
    if barcode.startswith("BATCH:"):
        batch_data = parse_batch_qr(barcode)
        if not batch_data:
            return {"error": "Invalid batch QR format"}
            
        # Try to find the associated medicine by exact name
        med = MedicineModel.query.filter(MedicineModel.name.ilike(batch_data["name"])).first()
        if med:
            return {
                "type": "batch",
                "batch_data": batch_data,
                "medicine": {
                    "id": med.id,
                    "name": med.name,
                    "quantity": med.quantity,
                    "price": med.price
                }
            }
        else:
            return {"error": f"Medicine '{batch_data['name']}' not found in database for this batch."}
            
    # Regular barcode
    matches = lookup_medicine(app_context_db, MedicineModel, barcode)
    
    if not matches:
        return {"error": "Barcode not recognized"}
        
    if len(matches) == 1:
        m = matches[0]
        return {
            "type": "medicine",
            "medicine": {
                "id": m.id,
                "name": m.name,
                "quantity": m.quantity,
                "price": m.price,
                "category": m.category
            }
        }
        
    # Multiple matches
    result_matches = []
    for m in matches:
        result_matches.append({
            "id": m.id,
            "name": m.name,
            "quantity": m.quantity,
            "price": m.price,
            "category": m.category
        })
        
    return {
        "type": "multiple_matches",
        "matches": result_matches
    }
