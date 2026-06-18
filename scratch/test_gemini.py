import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("GEMINI_API_KEY")
print("API Key:", key[:10] + "..." if key else None)
genai.configure(api_key=key)

models_to_test = [
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-2.5-flash",
    "models/gemini-1.5-flash",
    "models/gemini-2.5-flash",
    "gemini-pro"
]

for model_name in models_to_test:
    print(f"\nTesting model: {model_name}")
    try:
        model = genai.GenerativeModel(model_name=model_name)
        response = model.generate_content("Say hello in one word.")
        print(f"Success! Response: {response.text.strip()}")
    except Exception as e:
        print(f"Failed: {type(e).__name__}: {e}")
