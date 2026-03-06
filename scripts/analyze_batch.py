#!/usr/bin/env python3
"""
Analyze latest batch: Compare OCR output with parsed field data
to identify where extraction succeeded but parsing failed.
"""

import sys
import os
import json
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from db import get_db
from logger import setup_logger

logger = setup_logger('batch_analyzer')

def get_batch_data():
    """Get latest batch information"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get latest batch
        cursor.execute("""
            SELECT batch_id, upload_date, total_records, processed_records, status
            FROM batches
            ORDER BY upload_date DESC
            LIMIT 1
        """)
        
        latest_batch = cursor.fetchone()
        if not latest_batch:
            print("No batches found in database")
            return None
        
        batch_id = latest_batch[0]
        print(f"\n{'='*80}")
        print(f"BATCH ANALYSIS: {batch_id}")
        print(f"{'='*80}")
        print(f"Upload Date: {latest_batch[1]}")
        print(f"Total Records: {latest_batch[2]}, Processed: {latest_batch[3]}")
        print(f"Status: {latest_batch[4]}\n")
        
        # Get voucher data for this batch
        cursor.execute("""
            SELECT 
                v.voucher_id,
                v.voucher_number,
                v.voucher_date,
                v.supplier_name,
                v.gross_total,
                v.net_total,
                v.ocr_confidence,
                f.ocr_output,
                f.file_path
            FROM vouchers_master v
            LEFT JOIN file_tracking f ON v.voucher_id = f.voucher_id
            WHERE v.batch_id = %s
            ORDER BY v.voucher_id
        """, (batch_id,))
        
        vouchers = cursor.fetchall()
        print(f"Total vouchers in batch: {len(vouchers)}\n")
        
        # Analyze each voucher
        ocr_score = 0  # How good OCR extraction was
        parsing_issues = []
        
        for i, voucher in enumerate(vouchers):
            voucher_id, voucher_num, voucher_date, supplier_name, gross_total, net_total, ocr_conf, ocr_output, file_path = voucher
            
            print(f"\n{'─'*80}")
            print(f"VOUCHER {i+1}/{len(vouchers)}: {voucher_id}")
            print(f"{'─'*80}")
            
            # Analyze OCR output
            if ocr_output:
                ocr_lines = ocr_output.strip().split('\n')
                print(f"\nOCR EXTRACTION:")
                print(f"  Confidence Score: {ocr_conf}%")
                print(f"  Extracted Lines: {len(ocr_lines)}")
                print(f"  First 5 lines of OCR:")
                for line in ocr_lines[:5]:
                    if line.strip():
                        print(f"    • {line[:70]}")
            
            # Check parsed fields
            print(f"\nPARSED FIELDS:")
            print(f"  Voucher Number: {voucher_num or 'MISSING'}")
            print(f"  Voucher Date: {voucher_date or 'MISSING'}")
            print(f"  Supplier Name: {supplier_name or 'MISSING'}")
            print(f"  Gross Total: {gross_total or 'MISSING'}")
            print(f"  Net Total: {net_total or 'MISSING'}")
            
            # Determine parsing issues
            issues = []
            if not voucher_num:
                issues.append("voucher_number")
            if not voucher_date:
                issues.append("voucher_date")
            if not supplier_name:
                issues.append("supplier_name")
            if not gross_total:
                issues.append("gross_total")
            if not net_total:
                issues.append("net_total")
            
            if issues:
                parsing_issues.append({
                    'voucher_id': voucher_id,
                    'ocr_confidence': ocr_conf,
                    'missing_fields': issues,
                    'ocr_output_sample': ocr_output[:500] if ocr_output else None
                })
                print(f"\n  ⚠️  PARSING ISSUES: Missing {', '.join(issues)}")
            else:
                print(f"\n  ✓ All fields extracted successfully")
        
        # Summary
        print(f"\n\n{'='*80}")
        print(f"BATCH SUMMARY")
        print(f"{'='*80}")
        print(f"Total Vouchers: {len(vouchers)}")
        print(f"Successfully Parsed: {len(vouchers) - len(parsing_issues)}")
        print(f"With Issues: {len(parsing_issues)}")
        print(f"Success Rate: {((len(vouchers) - len(parsing_issues)) / len(vouchers) * 100) if vouchers else 0:.1f}%\n")
        
        if parsing_issues:
            print(f"FIELDS WITH PARSING FAILURES:\n")
            field_failures = {}
            for issue in parsing_issues:
                for field in issue['missing_fields']:
                    field_failures[field] = field_failures.get(field, 0) + 1
            
            for field, count in sorted(field_failures.items(), key=lambda x: -x[1]):
                print(f"  • {field}: {count} missing ({count/len(parsing_issues)*100:.1f}%)")
            
            print(f"\n\nDETAILED PARSING FAILURES:\n")
            for issue in parsing_issues[:10]:  # Show first 10
                print(f"Voucher {issue['voucher_id']} (OCR: {issue['ocr_confidence']}%)")
                print(f"  Missing: {', '.join(issue['missing_fields'])}")
                if issue['ocr_output_sample']:
                    print(f"  OCR Sample: {issue['ocr_output_sample'][:100]}...")
                print()
        
        cursor.close()
        db.close()
        
        return {
            'batch_id': batch_id,
            'total_vouchers': len(vouchers),
            'parsing_issues': len(parsing_issues),
            'success_rate': ((len(vouchers) - len(parsing_issues)) / len(vouchers) * 100) if vouchers else 0,
            'issue_details': parsing_issues
        }
        
    except Exception as e:
        logger.error(f"Error analyzing batch: {e}")
        print(f"Error: {e}")
        return None

if __name__ == '__main__':
    result = get_batch_data()
    if result:
        print(f"\n\nAnalysis complete. Check details above for parsing issues.")
