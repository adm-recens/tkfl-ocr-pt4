#!/usr/bin/env python3
"""Test the final fix on problematic voucher IMG-20240426-WA0033.jpg"""

import json
import sys
import os

# Force module reload
if 'backend.parser' in sys.modules:
    del sys.modules['backend.parser']
if 'backend.text_correction' in sys.modules:
    del sys.modules['backend.text_correction']

from backend.parser import parse_receipt_text
from backend.text_correction import apply_text_corrections

# Load the problematic batch from queue_store.json
with open('backend/data/queue_store.json', 'r') as f:
    queue_store = json.load(f)

# Batch 37 where the issue appears
target_batch_id = "c4d2fb03-1b9b-4143-96f6-8ddbf0528b45"
batch = queue_store[target_batch_id]

filename = "IMG-20240426-WA0033.jpg"
file_entry = None

for f in batch.get('files', []):
    if f['filename'] == filename:
        file_entry = f
        break

if not file_entry:
    print(f"ERROR: Could not find {filename} in batch {target_batch_id}")
    sys.exit(1)

ocr_text = file_entry.get('ocr_text', '')
print(f"Original OCR text:")
print("=" * 80)
print(ocr_text)
print("=" * 80)
print()

# Apply corrections
corrected_text = apply_text_corrections(ocr_text)
print(f"After text corrections:")
print("=" * 80)
print(corrected_text)
print("=" * 80)
print()

# Parse
result = parse_receipt_text(corrected_text)
print(f"Parse result:")
print("-" * 80)
print(f"Supplier Name: {result.get('supplier_name', 'NOT FOUND')}")
print(f"Vendor: {result.get('vendor_details', 'NOT FOUND')}")
print(f"Voucher Number: {result.get('voucher_number', 'NOT FOUND')}")
print("-" * 80)

# Check if fixed
if result.get('supplier_name') == 'TK':
    print("\n✅ SUCCESS: Supplier name correctly extracted as 'TK'")
else:
    print(f"\n❌ FAILED: Supplier name is '{result.get('supplier_name')}' instead of 'TK'")
