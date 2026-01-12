
import os
import sys
from backend.ocr_service_beta import extract_text_beta
from backend.db import get_connection, init_app
from flask import Flask

app = Flask(__name__)

def test_ocr():
    try:
        init_app(app)
        with app.app_context():
            conn = get_connection()
            cur = conn.cursor()
            
            # Get one valid file
            cur.execute("SELECT file_storage_path FROM vouchers_master_beta WHERE file_storage_path IS NOT NULL ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            
            if not row:
                print("No files found to test.")
                return

            path = row['file_storage_path']
            print(f"Testing OCR on: {path}")
            
            if not os.path.exists(path):
                print("File does not exist!")
                return
                
            print("Running 'optimal' mode...")
            res = extract_text_beta(path, method='optimal')
            print("Success!")
            print(f"Confidence: {res['confidence']}")
            print(f"Text length: {len(res['text'])}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ocr()
