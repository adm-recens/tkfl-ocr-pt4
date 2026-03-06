"""
Comprehensive Voucher Analysis - Analyze ALL vouchers to understand patterns
Build a robust system that handles variations automatically
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from psycopg2.extras import RealDictCursor
from collections import Counter, defaultdict
import json
import re
from typing import Dict, List, Tuple

# Database connection
import os
from dotenv import load_dotenv
load_dotenv()


def get_db_connection():
    """Get database connection directly"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        try:
            with open('.env', 'r') as f:
                for line in f:
                    if line.startswith('DATABASE_URL='):
                        database_url = line.strip().split('=', 1)[1].strip().strip('"').strip("'")
                        break
        except:
            pass
    
    if not database_url:
        raise Exception("DATABASE_URL not found")
    
    return psycopg2.connect(database_url)


def analyze_all_vouchers():
    """Analyze all vouchers to find patterns"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get all vouchers with corrections
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
            validation_status
        FROM vouchers_master
        WHERE validation_status = 'VALIDATED'
        ORDER BY id DESC
    """)
    
    vouchers = cur.fetchall()
    conn.close()
    
    return vouchers


def extract_voucher_number_patterns(vouchers):
    """Analyze how voucher numbers appear in OCR text"""
    patterns = defaultdict(list)
    
    for v in vouchers:
        if not v['raw_ocr_text'] or not v['user_voucher']:
            continue
        
        text = v['raw_ocr_text'].lower()
        target = str(v['user_voucher']).lower()
        
        # Find context around the voucher number
        for match in re.finditer(r'.{0,20}' + re.escape(target) + r'.{0,20}', text):
            context = match.group(0)
            patterns[target].append(context)
    
    return patterns


def extract_supplier_patterns(vouchers):
    """Analyze how suppliers appear in OCR text"""
    patterns = defaultdict(list)
    
    for v in vouchers:
        if not v['raw_ocr_text'] or not v['user_supplier']:
            continue
        
        text = v['raw_ocr_text'].lower()
        target = str(v['user_supplier']).lower()
        
        # Find context around supplier name
        for match in re.finditer(r'.{0,25}' + re.escape(target) + r'.{0,25}', text):
            context = match.group(0)
            patterns[target].append(context)
    
    return patterns


def analyze_ocr_errors(vouchers):
    """Analyze common OCR errors"""
    errors = {
        'voucher_number_missed': 0,
        'voucher_number_wrong': 0,
        'date_missed': 0,
        'supplier_missed': 0,
        'total_wrong': 0,
    }
    
    wrong_voucher_examples = []
    wrong_supplier_examples = []
    
    for v in vouchers:
        if not v['parsed_json_original']:
            continue
        
        try:
            parsed = json.loads(v['parsed_json_original']) if isinstance(v['parsed_json_original'], str) else v['parsed_json_original']
            master = parsed.get('master', {})
            
            # Check voucher number
            if v['user_voucher']:
                parsed_vn = master.get('voucher_number')
                if parsed_vn is None:
                    errors['voucher_number_missed'] += 1
                elif str(parsed_vn) != str(v['user_voucher']):
                    errors['voucher_number_wrong'] += 1
                    if len(wrong_voucher_examples) < 10:
                        wrong_voucher_examples.append({
                            'id': v['id'],
                            'expected': v['user_voucher'],
                            'got': parsed_vn,
                            'sample': v['raw_ocr_text'][:200] if v['raw_ocr_text'] else None
                        })
            
            # Check supplier
            if v['user_supplier']:
                parsed_sup = master.get('supplier_name')
                if parsed_sup is None:
                    errors['supplier_missed'] += 1
                    if len(wrong_supplier_examples) < 10:
                        wrong_supplier_examples.append({
                            'id': v['id'],
                            'expected': v['user_supplier'],
                            'sample': v['raw_ocr_text'][:300] if v['raw_ocr_text'] else None
                        })
            
            # Check date
            if v['user_date']:
                if master.get('voucher_date') is None:
                    errors['date_missed'] += 1
            
            # Check totals
            if v['user_gross']:
                parsed_gross = master.get('gross_total')
                if parsed_gross and abs(float(parsed_gross) - float(v['user_gross'])) > 10:
                    errors['total_wrong'] += 1
                    
        except Exception as e:
            continue
    
    return errors, wrong_voucher_examples, wrong_supplier_examples


def find_common_patterns(texts):
    """Find common patterns in OCR text"""
    patterns = Counter()
    
    for text in texts:
        if not text:
            continue
        
        # Look for label patterns
        labels = re.findall(r'\b([a-z]+)[\s:]*\d', text.lower())
        patterns.update(labels)
        
        # Look for field indicators
        field_patterns = [
            r'voucher\s*#?\s*\d',
            r'date[\s:]*\d',
            r'supp\s*\w+',
            r'total[\s:]*\d',
        ]
        
        for pattern in field_patterns:
            matches = re.findall(pattern, text.lower())
            for m in matches:
                patterns[m[:20]] += 1
    
    return patterns


def generate_parser_rules(vouchers):
    """Generate parser rules based on analysis"""
    
    # Analyze voucher number patterns
    vn_contexts = []
    for v in vouchers:
        if not v['raw_ocr_text'] or not v['user_voucher']:
            continue
        
        text = v['raw_ocr_text']
        target = str(v['user_voucher'])
        
        # Find the line containing voucher number
        for line in text.split('\n'):
            if target in line:
                vn_contexts.append(line.strip())
                break
    
    # Analyze supplier patterns
    sup_contexts = []
    for v in vouchers:
        if not v['raw_ocr_text'] or not v['user_supplier']:
            continue
        
        text = v['raw_ocr_text']
        target = str(v['user_supplier'])
        
        for line in text.split('\n'):
            if target in line:
                sup_contexts.append(line.strip())
                break
    
    return vn_contexts, sup_contexts


def main():
    """Main analysis"""
    
    print("="*100)
    print("COMPREHENSIVE VOUCHER ANALYSIS")
    print("Analyzing ALL vouchers to build robust patterns")
    print("="*100)
    
    try:
        print("\nFetching all validated vouchers...")
        vouchers = analyze_all_vouchers()
        
        print(f"[OK] Found {len(vouchers)} validated vouchers")
        
        # Analyze OCR errors
        print("\n" + "="*100)
        print("1. ERROR ANALYSIS")
        print("="*100)
        
        errors, wrong_vn_examples, wrong_sup_examples = analyze_ocr_errors(vouchers)
        
        print(f"\nParsing Error Breakdown:")
        for error_type, count in errors.items():
            percentage = (count / len(vouchers)) * 100 if vouchers else 0
            print(f"  {error_type:30s}: {count:3d} ({percentage:5.1f}%)")
        
        # Show examples of wrong voucher numbers
        if wrong_vn_examples:
            print(f"\n[ERROR] Wrong Voucher Number Examples (showing first {len(wrong_vn_examples)}):")
            for ex in wrong_vn_examples[:5]:
                print(f"\n  Voucher {ex['id']}:")
                print(f"    Expected: {ex['expected']}")
                print(f"    Got:      {ex['got']}")
                print(f"    Sample:   {ex['sample'][:80]}..." if ex['sample'] else "    No sample")
        
        # Show examples of missed suppliers
        if wrong_sup_examples:
            print(f"\n[ERROR] Missed Supplier Examples (showing first {len(wrong_sup_examples)}):")
            for ex in wrong_sup_examples[:5]:
                print(f"\n  Voucher {ex['id']}:")
                print(f"    Expected: {ex['expected']}")
                print(f"    Sample:   {ex['sample'][:100]}..." if ex['sample'] else "    No sample")
        
        # Find common patterns
        print("\n" + "="*100)
        print("2. PATTERN ANALYSIS")
        print("="*100)
        
        all_texts = [v['raw_ocr_text'] for v in vouchers if v['raw_ocr_text']]
        common_patterns = find_common_patterns(all_texts)
        
        print(f"\nMost Common OCR Patterns:")
        for pattern, count in common_patterns.most_common(20):
            print(f"  '{pattern}': {count} occurrences")
        
        # Generate rules
        print("\n" + "="*100)
        print("3. GENERATED INSIGHTS")
        print("="*100)
        
        vn_contexts, sup_contexts = generate_parser_rules(vouchers)
        
        print(f"\n[OK] Analyzed {len(vn_contexts)} voucher number contexts")
        print(f"[OK] Analyzed {len(sup_contexts)} supplier name contexts")
        
        # Show sample contexts
        if vn_contexts:
            print(f"\n[DATA] Sample Voucher Number Contexts:")
            for i, ctx in enumerate(vn_contexts[:10], 1):
                print(f"  {i}. {ctx[:60]}...")
        
        if sup_contexts:
            print(f"\n[DATA] Sample Supplier Contexts:")
            for i, ctx in enumerate(sup_contexts[:10], 1):
                print(f"  {i}. {ctx[:60]}...")
        
        # Recommendations
        print("\n" + "="*100)
        print("4. RECOMMENDATIONS")
        print("="*100)
        
        print(f"\nBased on analysis of {len(vouchers)} vouchers:")
        
        if errors['voucher_number_wrong'] > len(vouchers) * 0.3:
            print(f"\n[WARN]  VOUCHER NUMBERS:")
            print(f"   {errors['voucher_number_wrong']} vouchers have WRONG numbers")
            print(f"   → Need to filter out date patterns (2026) being picked as voucher numbers")
            print(f"   → Need stricter validation (2-4 digits only, not years)")
        
        if errors['supplier_missed'] > len(vouchers) * 0.5:
            print(f"\n[WARN]  SUPPLIER NAMES:")
            print(f"   {errors['supplier_missed']} vouchers have MISSING suppliers")
            print(f"   → OCR varies: 'Supp Name', 'SuppNane', 'SuppNare', 'Name'")
            print(f"   → Need flexible pattern matching")
        
        if errors['total_wrong'] > len(vouchers) * 0.3:
            print(f"\n[WARN]  TOTALS:")
            print(f"   {errors['total_wrong']} vouchers have WRONG totals")
            print(f"   → Parser picking first item instead of Total line")
            print(f"   → Need to prioritize 'Total X YYYY.YY' pattern")
        
        print(f"\n[TIP] SOLUTION:")
        print(f"   Instead of hardcoded patterns, build ADAPTIVE parser that:")
        print(f"   1. Learns from corrections (ML approach)")
        print(f"   2. Uses multiple strategies with confidence scoring")
        print(f"   3. Validates extracted values (e.g., voucher # can't be year)")
        print(f"   4. Falls back to alternative patterns when primary fails")
        
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
