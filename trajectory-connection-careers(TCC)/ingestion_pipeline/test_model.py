import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Sanity check with the requested model string
model_name = "models/gemini-flash-latest"
print(f"Testing model: {model_name}")

try:
    model = genai.GenerativeModel(model_name)
    response = model.generate_content("Say hello in one sentence.")
    print(f"Response: {response.text}")
    print("\n✅ Success! Your API key and model string are working.")
    print(f"Update your configs/llm.yaml to use: \"{model_name}\"")
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("If you hit 429, your daily quota is exhausted.")
    print("If you hit 404, the model name is incorrect.")
