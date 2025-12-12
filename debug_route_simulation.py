
import os
import sys
import time
from flask import Flask
from backend.db import get_connection, init_app
from backend.ocr_service_beta import extract_text_beta

app = Flask(__name__)

def simulate_comparison():
    print("--- Starting Comparison Route Simulation ---")
    try:
        init_app(app)
        with app.app_context():
            conn = get_connection()
            cur = conn.cursor()
            
            print("1. Querying Database...")
            cur.execute("SELECT id, file_name, file_storage_path FROM vouchers_master_beta WHERE file_storage_path IS NOT NULL ORDER BY id DESC")
            receipts = cur.fetchall()
            print(f"   Found {len(receipts)} receipts.")
            
            results = []
            max_test = 3 # Limit to 3 for quick debug
            
            for i, row in enumerate(receipts):
                if i >= max_test:
                    print("   (Limit reached for debug)")
                    break
                    
                r_id = row['id']
                r_name = row['file_name']
                r_path = row['file_storage_path']
                
                print(f"\n2. Testing Receipt ID {r_id} ({r_name})")
                print(f"   Path: {r_path}")
                
                if not os.path.exists(r_path):
                    print("   [!] File path does not exist. Skipping.")
                    continue
                else:
                    print("   [OK] File exists.")
                    
                # Test all 5 modes
                modes = ['optimal', 'adaptive', 'aggressive', 'enhanced', 'simple']
                
                for mode in modes:
                    print(f"   Running OCR ({mode})...")
                    try:
                        res = extract_text_beta(r_path, method=mode)
                        print(f"   [OK] {mode} Success! Confidence: {res['confidence']}")
                    except Exception as e:
                        print(f"   [FAIL] {mode} Error: {e}")
                        import traceback
                        traceback.print_exc()
                
                results.append({'id': r_id})

            print("\n--- Summary ---")
            print(f"Total processed: {len(results)}")

    except Exception as e:
        print(f"Simulation Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    simulate_comparison()
