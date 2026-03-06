import json
from backend.tkfl_parser_v2 import parse_receipt_text_tkfl_v2
from backend.quality_focused_extractor import parse_receipt_text as parse_receipt_qfe

def verify_bulk():
    print("Testing Parser improvements on bulk receipts...")
    
    with open("comprehensive_analysis.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        
    failures = data.get("failing_examples", [])
    
    success_count = {
        'vn': 0, 'vd': 0, 'supp': 0, 'net': 0
    }
    
    for item in failures:
        raw_text = item["text_snippet"] # wait, the snippet might be truncated!
        # if it's truncated, it might not parse well, but let's try
        
        # Testing the v2 parser
        result = parse_receipt_text_tkfl_v2(raw_text)
        master = result.get('master', {})
        
        if master.get('voucher_number'): success_count['vn'] += 1
        if master.get('voucher_date'): success_count['vd'] += 1
        if master.get('supplier_name'): success_count['supp'] += 1
        if master.get('net_total'): success_count['net'] += 1

    total = len(failures)
    print(f"Bulk Test Results on {total} previously failed chunks:")
    print(f"Voucher Number: {success_count['vn']}/{total}")
    print(f"Voucher Date:   {success_count['vd']}/{total}")
    print(f"Supplier Name:  {success_count['supp']}/{total}")
    print(f"Net Total:      {success_count['net']}/{total}")

if __name__ == "__main__":
    verify_bulk()
