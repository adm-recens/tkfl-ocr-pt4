#!/usr/bin/env python3
"""Simple test for the problematic voucher - no emoji output"""

import json
from backend.text_correction import apply_text_corrections
from backend.parser import parse_receipt_text

# Load the problematic batch
with open('backend/data/queue_store.json', 'r', encoding='utf-8') as f:
    queue_store = json.load(f)

target_batch_id = "c4d2fb03-1b9b-4143-96f6-8ddbf0528b45"
batch = queue_store[target_batch_id]

# Find IMG-20240426-WA0033.jpg
for file_info in batch['files']:
    if file_info['original_filename'] == 'IMG-20240426-WA0033.jpg':
        ocr_result = file_info.get('ocr_result', {})
        ocr_text = ocr_result.get('text', '')
        
        if not ocr_text:
            print("No OCR text for IMG-20240426-WA0033.jpg")
            break
        
        print("=== ORIGINAL OCR TEXT ===")
        print(ocr_text)
        print("\n=== AFTER TEXT CORRECTIONS ===")
        
        corrected = apply_text_corrections(ocr_text)
        print(corrected)
        
        print("\n=== PARSE RESULT ===")
        result = parse_receipt_text(corrected)
        supplier = result['master'].get('supplier_name')
        vendor = result['master'].get('vendor_details')
        voucher = result['master'].get('voucher_number')
        
        print(f"Supplier: {supplier}")
        print(f"Vendor: {vendor}")
        print(f"Voucher: {voucher}")
        
        if supplier == 'TK':
            print("\nSUCCESS: Supplier correctly extracted as 'TK'")
        else:
            print(f"\nFAIL: Supplier is '{supplier}' instead of 'TK'")
        
        break
