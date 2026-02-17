"""
Compare Standard vs Robust OCR Processing
Run this to see the improvement on your vouchers
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.ocr_service import extract_text as standard_ocr
from backend.parser import parse_receipt_text as standard_parser
from backend.adaptive_ocr_service import extract_text_robust
from backend.robust_parser import parse_receipt_text_robust
from backend.image_quality import analyze_image_quality
from backend.text_correction import apply_text_corrections


def format_field(value, max_length=40):
    """Format field value for display"""
    if value is None:
        return "❌ NOT FOUND"
    text = str(value)
    if len(text) > max_length:
        text = text[:max_length-3] + "..."
    return f"✓ {text}"


def compare_processing(image_path):
    """Compare standard vs robust processing"""
    
    print("\n" + "="*80)
    print(f"OCR COMPARISON TEST")
    print(f"Image: {os.path.basename(image_path)}")
    print("="*80)
    
    # Analyze image quality
    print("\n📊 IMAGE QUALITY ANALYSIS:")
    print("-" * 40)
    try:
        quality = analyze_image_quality(image_path)
        print(f"  Quality Score: {quality.quality_score():.1f}/100")
        print(f"  Brightness: {quality.brightness:.1f}")
        print(f"  Contrast: {quality.contrast:.1f}")
        print(f"  Sharpness: {quality.sharpness:.1f}")
        print(f"  Noise: {quality.noise_level:.1f}")
        print(f"  Skew: {quality.skew_angle:.2f}°")
        
        if quality.quality_score() >= 70:
            print(f"  Status: ✅ Good quality")
        elif quality.quality_score() >= 40:
            print(f"  Status: ⚠️  Medium quality")
        else:
            print(f"  Status: ❌ Poor quality - robust mode recommended")
    except Exception as e:
        print(f"  Error analyzing quality: {e}")
    
    # STANDARD PROCESSING
    print("\n" + "="*80)
    print("🔍 STANDARD PROCESSING (Current System)")
    print("="*80)
    
    try:
        print("\n1. Running OCR with 'optimal' mode...")
        standard_result = standard_ocr(image_path, method='optimal')
        
        print(f"\n   OCR Confidence: {standard_result.get('confidence', 0):.1f}%")
        print(f"   Processing Time: {standard_result.get('processing_time_ms', 0)}ms")
        
        # Apply text corrections
        corrected_text = apply_text_corrections(standard_result.get('text', ''))
        
        print(f"\n   Raw Text (first 300 chars):")
        print(f"   {corrected_text[:300]}...")
        
        print("\n2. Parsing extracted text...")
        standard_parsed = standard_parser(corrected_text)
        
        print("\n   📋 EXTRACTED FIELDS:")
        master = standard_parsed.get('master', {})
        print(f"   Voucher Number: {format_field(master.get('voucher_number'))}")
        print(f"   Date:           {format_field(master.get('voucher_date'))}")
        print(f"   Supplier:       {format_field(master.get('supplier_name'))}")
        print(f"   Gross Total:    {format_field(master.get('gross_total'))}")
        print(f"   Net Total:      {format_field(master.get('net_total'))}")
        print(f"   Items Count:    {len(standard_parsed.get('items', []))}")
        print(f"   Deductions:     {len(standard_parsed.get('deductions', []))}")
        
        # Calculate fields found
        fields_found = sum(1 for v in master.values() if v is not None)
        print(f"\n   ✅ Fields Found: {fields_found}/6")
        
    except Exception as e:
        print(f"\n   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    # ROBUST PROCESSING
    print("\n" + "="*80)
    print("🚀 ROBUST PROCESSING (New Adaptive System)")
    print("="*80)
    
    try:
        print("\n1. Running adaptive multi-pass OCR...")
        robust_result = extract_text_robust(image_path)
        
        print(f"\n   Final Confidence: {robust_result.get('confidence', 0):.1f}%")
        print(f"   Merge Strategy: {robust_result.get('merge_strategy', 'unknown')}")
        print(f"   OCR Attempts: {len(robust_result.get('attempts', []))}")
        
        # Show each attempt
        if robust_result.get('attempts'):
            print(f"\n   Attempt Details:")
            for i, attempt in enumerate(robust_result['attempts'], 1):
                print(f"     {i}. {attempt.get('mode', 'unknown')}: "
                      f"{attempt.get('confidence', 0):.1f}% "
                      f"({attempt.get('processing_time_ms', 0)}ms)")
        
        # Show field confidence
        field_conf = robust_result.get('field_confidence', {})
        if field_conf:
            print(f"\n   Field Confidence Scores:")
            for field, conf in field_conf.items():
                if field != 'overall':
                    status = "✅" if conf >= 70 else "⚠️" if conf >= 50 else "❌"
                    print(f"     {status} {field}: {conf:.0f}%")
        
        print(f"\n   Raw Text (first 300 chars):")
        print(f"   {robust_result.get('text', '')[:300]}...")
        
        print("\n2. Parsing with robust parser...")
        robust_parsed = parse_receipt_text_robust(
            robust_result.get('text', ''),
            field_confidence=field_conf
        )
        
        print("\n   📋 EXTRACTED FIELDS:")
        master = robust_parsed.get('master', {})
        conf = robust_parsed.get('confidence', {})
        
        # Show fields with confidence
        fields = [
            ('voucher_number', 'Voucher Number'),
            ('voucher_date', 'Date'),
            ('supplier_name', 'Supplier'),
            ('gross_total', 'Gross Total'),
            ('net_total', 'Net Total')
        ]
        
        for field_key, field_name in fields:
            value = master.get(field_key)
            field_conf = conf.get(field_key, 0)
            status = "✅" if field_conf >= 70 else "⚠️" if field_conf >= 50 else "❌"
            print(f"   {status} {field_name:15s}: {format_field(value)} "
                  f"({field_conf:.0f}% confidence)")
        
        print(f"   ✅ Items Count:    {len(robust_parsed.get('items', []))}")
        print(f"   ✅ Deductions:     {len(robust_parsed.get('deductions', []))}")
        
        # Calculate fields found
        fields_found = sum(1 for v in master.values() if v is not None)
        overall_conf = conf.get('overall', 0)
        print(f"\n   ✅ Fields Found: {fields_found}/6")
        print(f"   📊 Overall Confidence: {overall_conf:.1f}%")
        
        # Action recommendation
        print(f"\n   🎯 RECOMMENDATION:")
        if overall_conf >= 80:
            print(f"      ✅ HIGH CONFIDENCE - Can auto-process")
        elif overall_conf >= 50:
            print(f"      ⚠️  MEDIUM CONFIDENCE - Flag for review")
            low_conf_fields = [k for k, v in conf.items() 
                             if v < 70 and k != 'overall']
            if low_conf_fields:
                print(f"      📍 Review these fields: {', '.join(low_conf_fields)}")
        else:
            print(f"      ❌ LOW CONFIDENCE - Recommend retaking photo")
        
    except Exception as e:
        print(f"\n   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("COMPARISON COMPLETE")
    print("="*80)
    print("\n💡 TIP: Check ROBUST_OCR_GUIDE.md for integration instructions")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python compare_ocr.py <image_path>")
        print("\nExample:")
        print("  python compare_ocr.py uploads/voucher_001.jpg")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    if not os.path.exists(image_path):
        print(f"❌ Error: File not found: {image_path}")
        sys.exit(1)
    
    compare_processing(image_path)
