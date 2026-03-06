#!/usr/bin/env python3
"""Debug the parsing flow to understand why test 1 fails."""

from backend.text_correction import apply_text_corrections
from backend.parser import parse_receipt_text

# Test case 1 with OCR error
ocr_raw = """AS
AHMED SHARIF & BROS
LEMON PURCHASER & COMM AGENT
DARUSHAFA X ROAD, HYDERABAD 500024
Phone: 040-24412139, 9949333786

Voucher Number 214
Voucher Date 26/04/2024
SuppNanm3 TK

3 210000 630000"""

print("=" * 70)
print("STEP 1: TEXT CORRECTION")
print("=" * 70)

corrected_text = apply_text_corrections(ocr_raw)
print("Corrected text (first 400 chars):")
print(corrected_text[:400])
print()

print("=" * 70)
print("STEP 2: PARSING LINES")
print("=" * 70)

lines = [ln.strip() for ln in corrected_text.splitlines() if ln.strip()]
for i, ln in enumerate(lines[:10]):
    print(f"Line {i}: '{ln}'")
print()

print("=" * 70)
print("STEP 3: REGEX MATCHING")
print("=" * 70)

import re
RE_SUPPLIER_PREFIX = re.compile(r"(?:Supp|SUPP)\s*(?:Name|NAME|Nam[3e])?\s*[:\-\s]\s*(.+)", re.IGNORECASE)

for i, ln in enumerate(lines):
    if i < 12:  # Check first 12 lines
        match = RE_SUPPLIER_PREFIX.search(ln)
        print(f"Line {i}: '{ln}'")
        if match:
            print(f"  ✓ REGEX MATCHED: groups={match.groups()}")
        else:
            print(f"  ✗ No match")
        print()

print("=" * 70)
print("STEP 4: FULL PARSE")
print("=" * 70)

result = parse_receipt_text(corrected_text)
print(f"Supplier Name: {result['master']['supplier_name']}")
print(f"Vendor Details: {result['master']['vendor_details']}")
