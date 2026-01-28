#!/usr/bin/env python3
"""
Investigate the specific voucher with 'AS' supplier name issue.
"""

import json
from backend.text_correction import apply_text_corrections
from backend.parser import parse_receipt_text

# Load queue_store
with open('backend/data/queue_store.json', 'r') as f:
    queue_data = json.load(f)

# Find the problematic batch
batch_id = 'c4d2fb03-1b9b-4143-96f6-8ddbf0528b45'
batch = queue_data[batch_id]

print("=" * 100)
print(f"INVESTIGATING BATCH: {batch_id}")
print("=" * 100)

for file_idx, file_info in enumerate(batch['files']):
    filename = file_info.get('original_filename')
    
    if filename != 'IMG-20240426-WA0033.jpg':
        continue
    
    print(f"\n📄 File: {filename}")
    print("-" * 100)
    
    ocr_result = file_info.get('ocr_result') or {}
    parsed_data = file_info.get('parsed_data') or {}
    
    raw_text = ocr_result.get('text', '')
    
    print(f"\n[STEP 1] RAW OCR TEXT:")
    print("-" * 100)
    print(raw_text[:600])
    print()
    
    print(f"\n[STEP 2] AFTER TEXT CORRECTION:")
    print("-" * 100)
    corrected_text = apply_text_corrections(raw_text)
    print(corrected_text[:600])
    print()
    
    print(f"\n[STEP 3] TEXT LINES (first 15):")
    print("-" * 100)
    lines = [ln.strip() for ln in corrected_text.splitlines() if ln.strip()]
    for i, ln in enumerate(lines[:15]):
        print(f"Line {i}: '{ln}'")
    print()
    
    print(f"\n[STEP 4] PARSING RESULTS:")
    print("-" * 100)
    
    # Check regex matching
    import re
    RE_SUPPLIER_PREFIX = re.compile(r"(?:Supp|SUPP)\s*(?:Name|NAME|Nam[3e])?\s*[:\-\s]\s+(.+)", re.IGNORECASE)
    
    for i, ln in enumerate(lines[:15]):
        match = RE_SUPPLIER_PREFIX.search(ln)
        if match:
            print(f"Line {i}: '{ln}'")
            print(f"  ✓ REGEX MATCHED! Groups: {match.groups()}")
    
    print()
    
    master = parsed_data.get('master', {}) if parsed_data else {}
    supplier_name = master.get('supplier_name') if master else None
    vendor_name = master.get('vendor_details') if master else None
    
    print(f"Final Result:")
    print(f"  Supplier: {supplier_name}")
    print(f"  Vendor: {vendor_name}")
    print()
    
    # Look for 'Supp Name' in text
    if 'supp name' in corrected_text.lower():
        print("✓ Text CONTAINS 'Supp Name' label")
        # Find it
        for i, ln in enumerate(lines):
            if 'supp name' in ln.lower():
                print(f"  Found at line {i}: '{ln}'")
    else:
        print("✗ Text DOES NOT contain 'Supp Name' label")
    
    break
