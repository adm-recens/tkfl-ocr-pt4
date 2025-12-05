from backend.ocr_service import extract_text
from backend.parser import parse_receipt_text
import json
import os

# List files in uploads
print("=== FILES IN UPLOADS ===")
files = os.listdir('uploads')
for f in files:
    print(f"  - {f}")

if files:
    latest_file = files[-1]
    filepath = os.path.join('uploads', latest_file)
    print(f"\n=== TESTING WITH: {latest_file} ===")
    
    # Extract text
    text = extract_text(filepath)
    print("\n=== RAW OCR TEXT ===")
    print(text)
    print(f"\nLength: {len(text)} characters")
    
    # Parse
    parsed = parse_receipt_text(text)
    print("\n=== PARSED DATA ===")
    print(json.dumps(parsed, indent=2))
else:
    print("No files found in uploads directory!")
