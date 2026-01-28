#!/usr/bin/env python3
"""Test the supplier name extraction fix."""

from backend.parser import parse_receipt_text

# Test case 1: The problematic case from queue_store.json
ocr_text_1 = """AS
AHMED SHARIF & BROS
LEMON PURCHASER & COMM AGENT
DARUSHAFA X ROAD, HYDERABAD 500024
Phone: 040-24412139, 9949333786

Voucher Number 214
Voucher Date 26/04/2024
Supp Name TK

3 210000 630000
2 -100.00 4200.00
3 1360.00 4080.00

Total 8 14580.00
(-) Comm 4.00 5832.00
(-) Less For Damages 729.00
(-) UnLoading 58.42
(-) L/F And Cash 4408.00

Grand Total"""

# Test case 2: Without AS at the top
ocr_text_2 = """AHMED SHARIF & BROS
LEMON PURCHASER & COMM AGENT
DARUSHAFA X ROAD, HYDERABAD 500024
Phone: 040-24412139, 9949333786

Voucher Number 164
Voucher Date 10/12/2024
Supp Name TK

2 680.00 8160.00
2 600.00 1200.00
4 500.00"""

# Test case 3: Short vendor name without Supp Name label
ocr_text_3 = """RAVI TRADERS
NEW DELHI
Phone: 011-2345678

Voucher Number 105
Voucher Date 15/03/2024

2 1500.00 3000.00"""

print("=" * 70)
print("TEST 1: OCR with 'AS' at top (problematic case)")
print("=" * 70)
result1 = parse_receipt_text(ocr_text_1)
print(f"Supplier Name: {result1['master']['supplier_name']}")
print(f"Vendor Details: {result1['master']['vendor_details']}")
print(f"Expected: 'TK', Got: '{result1['master']['supplier_name']}'")
status1 = "✅ PASS" if result1['master']['supplier_name'] == "TK" else "❌ FAIL"
print(f"Status: {status1}\n")

print("=" * 70)
print("TEST 2: OCR without 'AS' at top")
print("=" * 70)
result2 = parse_receipt_text(ocr_text_2)
print(f"Supplier Name: {result2['master']['supplier_name']}")
print(f"Vendor Details: {result2['master']['vendor_details']}")
print(f"Expected: 'TK', Got: '{result2['master']['supplier_name']}'")
status2 = "✅ PASS" if result2['master']['supplier_name'] == "TK" else "❌ FAIL"
print(f"Status: {status2}\n")

print("=" * 70)
print("TEST 3: OCR with unnamed supplier (no 'Supp Name' label)")
print("=" * 70)
result3 = parse_receipt_text(ocr_text_3)
print(f"Supplier Name: {result3['master']['supplier_name']}")
print(f"Vendor Details: {result3['master']['vendor_details']}")
print(f"Note: Supplier should be None or extracted from context\n")

print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Test 1 (AS at top, should get TK): {status1}")
print(f"Test 2 (No AS, should get TK): {status2}")
