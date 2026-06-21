import json
import os
import requests
from io import BytesIO
from PIL import Image

def test_gemini():
    # Load .env manually for the test
    with open('.env') as f:
        for line in f:
            if '=' in line:
                k, v = line.strip().split('=', 1)
                os.environ[k] = v

    # Setup test image
    img = Image.new('RGB', (100, 100), color='white')
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_byte_arr.seek(0)
    
    from app import app
    app.testing = True
    
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user'] = 'admin'
            sess['role'] = 'Admin'
            
        print("\n--- Testing Valid Key: /api/chat ---")
        res = client.post('/api/chat', json={"message": "Say hello!"})
        print(f"Status: {res.status_code}")
        print(f"Response ok: {res.get_json() is not None}")
        
        print("\n--- Testing Valid Key: /api/consult ---")
        res = client.post('/api/consult', json={"symptoms": "Headache", "severity": "mild"})
        print(f"Status: {res.status_code}")
        print(f"Response ok: {res.get_json() is not None}")
        
        print("\n--- Testing Valid Key: /api/scan-medicine ---")
        img_byte_arr.seek(0)
        res = client.post('/api/scan-medicine', data={'file': (img_byte_arr, 'test.jpg')}, content_type='multipart/form-data')
        print(f"Status: {res.status_code}")
        print(f"Response ok: {res.get_json() is not None}")

if __name__ == '__main__':
    test_gemini()
