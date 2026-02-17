#!/usr/bin/env python3
"""
Analyze latest batch OCR vs Parsing discrepancies.
Compare what OCR extracted vs what was parsed into fields.
"""

import sys
import os
import json
import re
from pathlib import Path
from PIL import Image
import pytesseract

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from ocr_service import OCRService
from parser import Parser

def analyze_batch():
    """Analyze the latest batch"""
    uploads_dir = Path('uploads')
    
    # Get latest batch (most recent files)
    all_files = list(uploads_dir.glob('*.jpg')) + list(uploads_dir.glob('*.jpeg'))
    all_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not all_files:
        print("No uploaded files found")
        return
    
    # Group by batch ID (first part of filename)
    batches = {}
    for file in all_files:
        batch_id = file.name.split('_')[0]
        if batch_id not in batches:
            batches[batch_id] = []
        batches[batch_id].append(file)
    
    # Analyze latest batch
    latest_batch_id = list(batches.keys())[0]
    batch_files = batches[latest_batch_id]
    
    # Get only original images (not cropped)
    original_files = [f for f in batch_files if '_cropped_' not in f.name and 'preview_' not in f.name]
    original_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    print(f"\n{'='*80}")
    print(f"BATCH ANALYSIS: {latest_batch_id}")
    print(f"{'='*80}")
    print(f"Total original images: {len(original_files)}")
    print(f"Analyzing OCR extraction vs field parsing...\n")
    
    ocr_service = OCRService()
    parser = Parser()
    
    results = {
        'batch_id': latest_batch_id,
        'total_images': len(original_files),
        'analysis': []
    }
    
    ocr_quality_count = 0
    parsing_success_count = 0
    
    for i, img_file in enumerate(original_files[:10], 1):  # Analyze first 10
        print(f"\n[{i}/{min(10, len(original_files))}] Processing: {img_file.name}")
        print(f"{'─'*80}")
        
        try:
            # Extract OCR
            ocr_result = ocr_service.extract_text(str(img_file))
            ocr_text = ocr_result.get('text', '')
            ocr_confidence = ocr_result.get('confidence', 0)
            
            print(f"OCR Confidence: {ocr_confidence}%")
            print(f"OCR Text Length: {len(ocr_text)} characters")
            
            if ocr_confidence >= 60:
                ocr_quality_count += 1
                print(f"  ✓ Good OCR quality")
            else:
                print(f"  ✗ Poor OCR quality")
            
            # Show first 200 chars of OCR output
            ocr_preview = ocr_text[:200].replace('\n', ' ')
            print(f"OCR Preview: {ocr_preview}...")
            
            # Try to parse
            parse_result = parser.parse(ocr_text)
            
            # Extract key fields
            voucher_number = parse_result.get('voucher_number')
            voucher_date = parse_result.get('voucher_date')
            supplier_name = parse_result.get('supplier_name')
            gross_total = parse_result.get('gross_total')
            net_total = parse_result.get('net_total')
            
            print(f"\nPARSED FIELDS:")
            print(f"  Voucher Number: {voucher_number or '❌ MISSING'}")
            print(f"  Voucher Date: {voucher_date or '❌ MISSING'}")
            print(f"  Supplier Name: {supplier_name or '❌ MISSING'}")
            print(f"  Gross Total: {gross_total or '❌ MISSING'}")
            print(f"  Net Total: {net_total or '❌ MISSING'}")
            
            # Check parsing success
            missing_fields = []
            if not voucher_number: missing_fields.append('voucher_number')
            if not voucher_date: missing_fields.append('voucher_date')
            if not supplier_name: missing_fields.append('supplier_name')
            if not gross_total: missing_fields.append('gross_total')
            if not net_total: missing_fields.append('net_total')
            
            if not missing_fields:
                parsing_success_count += 1
                print(f"\n  ✓ All fields extracted successfully")
            else:
                print(f"\n  ⚠️  Missing: {', '.join(missing_fields)}")
            
            results['analysis'].append({
                'image': img_file.name,
                'ocr_confidence': ocr_confidence,
                'ocr_length': len(ocr_text),
                'parsed_fields': {
                    'voucher_number': voucher_number,
                    'voucher_date': voucher_date,
                    'supplier_name': supplier_name,
                    'gross_total': gross_total,
                    'net_total': net_total
                },
                'missing_fields': missing_fields
            })
            
        except Exception as e:
            print(f"  ✗ Error processing: {e}")
            results['analysis'].append({
                'image': img_file.name,
                'error': str(e)
            })
    
    # Summary
    print(f"\n\n{'='*80}")
    print(f"ANALYSIS SUMMARY")
    print(f"{'='*80}")
    print(f"Images Analyzed: {min(10, len(original_files))}")
    print(f"Good OCR Quality (≥60%): {ocr_quality_count}/{min(10, len(original_files))}")
    print(f"Successful Parsing: {parsing_success_count}/{min(10, len(original_files))}")
    
    gap = ocr_quality_count - parsing_success_count
    if gap > 0:
        print(f"\n⚠️  GAP DETECTED: {gap} image(s) with good OCR but failed parsing")
        print(f"   This suggests parser improvements are needed for:\n")
        
        # Analyze what fields are failing
        field_failures = {}
        for analysis in results['analysis']:
            if 'missing_fields' in analysis:
                for field in analysis['missing_fields']:
                    if field not in field_failures:
                        field_failures[field] = []
                    field_failures[field].append(analysis['image'])
        
        for field, images in sorted(field_failures.items(), key=lambda x: -len(x[1])):
            print(f"   • {field}: Missing in {len(images)} image(s)")
            for img in images[:3]:
                print(f"     - {img}")
    else:
        print(f"\n✓ No parsing gap detected - all images with good OCR parsed successfully")
    
    # Save detailed results
    with open('batch_analysis_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDetailed results saved to: batch_analysis_results.json")
    
    return results

if __name__ == '__main__':
    try:
        analyze_batch()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
