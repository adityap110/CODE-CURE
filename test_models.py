import google.generativeai as genai

genai.configure(api_key="AIzaSyA27t-9dcW0hTOiZ1nLWVry4RX1kTYi2vI")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)
