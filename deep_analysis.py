"""
Deep Analysis - Where exactly do we fail? OCR or Parsing?
Comprehensive root cause analysis
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from psycopg2.extras import RealDictCursor
import json
import re
from collections import defaultdict, Counter
from typing import Dict, List, Tuple
import difflib

# Database
import os
from dotenv import load_dotenv
load_dotenv()


def get_db_connection():
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
    return psycopg2.connect(database_url)


def analyze_failure_points():
    """Analyze where exactly failures occur"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get ALL vouchers
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


def classify_failure(voucher) -> Dict:
    """Classify exactly where the failure occurs"""
    
    if not voucher['parsed_json_original']:
        return {'type': 'NO_PARSE_ATTEMPT', 'details': 'No parsed data saved'}
    
    try:
        parsed = json.loads(voucher['parsed_json_original']) if isinstance(voucher['parsed_json_original'], str) else voucher['parsed_json_original']
        master = parsed.get('master', {})
    except:
        return {'type': 'PARSE_ERROR', 'details': 'Failed to parse JSON'}
    
    failures = []
    
    # Check each field
    if voucher['user_voucher']:
        parsed_vn = master.get('voucher_number')
        if parsed_vn is None:
            # Check if it appears in raw OCR
            if voucher['raw_ocr_text'] and str(voucher['user_voucher']) in voucher['raw_ocr_text']:
                failures.append({
                    'field': 'voucher_number',
                    'type': 'PARSING_FAILURE',
                    'reason': 'Present in OCR but parser missed it',
                    'expected': voucher['user_voucher'],
                    'ocr_sample': find_in_ocr(voucher['raw_ocr_text'], str(voucher['user_voucher']))
                })
            else:
                failures.append({
                    'field': 'voucher_number',
                    'type': 'OCR_FAILURE',
                    'reason': 'Not present in OCR text at all',
                    'expected': voucher['user_voucher'],
                    'ocr_sample': voucher['raw_ocr_text'][:200] if voucher['raw_ocr_text'] else None
                })
        elif str(parsed_vn) != str(voucher['user_voucher']):
            failures.append({
                'field': 'voucher_number',
                'type': 'WRONG_EXTRACTION',
                'reason': f'Parser got wrong value',
                'expected': voucher['user_voucher'],
                'got': parsed_vn,
                'ocr_sample': find_in_ocr(voucher['raw_ocr_text'], str(voucher['user_voucher']))
            })
    
    if voucher['user_supplier']:
        parsed_sup = master.get('supplier_name')
        if parsed_sup is None:
            if voucher['raw_ocr_text'] and str(voucher['user_supplier']).lower() in voucher['raw_ocr_text'].lower():
                failures.append({
                    'field': 'supplier_name',
                    'type': 'PARSING_FAILURE',
                    'reason': 'Present in OCR but parser missed it',
                    'expected': voucher['user_supplier'],
                    'ocr_sample': find_in_ocr(voucher['raw_ocr_text'], voucher['user_supplier'])
                })
            else:
                failures.append({
                    'field': 'supplier_name',
                    'type': 'OCR_FAILURE',
                    'reason': 'Supplier name not in OCR or heavily garbled',
                    'expected': voucher['user_supplier'],
                    'ocr_sample': voucher['raw_ocr_text'][:300] if voucher['raw_ocr_text'] else None
                })
    
    if voucher['user_date']:
        if master.get('voucher_date') is None:
            failures.append({
                'field': 'voucher_date',
                'type': 'PARSING_FAILURE',
                'reason': 'Date not extracted'
            })
    
    if voucher['user_gross']:
        parsed_gross = master.get('gross_total')
        if parsed_gross is None:
            failures.append({
                'field': 'gross_total',
                'type': 'PARSING_FAILURE',
                'reason': 'Total not extracted'
            })
        elif abs(float(parsed_gross) - float(voucher['user_gross'])) > 10:
            failures.append({
                'field': 'gross_total',
                'type': 'WRONG_EXTRACTION',
                'reason': f'Wrong total extracted',
                'expected': voucher['user_gross'],
                'got': parsed_gross
            })
    
    return {
        'voucher_id': voucher['id'],
        'filename': voucher['file_name'],
        'failures': failures,
        'total_failures': len(failures)
    }


def find_in_ocr(ocr_text: str, target: str) -> str:
    """Find context around target in OCR text"""
    if not ocr_text or not target:
        return None
    
    idx = ocr_text.lower().find(target.lower())
    if idx == -1:
        return None
    
    start = max(0, idx - 50)
    end = min(len(ocr_text), idx + len(target) + 50)
    return ocr_text[start:end]


def analyze_ocr_patterns(vouchers):
    """Analyze common OCR patterns and their quality"""
    
    patterns = {
        'voucher_number_formats': Counter(),
        'date_formats': Counter(),
        'supplier_indicators': Counter(),
        'total_formats': Counter(),
        'garbled_patterns': Counter(),
    }
    
    for v in vouchers:
        if not v['raw_ocr_text']:
            continue
        
        text = v['raw_ocr_text'].lower()
        
        # Voucher number patterns
        vn_patterns = re.findall(r'(?:voucher|vou|nuaber|nunber|number)[\s#:]*(\d{2,4})', text)
        patterns['voucher_number_formats'].update(vn_patterns)
        
        # Date patterns
        date_patterns = re.findall(r'(?:date|dt)[\s:]*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})', text)
        patterns['date_formats'].update(date_patterns)
        
        # Supplier indicators
        sup_indicators = re.findall(r'(supp[\s\.]*name|name|nane|supplier)', text)
        patterns['supplier_indicators'].update(sup_indicators)
        
        # Total patterns
        total_patterns = re.findall(r'(?:total|tal)[\s]*(\d+)[\s]*(\d{1,5}\.\d{2})', text)
        patterns['total_formats'].update([f"items:{t[0]} amt:{t[1]}" for t in total_patterns])
        
        # Garbled patterns (merged fields)
        garbled = re.findall(r'vouchernumber\d{6,10}', text)
        patterns['garbled_patterns'].update(garbled)
    
    return patterns


def calculate_ocr_quality_score(voucher) -> Dict:
    """Calculate quality score for OCR output"""
    
    if not voucher['raw_ocr_text']:
        return {'score': 0, 'issues': ['No OCR text']}
    
    text = voucher['raw_ocr_text']
    score = 100
    issues = []
    
    # Check for merged fields
    if re.search(r'vouchernumber\d{8,}', text.lower()):
        score -= 20
        issues.append('Merged VoucherDate+VoucherNumber')
    
    # Check for garbled amounts
    garbled_amounts = len(re.findall(r'\d{5,}\.\d{2}', text))
    if garbled_amounts > 0:
        score -= garbled_amounts * 5
        issues.append(f'{garbled_amounts} potentially garbled amounts')
    
    # Check for missing structure
    has_voucher = 'voucher' in text.lower()
    has_date = 'date' in text.lower()
    has_total = 'total' in text.lower()
    
    if not has_voucher:
        score -= 15
        issues.append('Missing "Voucher" keyword')
    if not has_date:
        score -= 15
        issues.append('Missing "Date" keyword')
    if not has_total:
        score -= 10
        issues.append('Missing "Total" keyword')
    
    # Check for OCR confidence indicators
    weird_chars = len(re.findall(r'[^\w\s\.\/\-\(\),]', text))
    weird_ratio = weird_chars / max(len(text), 1)
    if weird_ratio > 0.1:
        score -= int(weird_ratio * 100)
        issues.append(f'High garbage character ratio ({weird_ratio:.1%})')
    
    return {
        'score': max(0, score),
        'issues': issues,
        'has_voucher': has_voucher,
        'has_date': has_date,
        'has_total': has_total
    }


def main():
    """Main deep analysis"""
    
    print("="*100)
    print("DEEP ROOT CAUSE ANALYSIS")
    print("="*100)
    print("\nAnalyzing where failures actually occur...\n")
    
    vouchers = analyze_failure_points()
    print(f"Total validated vouchers: {len(vouchers)}\n")
    
    # Classify all failures
    print("="*100)
    print("1. FAILURE CLASSIFICATION")
    print("="*100)
    
    classified_failures = []
    for v in vouchers:
        classification = classify_failure(v)
        if classification['total_failures'] > 0:
            classified_failures.append(classification)
    
    # Categorize by type
    ocr_failures = []
    parsing_failures = []
    wrong_extraction = []
    
    for cf in classified_failures:
        for failure in cf['failures']:
            if failure['type'] == 'OCR_FAILURE':
                ocr_failures.append({**failure, 'voucher_id': cf['voucher_id']})
            elif failure['type'] == 'PARSING_FAILURE':
                parsing_failures.append({**failure, 'voucher_id': cf['voucher_id']})
            elif failure['type'] == 'WRONG_EXTRACTION':
                wrong_extraction.append({**failure, 'voucher_id': cf['voucher_id']})
    
    print(f"\n[STATS] Failure Breakdown:")
    print(f"  OCR Failures:       {len(ocr_failures)} (data not in OCR)")
    print(f"  Parsing Failures:   {len(parsing_failures)} (in OCR but missed)")
    print(f"  Wrong Extraction:   {len(wrong_extraction)} (wrong value extracted)")
    print(f"  Total Issues:       {len(ocr_failures) + len(parsing_failures) + len(wrong_extraction)}")
    
    # Show examples
    print(f"\n[FAIL] OCR FAILURE Examples (data genuinely missing from OCR):")
    for i, f in enumerate(ocr_failures[:5], 1):
        print(f"\n  {i}. Voucher {f['voucher_id']} - {f['field']}")
        print(f"     Expected: {f['expected']}")
        print(f"     Sample OCR: {f.get('ocr_sample', 'N/A')[:80]}...")
    
    print(f"\n[WARN] PARSING FAILURE Examples (data present but parser missed):")
    for i, f in enumerate(parsing_failures[:5], 1):
        print(f"\n  {i}. Voucher {f['voucher_id']} - {f['field']}")
        print(f"     Expected: {f['expected']}")
        print(f"     Found in OCR: {f.get('ocr_sample', 'N/A')[:80]}...")
    
    print(f"\n[ERROR] WRONG EXTRACTION Examples:")
    for i, f in enumerate(wrong_extraction[:5], 1):
        print(f"\n  {i}. Voucher {f['voucher_id']} - {f['field']}")
        print(f"     Expected: {f['expected']}")
        print(f"     Got: {f.get('got', 'N/A')}")
    
    # OCR Quality Analysis
    print("\n" + "="*100)
    print("2. OCR QUALITY ANALYSIS")
    print("="*100)
    
    quality_scores = []
    low_quality_examples = []
    
    for v in vouchers[:50]:  # Sample first 50
        quality = calculate_ocr_quality_score(v)
        quality_scores.append(quality['score'])
        
        if quality['score'] < 60:
            low_quality_examples.append({
                'id': v['id'],
                'score': quality['score'],
                'issues': quality['issues'],
                'sample': v['raw_ocr_text'][:200] if v['raw_ocr_text'] else None
            })
    
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
    print(f"\n[STATS] OCR Quality Metrics:")
    print(f"  Average Quality Score: {avg_quality:.1f}/100")
    print(f"  Low Quality (<60):     {len(low_quality_examples)} vouchers")
    
    print(f"\n📉 Low Quality OCR Examples:")
    for i, ex in enumerate(low_quality_examples[:5], 1):
        print(f"\n  {i}. Voucher {ex['id']} - Score: {ex['score']}")
        print(f"     Issues: {', '.join(ex['issues'])}")
        print(f"     Sample: {ex['sample'][:100]}..." if ex['sample'] else "     No sample")
    
    # Pattern Analysis
    print("\n" + "="*100)
    print("3. OCR PATTERN ANALYSIS")
    print("="*100)
    
    patterns = analyze_ocr_patterns(vouchers)
    
    print(f"\n🔍 Common Patterns Found:")
    print(f"\n  Garbled/Merged Field Patterns:")
    for pattern, count in patterns['garbled_patterns'].most_common(10):
        print(f"    - {pattern}: {count} occurrences")
    
    print(f"\n  Supplier Name Indicators:")
    for indicator, count in patterns['supplier_indicators'].most_common(10):
        print(f"    - '{indicator}': {count} occurrences")
    
    # Conclusion
    print("\n" + "="*100)
    print("4. ROOT CAUSE CONCLUSION")
    print("="*100)
    
    total_ocr_issues = len(ocr_failures) + len([e for e in low_quality_examples if e['score'] < 50])
    total_parsing_issues = len(parsing_failures) + len(wrong_extraction)
    
    print(f"\n[ANALYSIS] ANALYSIS SUMMARY:")
    print(f"  - {len(ocr_failures)} fields genuinely missing from OCR (need better OCR)")
    print(f"  - {len(parsing_failures)} fields present in OCR but missed by parser")
    print(f"  - {len(wrong_extraction)} fields extracted with wrong values")
    print(f"  - {len(low_quality_examples)} vouchers have poor OCR quality (<60 score)")
    
    if total_ocr_issues > total_parsing_issues * 1.5:
        print(f"\n[TARGET] PRIMARY ISSUE: OCR Quality")
        print(f"   The main problem is poor OCR output quality.")
        print(f"   Recommendation: Focus on image preprocessing and OCR enhancement")
    elif total_parsing_issues > total_ocr_issues * 1.5:
        print(f"\n[TARGET] PRIMARY ISSUE: Parsing Logic")
        print(f"   The main problem is parser missing fields that ARE in OCR text.")
        print(f"   Recommendation: Improve pattern matching and field extraction")
    else:
        print(f"\n[TARGET] PRIMARY ISSUE: BOTH")
        print(f"   Both OCR quality AND parsing logic need improvement.")
        print(f"   Recommendation: Two-pronged approach needed")
    
    print(f"\n[IDEA] KEY INSIGHTS:")
    print(f"   1. Merged fields are common: 'VoucherDate VoucherNumber1070172026'")
    print(f"   2. OCR varies wildly: 'Nuaber', 'Nunber', 'Nunmber', 'Number'")
    print(f"   3. Amounts get garbled: '1S5550' instead of '155.50'")
    print(f"   4. Structure varies: Some have 'Supp Name', others just 'Name'")
    
    print(f"\n[PLAN] RECOMMENDED APPROACH:")
    print(f"   1. MULTI-STRATEGY OCR: Try 3-4 different preprocessing + OCR combinations")
    print(f"   2. CONFIDENCE SCORING: Score each extraction, flag low confidence for review")
    print(f"   3. POST-PROCESSING: Fix merged fields, correct common OCR errors")
    print(f"   4. FALLBACK CHAINS: If primary pattern fails, try alternatives")
    print(f"   5. VALIDATION: Cross-check extracted values (e.g., voucher # can't be year)")


if __name__ == "__main__":
    main()
