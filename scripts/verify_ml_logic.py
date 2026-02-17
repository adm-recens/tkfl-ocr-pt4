import sys
import os
import json
import logging

# Add parent dir to path to import backend modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
from backend.ml_models.ml_correction_model import ParsingCorrectionModel

# Load env vars
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Verification")

def get_standalone_connection():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("Error: DATABASE_URL not found in environment.")
        sys.exit(1)
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

def verify_logic():
    print("=" * 60)
    print("VERIFYING ADAPTIVE PARSING LOGIC")
    print("=" * 60)
    
    try:
        conn = get_standalone_connection()
    except Exception as e:
        print(f"Failed to connect to DB: {e}")
        return

    cur = conn.cursor()
    
    # Fetch validated vouchers
    cur.execute("""
        SELECT id, supplier_name, raw_ocr_text, parsed_json 
        FROM vouchers_master 
        WHERE validation_status = 'VALIDATED' 
        AND raw_ocr_text IS NOT NULL 
        LIMIT 20
    """)
    rows = cur.fetchall()
    conn.close()
    
    if not rows:
        print("No validated vouchers found to verify against.")
        return

    model = ParsingCorrectionModel()
    
    print(f"Testing on {len(rows)} vouchers...")
    print("-" * 60)

    for row in rows:
        v_id = row['id']
        supplier = row['supplier_name']
        raw_ocr = row['raw_ocr_text']
        user_data = row['parsed_json']
        
        if isinstance(user_data, str):
            user_data = json.loads(user_data)
        
        master = user_data.get('master', {})
        deductions = user_data.get('deductions', [])
        
        print(f"\n[Voucher {v_id}] Supplier: {supplier}")
        
        # 1. TEST ANCHOR LEARNING (Date & Voucher No)
        # Simulate learning from THIS voucher
        if master.get('voucher_date'):
            model.learn_anchor('voucher_date', raw_ocr, master['voucher_date'], supplier)
        
        if master.get('voucher_number'):
            model.learn_anchor('voucher_number', raw_ocr, master['voucher_number'], supplier)

        # Now try to "Find" it back using the anchor we just learned
        # This proves the anchor logic works on this text
        
        # Date Check
        found_date = model.find_value_by_anchor('voucher_date', raw_ocr, supplier)
        if found_date:
            print(f"  [SUCCESS] Learned Anchor '{found_date['anchor']}' -> Found Date: {found_date['value']}")
        else:
            print(f"  [FAILED] Could not learn anchor for Date: {master.get('voucher_date')}")

        # 2. TEST DEDUCTION SCANNING (Regex Logic)
        print("  Checking Deductions...")
        
        # Use the SAME logic we added to MLTrainingService
        deduction_patterns = {
            'Commission': [r'Comm\s*@', r'Commission'],
            'Damage': [r'Less\s*for\s*Damage', r'Damage'],
            'Unloading': [r'UnLoading', r'Unloading'],
            'L/F and Cash': [r'L/F\s*and\s*Cash', r'L/F'],
            'Other': [r'Other'] 
        }
        
        import re
        from backend.parser import safe_float_conversion
        
        found_deductions = []
        for ded_type, patterns in deduction_patterns.items():
            for pat in patterns:
                # The updated regex logic
                regex = re.compile(pat + r".*?(\d+\.?\d*)\s*(%)?", re.IGNORECASE)
                match = regex.search(raw_ocr)
                if match:
                    val = float(match.group(1))
                    is_percent = bool(match.group(2))
                    suffix = "%" if is_percent else ""
                    print(f"    FOUND {ded_type}: {val}{suffix} (Match: '{match.group(0)}')")
                    found_deductions.append(ded_type)
        
        if not found_deductions and deductions:
             print("    WARNING: User has deductions but Logic found none.")
             for d in deductions:
                 print(f"      User Entry: {d}")
        elif not deductions and not found_deductions:
            print("    (No deductions present in user data or text)")

if __name__ == "__main__":
    verify_logic()
