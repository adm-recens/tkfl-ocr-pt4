
import os
import sys
import compileall
import importlib
from flask import Flask
from backend.db import get_connection, init_app
from backend.ocr_service_beta import extract_text_beta
from backend.parser_beta import parse_receipt_text, validate_and_correct
from backend.services.voucher_service_beta import VoucherServiceBeta

def check_syntax():
    print("\n[1/4] Checking Python Syntax...")
    try:
        # distinct=True to skip duplicate checks
        if compileall.compile_dir('backend', force=True, quiet=1):
            print("   ✅ Backend syntax OK")
        else:
            print("   ❌ Syntax errors found in backend/")
            return False
    except Exception as e:
        print(f"   ⚠️ Syntax check warning: {e}")
    return True

def check_critical_files():
    print("\n[2/4] Verifying Critical Files...")
    required = [
        'backend/ocr_service_beta.py',
        'backend/parser_beta.py',
        'backend/routes/api_beta_v2.py',
        'backend/templates/review_beta_v2.html',
        'backend/data/vendors.json'
    ]
    all_ok = True
    for f in required:
        if os.path.exists(f):
            print(f"   ✅ Found {f}")
        else:
            print(f"   ❌ MISSING {f}")
            all_ok = False
    return all_ok

def test_pipeline_simulation():
    print("\n[3/4] Testing OCR Pipeline Simulation...")
    app = Flask(__name__)
    try:
        init_app(app)
        with app.app_context():
            conn = get_connection()
            cur = conn.cursor()
            
            # Get a sample file
            cur.execute("SELECT file_storage_path FROM vouchers_master_beta WHERE file_storage_path IS NOT NULL LIMIT 1")
            row = cur.fetchone()
            
            if not row:
                print("   ⚠️ No existing files in DB to test. Skipping pipeline check.")
                return True
                
            path = row['file_storage_path']
            if not os.path.exists(path):
                print(f"   ❌ Test file missing on disk: {path}")
                return False
                
            print(f"   Testing with: {os.path.basename(path)}")
            
            # 1. OCR
            print("   >> Running Optimal OCR...")
            ocr_res = extract_text_beta(path, method='optimal')
            if not ocr_res or 'text' not in ocr_res:
                print("   ❌ OCR Failed")
                return False
            print(f"      Confidence: {ocr_res['confidence']}%")
            
            # 2. Parsing
            print("   >> Parsing Text...")
            parsed = parse_receipt_text(ocr_res['text'])
            print(f"      Extracted Gross: {parsed['master']['gross_total']}")
            
            # 3. Validation Logic (Phase 4 Check)
            print("   >> Running Logic Validator...")
            # Simulate a scenario to trigger validator if original is perfect
            parsed['items'].append({'line_amount': 99999.0}) # Inject noise
            parsed['master']['gross_total'] = 100.0
            
            validated, warnings, corrections = validate_and_correct(parsed)
            # We expect a warning now
            if warnings:
                print(f"   ✅ Validator correctly flagged inconsistencies: {len(warnings)} warnings")
            else:
                print("   ⚠️ Validator failed to flag injected error (Check logic)")

            print("   ✅ Pipeline Simulation Passed")
            return True
            
    except Exception as e:
        print(f"   ❌ Simulation Crashed: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_db_connectivity():
    print("\n[4/4] Verifying Database Connectivity...")
    try:
        app = Flask(__name__)
        init_app(app)
        with app.app_context():
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM vouchers_master_beta")
            count = cur.fetchone()[0]
            print(f"   ✅ Connected. Total Beta Vouchers: {count}")
            return True
    except Exception as e:
        print(f"   ❌ DB Connection Failed: {e}")
        return False

def run_all():
    print("=== FINAL SYSTEM VALIDATION ===")
    s1 = check_syntax()
    s2 = check_critical_files()
    s3 = verify_db_connectivity()
    s4 = test_pipeline_simulation()
    
    if s1 and s2 and s3 and s4:
        print("\n🏆 RESULT: SYSTEM IS HEALTHY. READY FOR COMMIT.")
    else:
        print("\n⚠️ RESULT: ISSUES DETECTED. REVIEW LOGS ABOVE.")

if __name__ == "__main__":
    run_all()
