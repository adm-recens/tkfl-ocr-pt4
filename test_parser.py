"""
Test parser with real OCR output - Debug tool
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.ocr_service import extract_text
from backend.parser import parse_receipt_text as original_parser
from backend.robust_parser import parse_receipt_text_robust as robust_parser
from backend.enhanced_parser import parse_receipt_text_enhanced as enhanced_parser
from backend.text_correction import apply_text_corrections


def test_parser_on_image(image_path):
    """Test all parsers on a single image"""
    
    print("\n" + "="*80)
    print(f"PARSER COMPARISON TEST")
    print(f"Image: {os.path.basename(image_path)}")
    print("="*80)
    
    # Step 1: Get OCR text
    print("\n1. EXTRACTING OCR TEXT...")
    print("-" * 40)
    ocr_result = extract_text(image_path, method='optimal')
    raw_text = ocr_result.get('text', '')
    corrected_text = apply_text_corrections(raw_text)
    
    print(f"OCR Confidence: {ocr_result.get('confidence', 0):.1f}%")
    print(f"\nRaw OCR Text (first 800 chars):")
    print("-" * 40)
    print(corrected_text[:800])
    if len(corrected_text) > 800:
        print("...")
    
    # Step 2: Test Original Parser
    print("\n" + "="*80)
    print("2. ORIGINAL PARSER RESULTS")
    print("="*80)
    original_result = original_parser(corrected_text)
    display_parser_results("Original", original_result)
    
    # Step 3: Test Robust Parser
    print("\n" + "="*80)
    print("3. ROBUST PARSER RESULTS")
    print("="*80)
    robust_result = robust_parser(corrected_text)
    display_parser_results("Robust", robust_result)
    
    # Step 4: Test Enhanced Parser
    print("\n" + "="*80)
    print("4. ENHANCED PARSER RESULTS (NEW)")
    print("="*80)
    enhanced_result = enhanced_parser(corrected_text)
    display_parser_results("Enhanced", enhanced_result, show_debug=True)
    
    # Step 5: Comparison
    print("\n" + "="*80)
    print("5. FIELD EXTRACTION COMPARISON")
    print("="*80)
    compare_fields(original_result, robust_result, enhanced_result)


def display_parser_results(name, result, show_debug=False):
    """Display parser results nicely"""
    
    master = result.get('master', {})
    
    print(f"\n📋 Master Fields:")
    print("-" * 60)
    
    fields = [
        ('voucher_number', 'Voucher Number'),
        ('voucher_date', 'Date'),
        ('supplier_name', 'Supplier Name'),
        ('gross_total', 'Gross Total'),
        ('net_total', 'Net Total'),
    ]
    
    for field_key, field_name in fields:
        value = master.get(field_key)
        if value is not None:
            print(f"  ✅ {field_name:20s}: {value}")
        else:
            print(f"  ❌ {field_name:20s}: NOT FOUND")
    
    print(f"\n📦 Items: {len(result.get('items', []))}")
    print(f"💰 Deductions: {len(result.get('deductions', []))}")
    
    if 'confidence' in result:
        conf = result['confidence']
        if isinstance(conf, dict):
            overall = conf.get('overall', 0)
            print(f"\n📊 Overall Confidence: {overall:.1f}%")
    
    if show_debug and 'debug' in result:
        print(f"\n🐛 Debug Info:")
        for msg in result['debug'][:10]:  # Show first 10 messages
            print(f"    {msg}")


def compare_fields(original, robust, enhanced):
    """Compare field extraction across parsers"""
    
    fields = ['voucher_number', 'voucher_date', 'supplier_name', 'gross_total', 'net_total']
    
    print(f"\n{'Field':<20s} {'Original':<25s} {'Robust':<25s} {'Enhanced (NEW)':<25s}")
    print("-" * 95)
    
    for field in fields:
        orig_val = original.get('master', {}).get(field)
        robust_val = robust.get('master', {}).get(field)
        enhanced_val = enhanced.get('master', {}).get(field)
        
        orig_str = str(orig_val)[:23] if orig_val else "❌"
        robust_str = str(robust_val)[:23] if robust_val else "❌"
        enhanced_str = str(enhanced_val)[:23] if enhanced_val else "❌"
        
        # Mark if enhanced found something others didn't
        if enhanced_val and not orig_val and not robust_val:
            enhanced_str = f"⭐ {enhanced_str}"
        
        print(f"{field:<20s} {orig_str:<25s} {robust_str:<25s} {enhanced_str:<25s}")
    
    # Count successful extractions
    orig_count = sum(1 for f in fields if original.get('master', {}).get(f))
    robust_count = sum(1 for f in fields if robust.get('master', {}).get(f))
    enhanced_count = sum(1 for f in fields if enhanced.get('master', {}).get(f))
    
    print("\n" + "-" * 95)
    print(f"{'Success Rate':<20s} {orig_count}/{len(fields)} fields        "
          f"{robust_count}/{len(fields)} fields        "
          f"{enhanced_count}/{len(fields)} fields")
    
    print("\n💡 Legend:")
    print("   ❌ = Not found")
    print("   ⭐ = Enhanced parser found what others missed")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_parser.py <image_path>")
        print("\nExample:")
        print("  python test_parser.py uploads/voucher_001.jpg")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    if not os.path.exists(image_path):
        print(f"❌ Error: File not found: {image_path}")
        sys.exit(1)
    
    test_parser_on_image(image_path)
