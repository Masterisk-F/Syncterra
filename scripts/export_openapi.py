import json
import sys
import os

# Ensure backend module is found
sys.path.append(os.getcwd())

from backend.main import app

def export_openapi():
    openapi_data = app.openapi()
    with open("openapi.json", "w", encoding="utf-8") as f:
        json.dump(openapi_data, f, indent=2, ensure_ascii=False)
    print("openapi.json generated successfully.")

if __name__ == "__main__":
    export_openapi()
