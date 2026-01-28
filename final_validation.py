#!/usr/bin/env python3
"""Analyze all real vouchers without emoji output"""

import json
from backend.text_correction import apply_text_corrections
from backend.parser import parse_receipt_text

def analyze_queue_store():
    """Analyze all vouchers in queue_store.json"""
    
    queue_file = 'backend/data/queue_store.json'
    
    with open(queue_file, 'r', encoding='utf-8') as f:
        queue_data = json.load(f)
    
    print("=" * 80)
    print("ANALYZING REAL VOUCHERS FROM QUEUE_STORE.JSON")
    print("=" * 80)
    print(f"\nTotal batches: {len(queue_data)}")
    
    total_vouchers = 0
    good_count = 0
    issues_count = 0
    issues_list = []
    
    for batch_idx, (batch_id, batch) in enumerate(queue_data.items()):
        files = batch.get('files', [])
        
        print(f"\nBatch {batch_idx + 1} ({batch_id}): {len(files)} files")
        
        for file_idx, file_info in enumerate(files):
            total_vouchers += 1
            filename = file_info.get('original_filename', 'unknown')
            ocr_result = file_info.get('ocr_result') or {}
            
            # Get extracted text
            raw_text = ocr_result.get('text', '')
            
            if not raw_text:
                print(f"  {file_idx + 1}. {filename}: NO OCR TEXT")
                continue
            
            # Apply corrections and parse
            corrected_text = apply_text_corrections(raw_text)
            parsed = parse_receipt_text(corrected_text)
            
            supplier_name = parsed['master'].get('supplier_name')
            vendor_name = parsed['master'].get('vendor_details')
            
            # Check if good or bad
            is_good = False
            issue_desc = None
            
            if supplier_name is None:
                issue_desc = "No supplier label found"
            elif len(supplier_name) < 2:
                issue_desc = f"Supplier name too short: '{supplier_name}'"
            elif len(supplier_name) > 50:
                issue_desc = f"Supplier name too long: '{supplier_name}'"
            else:
                is_good = True
            
            if is_good:
                good_count += 1
                print(f"  {file_idx + 1}. {filename}: GOOD (supplier='{supplier_name}')")
            else:
                issues_count += 1
                print(f"  {file_idx + 1}. {filename}: ISSUE ({issue_desc})")
                issues_list.append({
                    'filename': filename,
                    'supplier': supplier_name,
                    'vendor': vendor_name,
                    'issue': issue_desc
                })
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nTotal vouchers analyzed: {total_vouchers}")
    print(f"Good extractions: {good_count}")
    print(f"Issues found: {issues_count}")
    
    if issues_list:
        print(f"\nISSUES DETAILS ({len(issues_list)} vouchers):")
        print("-" * 80)
        for i, issue in enumerate(issues_list, 1):
            print(f"\n{i}. {issue['filename']}")
            print(f"   Supplier: {issue['supplier']}")
            print(f"   Vendor: {issue['vendor']}")
            print(f"   Issue: {issue['issue']}")
    
    # Final status
    if issues_count == 0:
        print("\n*** ALL VOUCHERS PASSED ***")
        return True
    else:
        print(f"\n*** {issues_count} ISSUES REMAIN ***")
        return False

if __name__ == '__main__':
    success = analyze_queue_store()
    exit(0 if success else 1)
