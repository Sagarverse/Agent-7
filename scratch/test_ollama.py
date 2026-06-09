import requests
import base64
from PIL import Image
import io

# 1. Create a simple red square image
img = Image.new('RGB', (100, 100), color = 'red')
img_byte_arr = io.BytesIO()
img.save(img_byte_arr, format='PNG')
img_bytes = img_byte_arr.getvalue()

# 2. Encode to base64 (exactly as we do in brain.py)
b64_image = base64.b64encode(img_bytes).decode('utf-8')

# 3. Construct the payload for Ollama
payload = {
    "model": "llava",
    "messages": [
        {
            "role": "user",
            "content": "What is the single dominant color of this image? Reply with just the color name.",
            "images": [b64_image]
        }
    ],
    "stream": False
}

print("Sending image payload to Ollama...")
try:
    response = requests.post("http://localhost:11434/api/chat", json=payload)
    response.raise_for_status()
    result = response.json()
    print("Ollama Response:", result["message"]["content"].strip())
except Exception as e:
    print("Error:", e)
    if hasattr(e, 'response') and e.response is not None:
        print("Response Text:", e.response.text)
