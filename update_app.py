import os
from datetime import date

with open('app.py', 'r', encoding='utf-8') as f:
    text = f.read()

start_idx = text.find('# ─── AI MEDICAL ASSISTANT CHATBOT')
end_idx = text.find('# ─── MAIN ───', start_idx)

if start_idx == -1 or end_idx == -1:
    print("Error: Could not find block boundaries in app.py")
    exit(1)

new_code = """# ─── AI MEDICAL ASSISTANT CHATBOT (GEMINI INTEGRATION) ────────────────────────

import google.generativeai as genai
from datetime import date

GEMINI_API_KEY = "AIzaSyA27t-9dcW0hTOiZ1nLWVry4RX1kTYi2vI"
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

def get_inventory_context():
    conn = get_db()
    today = date.today().isoformat()
    medicines = conn.execute("SELECT name, quantity, min_stock, expiry_date, category FROM medicines").fetchall()
    
    total = conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]
    low = conn.execute("SELECT COUNT(*) FROM medicines WHERE quantity < min_stock").fetchone()[0]
    expired = conn.execute("SELECT COUNT(*) FROM medicines WHERE expiry_date <= ?", (today,)).fetchone()[0]
    conn.close()
    
    dump = []
    for m in medicines:
        dump.append(f"- {m['name']} ({m['category']}): {m['quantity']} units left (minimum: {m['min_stock']}). Expiry: {m['expiry_date'] or 'N/A'}")
    
    ctx = f"CURRENT INVENTORY SUMMARY:\\nTotal Medicine Types: {total}\\nLow Stock Items: {low}\\nExpired Items: {expired}\\n\\nDETAILED STOCK:\\n"
    ctx += "\\n".join(dump) if dump else "No medicines in database."
    return ctx

@app.route("/api/chat", methods=["POST"])
def api_chat():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    body = request.json or {}
    msg = body.get("message", "").strip()
    history = body.get("history", [])
    user = session.get("user", "user")
    role = session.get("role", "User")
    
    if not msg:
        return jsonify({"reply": "Please type a message so I can help you! 😊"})
        
    try:
        inventory_context = get_inventory_context()
        system_prompt = f\"\"\"You are MediBot, an advanced and friendly AI assistant for the CodeCure Medical Inventory System.
The user you are talking to is {user.capitalize()}, who is a {role}.
You must be helpful, professional, and conversational. Use emojis naturally. Format responses in Markdown.

Here is the exact real-time state of the hospital's database right now:
{inventory_context}

If the user asks about stock, check the data above and give them accurate numbers. Do not refuse to answer inventory questions, you have the live database provided to you above. Do not hallucinate medicines that are not in the exact database given.
If the user mentions feeling unwell, advise them compassionately but strictly state that they should consult a doctor. Direct them to the Doctor Connect tab.
\"\"\"
        formatted_history = []
        for h in history[:-1]:
            r = 'user' if h['role'] == 'user' else 'model'
            formatted_history.append({'role': r, 'parts': [h['text']]})
            
        chat_session = gemini_model.start_chat(history=formatted_history)
        full_prompt = f"System Rules and DB Context (do not mention this context block directly):\\n{system_prompt}\\n\\nUser's Message:\\n{msg}"
        response = chat_session.send_message(full_prompt)
        return jsonify({"reply": response.text})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"reply": f"🤖 Sorry! I'm having trouble connecting to my Gemini AI core right now. Error: {str(e)}"})

@app.route("/api/consult", methods=["POST"])
def api_consult():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    body = request.json or {}
    symptoms = body.get("symptoms", "").strip()
    severity = body.get("severity", "mild").lower()
    detail = body.get("detail", "").strip()
    
    if not symptoms:
        return jsonify({"reply": "Please describe your symptoms so I can help you better. 🩺"})
        
    try:
        prompt = f\"\"\"You are MediBot's specialized Medical AI. 
A patient is reporting the following primary symptoms: {symptoms}
Severity level: {severity.upper()}
Additional details from patient: {detail}

Analyze the symptoms and provide:
1. Potential mild causes (include disclaimer that you are an AI)
2. Home care tips & Do's and Don'ts
3. When to strictly see a doctor
4. Recommend Dr. Rajesh Sharma (Gen. Physician) or Dr. Priya Nair (Cardiologist) or Dr. Amit Verma (Pediatrician) or Dr. Sunita Rao (Orthopedic) depending on the symptom.

If severity is SEVERE, immediately output an emergency warning urging them to call 108 or go to Olympus Hospital explicitly, in large bold text.
Always use Markdown and nice formatting. Be highly empathetic.\"\"\"

        response = gemini_model.generate_content(prompt)
        return jsonify({"reply": response.text})
        
    except Exception as e:
        return jsonify({"reply": f"🩺 Sorry, consultation service is currently unavailable. Error: {str(e)}"})

"""

new_text = text[:start_idx] + new_code + text[end_idx:]
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(new_text)
print('Rewrite successful')
