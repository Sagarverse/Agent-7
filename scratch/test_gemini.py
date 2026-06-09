import os
from dotenv import load_dotenv
load_dotenv()
from google import genai

client = genai.Client()

for test_model in ["gemini-3.5-flash"]:
    print(f"\nTesting {test_model}...")
    try:
        response = client.models.generate_content(
            model=test_model,
            contents="Say hello!",
        )
        print(f"Success! {test_model} response: {response.text}")
    except Exception as e:
        print(f"Error for {test_model}: {e}")
