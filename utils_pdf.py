import io
import json
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm

def generate_a4_invoice(sale, config):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, spaceAfter=10, textColor=colors.HexColor("#0D9488"))
    subtitle_style = ParagraphStyle('SubtitleStyle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor("#64748B"))
    info_style = ParagraphStyle('InfoStyle', parent=styles['Normal'], fontSize=10, spaceAfter=2)
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Heading2'], fontSize=12, spaceAfter=10)
    
    # Header Section
    elements.append(Paragraph(config.get('PHARMACY_NAME', 'CodeCure Pharmacy'), title_style))
    elements.append(Paragraph(config.get('PHARMACY_ADDRESS', ''), subtitle_style))
    elements.append(Paragraph(f"Phone: {config.get('PHARMACY_PHONE', '')}", subtitle_style))
    gst = config.get('PHARMACY_GST', '')
    if gst:
        elements.append(Paragraph(f"GST: {gst}", subtitle_style))
    
    elements.append(Spacer(1, 15*mm))
    
    # Invoice Information
    elements.append(Paragraph("TAX INVOICE", header_style))
    
    # Parse items
    try:
        items = json.loads(sale.items_json)
    except:
        items = []
        
    cust_name = sale.customer_name if sale.customer_name else "Walk-in Customer"
    
    info_data = [
        ["Invoice Number:", sale.invoice_id, "Date:", sale.timestamp[:10]],
        ["Customer Name:", cust_name, "Time:", sale.timestamp[11:16]],
        ["Cashier:", sale.sold_by, "Status:", getattr(sale, 'status', 'Paid')]
    ]
    info_table = Table(info_data, colWidths=[35*mm, 50*mm, 35*mm, 50*mm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.darkslategray),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10*mm))
    
    # Item Table
    table_data = [["#", "Description", "Qty", "Unit Price", "Total"]]
    for idx, item in enumerate(items):
        name = item.get("name", "Unknown")
        qty = item.get("qty", 1)
        price = item.get("price", 0.0)
        subtotal = item.get("subtotal", qty * price)
        table_data.append([str(idx+1), name, str(qty), f"Rs. {price:.2f}", f"Rs. {subtotal:.2f}"])
        
    table_data.append(["", "", "", "Discount", f"Rs. {sale.discount:.2f}"])
    table_data.append(["", "", "", "Grand Total", f"Rs. {sale.total_amount:.2f}"])
    
    item_table = Table(table_data, colWidths=[10*mm, 70*mm, 20*mm, 35*mm, 35*mm])
    item_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#334155")),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('ALIGN', (2,1), (-1,-1), 'RIGHT'),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('GRID', (0,0), (-1,-3), 0.5, colors.HexColor("#E2E8F0")),
        ('LINEABOVE', (3,-2), (-1,-1), 1, colors.HexColor("#94A3B8")),
        ('FONTNAME', (3,-1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (3,-1), (-1,-1), 12),
    ]))
    
    elements.append(item_table)
    elements.append(Spacer(1, 20*mm))
    
    # Footer
    elements.append(Paragraph("Thank you for your business!", ParagraphStyle('Footer', parent=styles['Normal'], alignment=1, textColor=colors.gray)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_thermal_invoice(sale, config):
    buffer = io.BytesIO()
    
    # Typical thermal receipt width: 80mm
    width = 80*mm
    # Height will be dynamic, but platypus can handle long pages if we set a large height
    height = 300*mm 
    doc = SimpleDocTemplate(buffer, pagesize=(width, height), rightMargin=5*mm, leftMargin=5*mm, topMargin=5*mm, bottomMargin=5*mm)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom Styles for Thermal
    center_style = ParagraphStyle('CenterStyle', parent=styles['Normal'], alignment=1, fontSize=9)
    bold_center = ParagraphStyle('BoldCenter', parent=styles['Normal'], alignment=1, fontSize=11, fontName='Helvetica-Bold')
    left_style = ParagraphStyle('LeftStyle', parent=styles['Normal'], fontSize=8)
    
    elements.append(Paragraph(config.get('PHARMACY_NAME', 'CodeCure Pharmacy'), bold_center))
    elements.append(Paragraph(config.get('PHARMACY_ADDRESS', ''), center_style))
    elements.append(Paragraph(f"Ph: {config.get('PHARMACY_PHONE', '')}", center_style))
    gst = config.get('PHARMACY_GST', '')
    if gst:
        elements.append(Paragraph(f"GST: {gst}", center_style))
        
    elements.append(Spacer(1, 4*mm))
    elements.append(Paragraph("-" * 35, center_style))
    
    cust_name = sale.customer_name if sale.customer_name else "Walk-in"
    
    elements.append(Paragraph(f"Inv: {sale.invoice_id}", left_style))
    elements.append(Paragraph(f"Date: {sale.timestamp[:10]} {sale.timestamp[11:16]}", left_style))
    elements.append(Paragraph(f"Cust: {cust_name}", left_style))
    elements.append(Paragraph(f"Cashier: {sale.sold_by}", left_style))
    elements.append(Paragraph(f"Status: {getattr(sale, 'status', 'Paid')}", left_style))
    
    elements.append(Paragraph("-" * 35, center_style))
    
    try:
        items = json.loads(sale.items_json)
    except:
        items = []
        
    # Item Table (Item | Qty | Total)
    table_data = []
    for item in items:
        name = item.get("name", "Unknown")
        qty = item.get("qty", 1)
        subtotal = item.get("subtotal", 0.0)
        table_data.append([Paragraph(name, left_style), str(qty), f"{subtotal:.2f}"])
        
    item_table = Table(table_data, colWidths=[40*mm, 10*mm, 20*mm])
    item_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 2),
    ]))
    
    elements.append(item_table)
    elements.append(Paragraph("-" * 35, center_style))
    
    elements.append(Paragraph(f"Total: Rs. {sale.total_amount:.2f}", ParagraphStyle('Total', parent=styles['Normal'], alignment=2, fontName='Helvetica-Bold', fontSize=10)))
    if sale.discount > 0:
        elements.append(Paragraph(f"Discount: Rs. {sale.discount:.2f}", ParagraphStyle('Disc', parent=styles['Normal'], alignment=2, fontSize=8)))
        
    elements.append(Spacer(1, 6*mm))
    elements.append(Paragraph("*** THANK YOU ***", center_style))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer
