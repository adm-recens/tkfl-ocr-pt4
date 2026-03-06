"""
Analyze Real Voucher Data - Compare OCR vs User Corrections
Uses actual database data to identify parsing issues and test improvements
"""

import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.text_correction import apply_text_corrections

# Import parsers directly
from backend.parser import parse_receipt_text as original_parser
from backend.robust_parser import parse_receipt_text_robust as robust_parser
from backend.enhanced_parser import parse_receipt_text_enhanced as enhanced_parser
from backend.tkfl_parser import parse_receipt_text_tkfl as tkfl_parser

# Database connection from environment
import os
from dotenv import load_dotenv
load_dotenv()


def get_db_connection():
    """Get database connection directly"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        # Try to read from .env file
        try:
            with open('.env', 'r') as f:
                for line in f:
                    if line.startswith('DATABASE_URL='):
                        database_url = line.strip().split('=', 1)[1].strip().strip('"').strip("'")
                        break
        except:
            pass
    
    if not database_url:
        raise Exception("DATABASE_URL not found. Please set it in .env file or environment")
    
    return psycopg2.connect(database_url)


def get_validation_stats():
    """Get statistics on validated vouchers"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Count total vouchers
    cur.execute("SELECT COUNT(*) as total FROM vouchers_master")
    total = cur.fetchone()['total']
    
    # Count validated vouchers (have user corrections)
    cur.execute("""
        SELECT COUNT(*) as validated 
        FROM vouchers_master 
        WHERE validation_status = 'VALIDATED' 
        AND parsed_json_original IS NOT NULL
    """)
    validated = cur.fetchone()['validated']
    
    # Get sample of vouchers with corrections
    cur.execute("""
        SELECT 
            id,
            file_name,
            raw_ocr_text,
            parsed_json_original,
            parsed_json,
            supplier_name as user_supplier,
            voucher_date as user_date,
            voucher_number as user_voucher,
            gross_total as user_gross,
            net_total as user_net,
            created_at
        FROM vouchers_master
        WHERE validation_status = 'VALIDATED' 
        AND parsed_json_original IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 20
    """)
    
    vouchers = cur.fetchall()
    conn.close()
    
    return {
        'total_vouchers': total,
        'validated_vouchers': validated,
        'sample_vouchers': vouchers
    }


def test_new_parser_on_voucher(voucher):
    """Test all parsers on a real voucher"""
    
    raw_text = voucher['raw_ocr_text'] or ''
    corrected_text = apply_text_corrections(raw_text)
    
    # Parse with all parsers
    try:
        original_result = original_parser(corrected_text)
    except Exception as e:
        original_result = {'master': {}}
        print(f"    Original parser error: {e}")
    
    try:
        robust_result = robust_parser(corrected_text)
    except Exception as e:
        robust_result = {'master': {}}
        print(f"    Robust parser error: {e}")
    
    try:
        enhanced_result = enhanced_parser(corrected_text)
    except Exception as e:
        enhanced_result = {'master': {}, 'confidence': {}}
        print(f"    Enhanced parser error: {e}")
    
    try:
        tkfl_result = tkfl_parser(corrected_text)
    except Exception as e:
        tkfl_result = {'master': {}, 'confidence': {}}
        print(f"    TKFL parser error: {e}")
    
    # Get user-corrected data
    user_data = {
        'voucher_number': voucher['user_voucher'],
        'voucher_date': str(voucher['user_date']) if voucher['user_date'] else None,
        'supplier_name': voucher['user_supplier'],
        'gross_total': float(voucher['user_gross']) if voucher['user_gross'] else None,
        'net_total': float(voucher['user_net']) if voucher['user_net'] else None,
    }
    
    return {
        'voucher_id': voucher['id'],
        'file_name': voucher['file_name'],
        'user_data': user_data,
        'original_parser': original_result.get('master', {}),
        'robust_parser': robust_result.get('master', {}),
        'enhanced_parser': enhanced_result.get('master', {}),
        'tkfl_parser': tkfl_result.get('master', {}),
        'enhanced_confidence': enhanced_result.get('confidence', {}),
        'tkfl_confidence': tkfl_result.get('confidence', {}),
        'raw_text_sample': corrected_text[:400] if corrected_text else ''
    }


def calculate_field_match(parser_val, user_val):
    """Check if parser value matches user value"""
    if parser_val is None and user_val is None:
        return True
    if parser_val is None or user_val is None:
        return False
    
    # String comparison
    if isinstance(parser_val, str) and isinstance(user_val, str):
        return parser_val.strip().lower() == user_val.strip().lower()
    
    # Numeric comparison (allow small differences)
    if isinstance(parser_val, (int, float)) and isinstance(user_val, (int, float)):
        return abs(parser_val - user_val) < 0.01
    
    # Direct comparison
    return str(parser_val).strip() == str(user_val).strip()


def truncate_string(s, length=23):
    """Truncate string for display"""
    if s is None:
        return "N/A"
    s = str(s)
    if len(s) > length:
        return s[:length-3] + "..."
    return s


def display_voucher_comparison(comp, index):
    """Display comparison for a single voucher"""
    
    print(f"\n{'='*100}")
    print(f"Voucher #{index} (ID: {comp['voucher_id']}) - {comp['file_name']}")
    print(f"{'='*100}")
    
    print(f"\nRaw OCR Text (first 250 chars):")
    print("-" * 80)
    sample = comp['raw_text_sample'][:250] if comp['raw_text_sample'] else "[No text]"
    print(sample)
    if len(comp['raw_text_sample'] or '') > 250:
        print("...")
    
    print(f"\n{'Field':<15s} | {'User':<18s} | {'Original':<18s} | {'Enhanced':<18s} | {'TKFL (NEW)':<18s}")
    print("-" * 105)
    
    fields = [
        ('voucher_number', 'Voucher #'),
        ('voucher_date', 'Date'),
        ('supplier_name', 'Supplier'),
        ('gross_total', 'Gross Total'),
        ('net_total', 'Net Total')
    ]
    
    total_original_correct = 0
    total_enhanced_correct = 0
    total_tkfl_correct = 0
    tkfl_improvements = []
    
    for field_key, field_name in fields:
        user_val = comp['user_data'].get(field_key)
        orig_val = comp['original_parser'].get(field_key)
        enhanced_val = comp['enhanced_parser'].get(field_key)
        tkfl_val = comp['tkfl_parser'].get(field_key)
        
        orig_match = calculate_field_match(orig_val, user_val)
        enhanced_match = calculate_field_match(enhanced_val, user_val)
        tkfl_match = calculate_field_match(tkfl_val, user_val)
        
        user_str = truncate_string(user_val, 16)
        
        if orig_match:
            total_original_correct += 1
            orig_str = f"OK {truncate_string(orig_val, 14)}"
        else:
            orig_str = f"XX {truncate_string(orig_val or 'MISSING', 14)}"
        
        if enhanced_match:
            total_enhanced_correct += 1
            enhanced_str = f"OK {truncate_string(enhanced_val, 14)}"
        else:
            enhanced_str = f"XX {truncate_string(enhanced_val or 'MISSING', 14)}"
        
        if tkfl_match:
            total_tkfl_correct += 1
            tkfl_str = f"OK {truncate_string(tkfl_val, 14)}"
        else:
            if tkfl_val is not None and not orig_match:
                # TKFL found something but wrong
                tkfl_str = f"XX {truncate_string(tkfl_val, 14)}"
            elif tkfl_val is not None and orig_val is None:
                # TKFL found what original missed
                tkfl_str = f"** {truncate_string(tkfl_val, 14)}"
                tkfl_improvements.append(field_name)
            else:
                tkfl_str = f"XX {truncate_string(tkfl_val or 'MISSING', 14)}"
        
        print(f"{field_name:<15s} | {user_str:<18s} | {orig_str:<18s} | {enhanced_str:<18s} | {tkfl_str:<18s}")
    
    print("-" * 105)
    
    # Summary
    if tkfl_improvements:
        print(f"\n[TKFL WINS] Found what others missed: {', '.join(tkfl_improvements)}")
    
    best = max(total_original_correct, total_enhanced_correct, total_tkfl_correct)
    if total_tkfl_correct == best and best > total_original_correct:
        diff = total_tkfl_correct - total_original_correct
        print(f"[RESULT] TKFL +{diff} field(s) better than original")
    elif total_tkfl_correct > total_original_correct:
        diff = total_tkfl_correct - total_original_correct
        print(f"[RESULT] TKFL +{diff} field(s) better (but not best)")
    elif total_tkfl_correct < total_original_correct:
        diff = total_original_correct - total_tkfl_correct
        print(f"[RESULT] TKFL -{diff} field(s) worse than original")
    else:
        print(f"[RESULT] Same accuracy ({total_original_correct}/5 fields)")
    
    return total_original_correct, total_enhanced_correct, total_tkfl_correct


def main():
    """Main analysis function"""
    
    print("="*100)
    print("REAL DATA ANALYSIS - Testing Parser Against User Corrections")
    print("="*100)
    print("\nThis analyzes your ACTUAL voucher data to measure real improvement")
    print()
    
    try:
        # Get validation stats
        print("Connecting to database...")
        stats = get_validation_stats()
        
        print(f"\nDatabase Stats:")
        print(f"  Total vouchers: {stats['total_vouchers']}")
        print(f"  Validated (with corrections): {stats['validated_vouchers']}")
        
        if stats['validated_vouchers'] == 0:
            print("\n[!] No validated vouchers found!")
            print("   You need to:")
            print("   1. Upload some vouchers through the web UI")
            print("   2. Review them and correct any wrong data")
            print("   3. Save the corrections")
            print("\n   Then run this tool again to see metrics.")
            return
        
        # Test parsers on sample
        sample_size = len(stats['sample_vouchers'])
        print(f"\nAnalyzing last {sample_size} validated vouchers...")
        print()
        
        comparisons = []
        total_orig_correct = 0
        total_enhanced_correct = 0
        total_tkfl_correct = 0
        
        for i, voucher in enumerate(stats['sample_vouchers'], 1):
            try:
                comp = test_new_parser_on_voucher(voucher)
                comparisons.append(comp)
                orig, enhanced, tkfl = display_voucher_comparison(comp, i)
                total_orig_correct += orig
                total_enhanced_correct += enhanced
                total_tkfl_correct += tkfl
            except Exception as e:
                print(f"\n[!] Error analyzing voucher {voucher['id']}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # Overall Summary
        print("\n" + "="*100)
        print("OVERALL SUMMARY")
        print("="*100)
        
        total_fields = len(comparisons) * 5
        
        print(f"\nTotal vouchers analyzed: {len(comparisons)}")
        print(f"Total fields checked: {total_fields}")
        print()
        print(f"Original Parser: {total_orig_correct}/{total_fields} ({total_orig_correct/total_fields*100:.1f}%)")
        print(f"Enhanced Parser: {total_enhanced_correct}/{total_fields} ({total_enhanced_correct/total_fields*100:.1f}%)")
        print(f"TKFL Parser:     {total_tkfl_correct}/{total_fields} ({total_tkfl_correct/total_fields*100:.1f}%)")
        
        # Determine best parser
        if total_tkfl_correct >= total_enhanced_correct and total_tkfl_correct >= total_orig_correct:
            best_parser = 'TKFL'
            best_score = total_tkfl_correct
        elif total_enhanced_correct >= total_orig_correct:
            best_parser = 'Enhanced'
            best_score = total_enhanced_correct
        else:
            best_parser = 'Original'
            best_score = total_orig_correct
        
        print(f"\n** Best Parser: {best_parser} ({best_score}/{total_fields} fields)")
        
        if best_parser == 'TKFL' and total_tkfl_correct > total_orig_correct:
            improvement = total_tkfl_correct - total_orig_correct
            print(f"\n[WIN] TKFL parser is +{improvement} fields better than original ({improvement/total_fields*100:.1f}% improvement)")
            print("\n[RECOMMENDATION] Switch to TKFL parser - it's tuned for your specific voucher format!")
        elif best_parser == 'Enhanced' and total_enhanced_correct > total_orig_correct:
            improvement = total_enhanced_correct - total_orig_correct
            print(f"\n[WIN] Enhanced parser is +{improvement} fields better ({improvement/total_fields*100:.1f}% improvement)")
            print("\n[RECOMMENDATION] Use Enhanced parser")
        elif best_score == total_orig_correct:
            print(f"\n[INFO] Original parser is still best")
            print("\n[RECOMMENDATION] Keep using current parser")
        else:
            print(f"\n[WARNING] TKFL parser needs more work")
        
        # Show improvement potential
        if total_tkfl_correct > total_orig_correct:
            print(f"\n[IMPROVEMENT] Field extraction: +{total_tkfl_correct - total_orig_correct} fields")
        
        # Show average confidence
        if comparisons:
            tkfl_confidences = [c['tkfl_confidence'].get('overall', 0) for c in comparisons if 'tkfl_confidence' in c]
            if tkfl_confidences:
                avg_conf = sum(tkfl_confidences) / len(tkfl_confidences)
                print(f"\n[METRICS] TKFL Parser Average Confidence: {avg_conf:.1f}%")
        
    except Exception as e:
        print(f"\n[!] Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
