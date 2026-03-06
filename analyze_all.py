import os
import psycopg2
import json
from dotenv import load_dotenv

load_dotenv(r'C:\Users\ramst\Documents\apps\tkfl_ocr\pt5\.env')

def analyze_all_receipts():
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cur = conn.cursor()
    
    cur.execute('''
        SELECT id, file_name, raw_ocr_text, parsed_json 
        FROM vouchers_master 
        WHERE raw_ocr_text IS NOT NULL
    ''')
    
    rows = cur.fetchall()
    
    total_receipts = len(rows)
    stats = {
        'total': total_receipts,
        'has_voucher_number': 0,
        'has_date': 0,
        'has_supplier': 0,
        'has_gross_total': 0,
        'has_net_total': 0,
        'has_items': 0,
        'has_deductions': 0,
        'failed_completely': 0
    }
    
    failing_examples = []
    
    for row in rows:
        vid, fname, text, parsed = row
        
        if not parsed:
            stats['failed_completely'] += 1
            continue
            
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except:
                continue
                
        master = parsed.get('master', {})
        
        has_vn = bool(master.get('voucher_number'))
        has_dt = bool(master.get('voucher_date'))
        has_supp = bool(master.get('supplier_name'))
        has_gross = bool(master.get('gross_total'))
        has_net = bool(master.get('net_total'))
        has_items = len(parsed.get('items', [])) > 0
        has_ded = len(parsed.get('deductions', [])) > 0
        
        if has_vn: stats['has_voucher_number'] += 1
        if has_dt: stats['has_date'] += 1
        if has_supp: stats['has_supplier'] += 1
        if has_gross: stats['has_gross_total'] += 1
        if has_net: stats['has_net_total'] += 1
        if has_items: stats['has_items'] += 1
        if has_ded: stats['has_deductions'] += 1
        
        # If it failed to extract key fields but has text, save it for analysis
        if not has_vn or not has_supp or not has_net:
            if len(failing_examples) < 100: # limit to avoid massive memory usage
                failing_examples.append({
                    'id': vid,
                    'file': fname,
                    'text_snippet': text[:500] if text else "",
                    'missing': {
                        'voucher_number': not has_vn,
                        'supplier': not has_supp,
                        'net_total': not has_net
                    }
                })
                
    with open('comprehensive_analysis.json', 'w') as f:
        json.dump({
            'stats': stats,
            'failing_examples': failing_examples
        }, f, indent=2)
        
    print(json.dumps(stats, indent=2))
    conn.close()

if __name__ == '__main__':
    analyze_all_receipts()
