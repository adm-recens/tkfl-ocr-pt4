#!/usr/bin/env python3
"""
Analyze real vouchers from queue_store.json to check for supplier name extraction issues.
"""

import json
import os
from pathlib import Path
from backend.text_correction import apply_text_corrections
from backend.parser import parse_receipt_text

def analyze_queue_store():
    """Analyze all vouchers in queue_store.json"""
    
    queue_file = 'backend/data/queue_store.json'
    if not os.path.exists(queue_file):
        print(f"Queue file not found: {queue_file}")
        return
    
    with open(queue_file, 'r') as f:
        queue_data = json.load(f)
    
    print("=" * 100)
    print("ANALYZING REAL VOUCHERS FROM QUEUE_STORE.JSON")
    print("=" * 100)
    print(f"\nTotal batches: {len(queue_data)}")
    
    total_vouchers = 0
    supplier_issues = []
    good_extractions = []
    
    for batch_idx, (batch_id, batch) in enumerate(queue_data.items()):
        files = batch.get('files', [])
        
        print(f"\nBatch {batch_idx + 1} (ID: {batch_id}): {len(files)} files")
        print("-" * 100)
        
        for file_idx, file_info in enumerate(files):
            total_vouchers += 1
            filename = file_info.get('original_filename', 'unknown')
            ocr_result = file_info.get('ocr_result') or {}
            parsed_data = file_info.get('parsed_data') or {}
            
            # Get extracted text
            raw_text = ocr_result.get('text', '')
            
            if not raw_text:
                print(f"  {file_idx + 1}. {filename}: NO OCR TEXT")
                continue
            
            # Get parsed supplier info
            master = parsed_data.get('master', {}) if parsed_data else {}
            supplier_name = master.get('supplier_name') if master else None
            vendor_name = master.get('vendor_details') if master else None
            
            # Check for issues
            issue_found = False
            issue_desc = []
            
            # Issue 1: Missing supplier name when text has "Supp Name"
            text_lower = raw_text.lower()
            has_supp_label = 'supp name' in text_lower or 'supp nam' in text_lower
            
            if has_supp_label and not supplier_name:
                issue_desc.append("HAS 'Supp Name' label but supplier_name is EMPTY/NULL")
                issue_found = True
            
            # Issue 2: Supplier name is "AS" or very short (likely wrong)
            if supplier_name and supplier_name in ['AS', 'A', 'S', 'O', 'I', 'L']:
                issue_desc.append(f"Supplier name is '{supplier_name}' (likely wrong - too short)")
                issue_found = True
            
            # Issue 3: Supplier name contains vendor info
            if supplier_name and vendor_name and vendor_name.upper() in supplier_name.upper():
                issue_desc.append(f"Supplier name contains vendor name: '{supplier_name}' (vendor: '{vendor_name}')")
                issue_found = True
            
            if issue_found:
                supplier_issues.append({
                    'file': filename,
                    'batch': batch_id,
                    'supplier': supplier_name,
                    'vendor': vendor_name,
                    'issues': issue_desc,
                    'raw_text': raw_text[:300]
                })
                print(f"  {file_idx + 1}. {filename}")
                print(f"     ⚠️  ISSUES FOUND:")
                for issue in issue_desc:
                    print(f"        - {issue}")
            else:
                good_extractions.append({
                    'file': filename,
                    'supplier': supplier_name,
                    'vendor': vendor_name
                })
                status = "✅" if supplier_name else "⚠️  (no supplier label)"
                print(f"  {file_idx + 1}. {filename}: {status}")
                if supplier_name:
                    print(f"     Supplier: {supplier_name}")
                if vendor_name:
                    print(f"     Vendor: {vendor_name}")
    
    # Summary
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"\nTotal vouchers analyzed: {total_vouchers}")
    print(f"✅ Good extractions: {len(good_extractions)}")
    print(f"⚠️  Issues found: {len(supplier_issues)}")
    
    if supplier_issues:
        print(f"\n⚠️  ISSUES DETAILS ({len(supplier_issues)} vouchers with issues):")
        print("-" * 100)
        for i, issue in enumerate(supplier_issues, 1):
            print(f"\n{i}. {issue['file']} (Batch: {issue['batch']})")
            print(f"   Supplier: {issue['supplier']}")
            print(f"   Vendor: {issue['vendor']}")
            for desc in issue['issues']:
                print(f"   ⚠️  {desc}")
            print(f"   Text preview: {issue['raw_text'][:150]}...")
    else:
        print("\n✅ No supplier name extraction issues found!")

if __name__ == "__main__":
    analyze_queue_store()
