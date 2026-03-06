#!/usr/bin/env python3
"""
Comprehensive end-to-end test for supplier name extraction fix.
Tests the complete flow: OCR errors → Text Correction → Parsing
"""

from backend.text_correction import apply_text_corrections
from backend.parser import parse_receipt_text

test_cases = [
    {
        'name': 'Real-world example with OCR errors and "AS" prefix',
        'ocr_text': """AS
AHMED SHARIF & BROS
LEMON PURCHASER & COMM AGENT
DARUSHAFA X ROAD, HYDERABAD 500024
Phone: 040-24412139, 9949333786

Voucher Number 214
Voucher Date 26/04/2024
SuppNanm3      TK

3   210000   630000
2   -100.00  4200.00
Total 8 14580.00""",
        'expected_supplier': 'TK',
        'expected_vendor': 'AHMED SHARIF & BROS'
    },
    {
        'name': 'OCR error: SuppNam3 (with "3" instead of "e")',
        'ocr_text': """RAVI TRADERS
DELHI

Voucher Number 105
Voucher Date 15/03/2024
SuppNam3      SUNNY ENTERPRISES

2 1500.00 3000.00""",
        'expected_supplier': 'SUNNY ENTERPRISES',
        'expected_vendor': 'RAVI TRADERS'
    },
    {
        'name': 'Correct "Supp Name" text (no OCR errors)',
        'ocr_text': """SHARMA & CO
MUMBAI

Voucher Number 301
Voucher Date 10/01/2024
Supp Name KUMAR SUPPLY

5 2000.00 10000.00""",
        'expected_supplier': 'KUMAR SUPPLY',
        'expected_vendor': 'SHARMA & CO'
    },
    {
        'name': 'Missing supplier name label (should be None)',
        'ocr_text': """ABC TRADERS
BENGALURU

Voucher Number 202
Voucher Date 05/06/2024

3 1800.00 5400.00""",
        'expected_supplier': None,
        'expected_vendor': 'ABC TRADERS'
    }
]

print("=" * 80)
print("COMPREHENSIVE SUPPLIER NAME EXTRACTION TEST")
print("=" * 80)
print()

passed = 0
failed = 0

for i, test in enumerate(test_cases, 1):
    print(f"TEST {i}: {test['name']}")
    print("-" * 80)
    
    # Apply text corrections
    corrected_text = apply_text_corrections(test['ocr_text'])
    
    # Parse receipt
    result = parse_receipt_text(corrected_text)
    
    supplier_name = result['master']['supplier_name']
    vendor_details = result['master']['vendor_details']
    
    # Check results
    supplier_match = supplier_name == test['expected_supplier']
    vendor_match = vendor_details == test['expected_vendor']
    
    print(f"Expected Supplier: {test['expected_supplier']}")
    print(f"Got Supplier:      {supplier_name}")
    print(f"Supplier Match:    {'✅ PASS' if supplier_match else '❌ FAIL'}")
    print()
    print(f"Expected Vendor:   {test['expected_vendor']}")
    print(f"Got Vendor:        {vendor_details}")
    print(f"Vendor Match:      {'✅ PASS' if vendor_match else '❌ FAIL'}")
    print()
    
    if supplier_match and vendor_match:
        print("✅ TEST PASSED")
        passed += 1
    else:
        print("❌ TEST FAILED")
        failed += 1
    
    print()

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Total Tests: {len(test_cases)}")
print(f"Passed: {passed} ✅")
print(f"Failed: {failed} ❌")
print()

if failed == 0:
    print("🎉 ALL TESTS PASSED! The supplier name extraction is working correctly.")
else:
    print(f"⚠️  {failed} test(s) failed. Please review the fixes.")
