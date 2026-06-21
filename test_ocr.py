import requests
import json

s = requests.Session()
login_res = s.post('http://127.0.0.1:5000/', data={'username':'pharmacist', 'password':'1234'})

img_path = r"C:\Users\adity\.gemini\antigravity\brain\7dfc6515-dab3-48f2-bbf3-17dc895c1a22\test_prescription_dangerous_1781772783676.png"
with open(img_path, 'rb') as f:
    files = {'file': ('prescription.png', f, 'image/png')}
    res = s.post('http://127.0.0.1:5000/api/scan-prescription', files=files)

print("Scan Status:", res.status_code)
if res.status_code == 200:
    print(json.dumps(res.json(), indent=2))
else:
    print(res.text)
