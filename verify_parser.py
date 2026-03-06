import json
from backend.tkfl_parser_v2 import parse_receipt_text_tkfl_v2

def verify_parsing():
    print("Testing Parser v2 improvements on failed receipts...")
    
    with open("raw_text_output.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        
    for item in data:
        vid = item["voucher_id"]
        raw_text = item["raw_text"]
        
        print(f"\n--- Testing Voucher {vid} ---")
        result = parse_receipt_text_tkfl_v2(raw_text)
        
        master = result.get('master', {})
        deductions = result.get('deductions', [])
        
        vn = master.get('voucher_number')
        vd = master.get('voucher_date')
        supp = master.get('supplier_name')
        nt = master.get('net_total')
        
        print(f"Voucher #: {vn if vn else 'FAIL'}")
        print(f"Date:      {vd if vd else 'FAIL'}")
        print(f"Supplier:  {supp if supp else 'FAIL'}")
        print(f"Net Total: {nt if nt else 'FAIL'}")
        print(f"Deductions count: {len(deductions)}")
        for d in deductions:
            print(f"  - {d['deduction_type']}: {d['amount']}")

if __name__ == "__main__":
    verify_parsing()
