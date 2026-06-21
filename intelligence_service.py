import json
import logging
from datetime import datetime, timedelta
import google.generativeai as genai
import os

def calculate_intelligence(db_session, Medicine, MedicineBatch, Sale, page=1, page_size=100):
    """
    Core engine for G6 Intelligence calculations.
    Returns a comprehensive dict of intelligence KPIs.
    """
    now = datetime.utcnow()
    day_30 = now - timedelta(days=30)
    day_60 = now - timedelta(days=60)
    day_90 = now - timedelta(days=90)
    
    # 1. Gather historical sales data
    recent_sales = Sale.query.filter(Sale.timestamp >= day_90.isoformat()).all()
    
    med_sales = {} # format: id: {'0_30': 0, '31_60': 0, '61_90': 0, 'days_sold': set()}
    
    for s in recent_sales:
        s_date = datetime.fromisoformat(s.timestamp)
        try:
            items = json.loads(s.items_json or "[]")
        except:
            items = []
        for item in items:
            med_name = item.get("name")
            qty = item.get("qty", 0)
            if med_name not in med_sales:
                med_sales[med_name] = {'0_30': 0, '31_60': 0, '61_90': 0, 'days_sold': set()}
                
            med_sales[med_name]['days_sold'].add(s_date.date())
            
            if s_date >= day_30:
                med_sales[med_name]['0_30'] += qty
            elif s_date >= day_60:
                med_sales[med_name]['31_60'] += qty
            else:
                med_sales[med_name]['61_90'] += qty

    medicines = Medicine.query.yield_per(1000)
    batches = MedicineBatch.query.filter(MedicineBatch.quantity > 0).yield_per(1000)
    
    # Group batches by medicine id
    batch_map = {}
    for b in batches:
        batch_map.setdefault(b.medicine_id, []).append(b)
        
    for k in batch_map:
        batch_map[k].sort(key=lambda x: x.expiry_date if x.expiry_date else "9999-99-99")
        
    results = {
        "runouts": [],
        "reorders": [],
        "slow_moving": [],
        "dead_stock": [],
        "expiry_risks": [],
        "health_score": 100,
        "kpis": {
            "at_risk_count": 0,
            "dead_stock_value": 0.0,
            "est_expiry_loss": 0.0
        }
    }
    
    total_penalty = 0
    today_iso = now.date().isoformat()
    
    for m in medicines:
        stats = med_sales.get(m.name, {'0_30': 0, '31_60': 0, '61_90': 0, 'days_sold': set()})
        
        # Weighted Daily Sales
        daily_0_30 = stats['0_30'] / 30.0
        daily_31_60 = stats['31_60'] / 30.0
        daily_61_90 = stats['61_90'] / 30.0
        
        weighted_daily_sales = (daily_0_30 * 0.60) + (daily_31_60 * 0.25) + (daily_61_90 * 0.15)
        
        # Confidence
        total_qty_sold = stats['0_30'] + stats['31_60'] + stats['61_90']
        days_sold = len(stats['days_sold'])
        
        if days_sold >= 20 and total_qty_sold > 50:
            confidence = "High"
        elif days_sold >= 5:
            confidence = "Medium"
        else:
            confidence = "Low"
            
        current_stock = m.quantity
        price = m.price or 0.0
        
        # Runout Prediction
        days_to_runout = -1
        if weighted_daily_sales > 0:
            days_to_runout = int(current_stock / weighted_daily_sales)
        elif current_stock == 0:
            days_to_runout = 0
            
        if 0 <= days_to_runout <= 30 and weighted_daily_sales > 0:
            results["runouts"].append({
                "id": m.id,
                "name": m.name,
                "current_stock": current_stock,
                "avg_daily_sales": round(weighted_daily_sales, 2),
                "days_to_runout": days_to_runout,
                "confidence": confidence
            })
            results["kpis"]["at_risk_count"] += 1
            total_penalty += (30 - days_to_runout) * 0.5
            
        # Reorder Recommendation
        safety_stock = m.min_stock
        forecast_30_day = weighted_daily_sales * 30
        reorder_qty = int(forecast_30_day + safety_stock - current_stock)
        
        if reorder_qty > 0 and weighted_daily_sales > 0:
            if days_to_runout <= 7:
                priority = "Critical"
            elif days_to_runout <= 14:
                priority = "High"
            elif days_to_runout <= 30:
                priority = "Medium"
            else:
                priority = "Low"
                
            results["reorders"].append({
                "id": m.id,
                "name": m.name,
                "current_stock": current_stock,
                "reorder_qty": reorder_qty,
                "priority": priority,
                "days_remaining": days_to_runout,
                "confidence": confidence
            })
            
        # Slow Moving
        if 0 < weighted_daily_sales < 0.2 and current_stock > 30:
            last_sale = "90+ days ago"
            if len(stats['days_sold']) > 0:
                last_sale = max(stats['days_sold']).isoformat()
                
            results["slow_moving"].append({
                "id": m.id,
                "name": m.name,
                "current_stock": current_stock,
                "last_sale_date": last_sale
            })
            total_penalty += 5
            
        # Dead Stock
        if total_qty_sold == 0 and current_stock > 0:
            value = current_stock * price
            results["dead_stock"].append({
                "id": m.id,
                "name": m.name,
                "current_stock": current_stock,
                "inventory_value": round(value, 2)
            })
            results["kpis"]["dead_stock_value"] += value
            total_penalty += 10
            
        # Expiry Loss Forecasting (FEFO aware)
        med_batches = batch_map.get(m.id, [])
        simulated_stock = current_stock
        cumulative_sold_forecast = 0
        
        for b in med_batches:
            if b.expiry_date:
                try:
                    exp_date = datetime.strptime(b.expiry_date, "%Y-%m-%d")
                    days_to_expiry = (exp_date - now).days
                    if days_to_expiry <= 0:
                        # Already expired
                        loss = b.quantity * price
                        results["expiry_risks"].append({
                            "id": m.id,
                            "name": m.name,
                            "batch": b.batch_number,
                            "expiry_date": b.expiry_date,
                            "units_at_risk": b.quantity,
                            "estimated_loss": round(loss, 2)
                        })
                        results["kpis"]["est_expiry_loss"] += loss
                        total_penalty += 5
                    elif days_to_expiry < 365:
                        # Calculate how much we can sell before expiry
                        can_sell = weighted_daily_sales * days_to_expiry
                        # Adjusted for FEFO: previous batches will be sold first
                        if can_sell < (cumulative_sold_forecast + b.quantity):
                            units_at_risk = int((cumulative_sold_forecast + b.quantity) - can_sell)
                            if units_at_risk > b.quantity:
                                units_at_risk = b.quantity
                            if units_at_risk > 0:
                                loss = units_at_risk * price
                                results["expiry_risks"].append({
                                    "id": m.id,
                                    "name": m.name,
                                    "batch": b.batch_number,
                                    "expiry_date": b.expiry_date,
                                    "units_at_risk": units_at_risk,
                                    "estimated_loss": round(loss, 2)
                                })
                                results["kpis"]["est_expiry_loss"] += loss
                                total_penalty += 5
                except:
                    pass
            cumulative_sold_forecast += b.quantity


    # Paginate lists to preserve memory and network transfer
    for key in ["runouts", "reorders", "slow_moving", "dead_stock", "expiry_risks"]:
        total_records = len(results[key])
        start = (page - 1) * page_size
        end = start + page_size
        sliced_data = results[key][start:end]
        results[key] = {
            "data": sliced_data,
            "page": page,
            "page_size": page_size,
            "total_records": total_records
        }

    # Calculate Health Score

    health = 100 - min(100, int(total_penalty))
    results["health_score"] = health
    
    return results

def generate_ai_advisor_summary(kpi_data):
    """
    Sends condensed KPIs to Gemini to get an Executive Summary.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        return "AI Advisor requires a valid GEMINI_API_KEY to generate recommendations."
        
    # Prepare prompt data
    prompt_data = {
        "Health Score": kpi_data["health_score"],
        "Top Runout Risks": [f"{r['name']} (Runout: {r['days_to_runout']} days)" for r in sorted(kpi_data["runouts"]["data"], key=lambda x: x['days_to_runout'])[:10]],
        "Top Dead Stock": [f"{r['name']} (Value: ${r['inventory_value']})" for r in sorted(kpi_data["dead_stock"]["data"], key=lambda x: x['inventory_value'], reverse=True)[:10]],
        "Top Expiry Risks": [f"{r['name']} {r['batch']} (Loss: ${r['estimated_loss']})" for r in sorted(kpi_data["expiry_risks"]["data"], key=lambda x: x['estimated_loss'], reverse=True)[:10]]
    }
    
    prompt = f"""
    You are an AI Inventory Advisor for a pharmacy. Analyze the following KPIs and provide an executive summary.
    
    Data:
    {json.dumps(prompt_data, indent=2)}
    
    Provide:
    1. Executive Summary (2 sentences)
    2. Critical Reorder Recommendations
    3. Expiry Reduction Actions
    4. General Inventory Optimization
    
    Format as clean Markdown using bullet points. Do NOT hallucinate data. Be very concise.
    """
    
    try:
        from flask import current_app
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        model = genai.GenerativeModel(current_app.config["GEMINI_MODEL"])
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logging.exception("AI Advisor Gemini failure")
        return "AI Advisor temporarily unavailable."
