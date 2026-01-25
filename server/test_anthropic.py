import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv()

print("Debugging Connection...")
try:
    from anthropic import Anthropic
    import json
    
    # Check for API KEY
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        try:
            with open("config.json", "r") as f:
                conf = json.load(f)
                api_key = conf.get("anthropic_api_key").strip()
        except:
            pass
            
    if not api_key:
        print("ERROR: No API Key found.")
        exit(1)

    print(f"\nTesting Anthropic Model: {os.getenv('ANTHROPIC_MODEL')}")
    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL"),
        max_tokens=10,
        messages=[{"role": "user", "content": "Hello"}]
    )
    print("Anthropic Success:", message.content[0].text)

except Exception as e:
    print(f"Anthropic Failed: {e}")
