#!/usr/bin/env python3
"""Debug the IMG-20240426-WA0033.jpg parsing"""

import sys

# Force reload
for mod in list(sys.modules.keys()):
    if 'backend' in mod:
        del sys.modules[mod]

from backend.text_correction import apply_text_corrections
from backend.parser import parse_receipt_text

# The actual OCR text from queue_store.json
ocr_text = """AS
AHMEDSHARIF&BROS
LEMONPURCHASER&COMMAGENT
DARUSHAFAXROAD.HYDERABAD500024
Phone.040-24412139, 9949.00 3337.86
VoucherNumber214
YoucherDate 26/04/2024
TK
SuppNane
SrandTotal dealtge
Total 8 14580oO0
-: Comm?400: S832n
-- Less For Damages POQOn
- UnLoading S842
l4 0.00
L-FAndCash 44008.00"""

print("=== ORIGINAL OCR TEXT ===")
print(ocr_text)
print("\n" + "="*80 + "\n")

# Apply corrections
corrected = apply_text_corrections(ocr_text)
print("=== AFTER TEXT CORRECTIONS ===")
print(corrected)
print("\n" + "="*80 + "\n")

# Show lines
lines = corrected.split('\n')
print("=== LINES (indexed) ===")
for i, line in enumerate(lines):
    print(f"Line {i}: {repr(line)}")
print("\n" + "="*80 + "\n")

# Parse
result = parse_receipt_text(corrected)
print("=== PARSE RESULT ===")
print(f"supplier_name: {repr(result.get('supplier_name'))}")
print(f"vendor_details: {repr(result.get('vendor_details'))}")
print(f"voucher_number: {repr(result.get('voucher_number'))}")
print("\n" + "="*80 + "\n")

# Check
if result.get('supplier_name') == 'TK':
    print("✅ CORRECT: Supplier name is 'TK'")
else:
    print(f"❌ WRONG: Supplier name is {repr(result.get('supplier_name'))}, expected 'TK'")
