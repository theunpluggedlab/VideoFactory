import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("API Key not found in .env")
    exit()

genai.configure(api_key=api_key)

print("Fetching available models...")
try:
    models = genai.list_models()
    found_image_model = False
    
    with open("models_list.txt", "w", encoding="utf-8") as f:
        f.write(f"{'Model Name':<40} | {'Supported Methods'}\n")
        f.write("-" * 80 + "\n")
        
        for m in models:
            methods = ", ".join(m.supported_generation_methods)
            f.write(f"{m.name:<40} | {methods}\n")

    print("Model list saved to models_list.txt")

    print("-" * 80)
    print("Note: 'generateContent' method is typically used for text/chat.")
    print("      For image generation, look for models that might support it explicitly or check documentation.")
    
except Exception as e:
    print(f"Error listing models: {e}")
