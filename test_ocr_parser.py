from backend.ocr_service import extract_text
from backend.parser import parse_receipt_text
import json

# Test OCR
text = extract_text('uploads/IMG-20241126-WA0117.jpg')
print("===== RAW OCR TEXT =====")
print(text)
print("\n===== TEXT LENGTH =====")
print(len(text))

# Test Parser
parsed = parse_receipt_text(text)
print("\n===== PARSED DATA =====")
print(json.dumps(parsed, indent=2, ensure_ascii=False))
