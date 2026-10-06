import ollama
from PIL import ImageGrab
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_PATH = os.path.join(BASE_DIR, "screen.png")

# Take screenshot
screenshot = ImageGrab.grab()
screenshot.save(SCREENSHOT_PATH)

print("Screenshot captured.")

# Ask vision model
response = ollama.chat(
    model="moondream",
    messages=[
        {
            "role": "user",
            "content": "Describe what you can see on this screen. Keep it brief.",
            "images": [SCREENSHOT_PATH]
        }
    ]
)

print("\nAI:")
print(response["message"]["content"])