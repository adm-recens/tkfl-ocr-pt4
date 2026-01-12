"""
Integration Test: Beta_v2 to Main Migration Validation
Tests the complete workflow: Upload → OCR (Optimal) → Parse (Validation) → Display
"""

import os
import sys
from flask import Flask
from backend.db import init_app, get_connection
from backend.ocr_service import extract_text
from backend.parser import parse_receipt_text

def test_migration():
    print("=== MIGRATION INTEGRATION TEST ===\n")
    
    app = Flask(__name__)
    init_app(app)
    
    with app.app_context():
        conn = get_connection()
        cur = conn.cursor()
        
        # Get a sample file from database
        cur.execute("SELECT id, file_name, file_storage_path FROM vouchers_master WHERE file_storage_path IS NOT NULL LIMIT 1")
        row = cur.fetchone()
        
        if not row:
            print("⚠️  No files in database. Please upload a voucher first.")
            return False
        
        voucher_id = row['id']
        file_name = row['file_name']
        file_path = row['file_storage_path']
        
        print(f"Testing with Voucher #{voucher_id}: {file_name}")
        print(f"Path: {file_path}\n")
        
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return False
        
        # Test 1: OCR with Optimal Mode
        print("[1/4] Testing OCR Service (Optimal Mode)...")
        try:
            ocr_result = extract_text(file_path, method='optimal')
            print(f"   ✅ OCR Success")
            print(f"   Confidence: {ocr_result['confidence']}%")
            print(f"   Processing Time: {ocr_result['processing_time_ms']}ms")
            print(f"   Text Length: {len(ocr_result['text'])} chars")
        except Exception as e:
            print(f"   ❌ OCR Failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test 2: Enhanced Parser with Validation
        print("\n[2/4] Testing Enhanced Parser...")
        try:
            parsed_data = parse_receipt_text(ocr_result['text'])
            print(f"   ✅ Parsing Success")
            print(f"   Voucher #: {parsed_data['master']['voucher_number']}")
            print(f"   Gross Total: {parsed_data['master']['gross_total']}")
            print(f"   Net Total: {parsed_data['master']['net_total']}")
            print(f"   Items: {len(parsed_data['items'])}")
            print(f"   Deductions: {len(parsed_data['deductions'])}")
        except Exception as e:
            print(f"   ❌ Parsing Failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test 3: Phase 4 Validation Features
        print("\n[3/4] Testing Phase 4 Validation...")
        metadata = parsed_data.get('metadata', {})
        warnings = metadata.get('validation_warnings', [])
        corrections = metadata.get('corrections', [])
        
        if warnings:
            print(f"   ⚠️  Validation Warnings ({len(warnings)}):")
            for w in warnings:
                print(f"      - {w}")
        else:
            print("   ✅ No validation warnings")
        
        if corrections:
            print(f"   ✅ Auto-Corrections Applied ({len(corrections)}):")
            for c in corrections:
                print(f"      - {c}")
        else:
            print("   ℹ️  No auto-corrections needed")
        
        # Test 4: Mode Compatibility
        print("\n[4/4] Testing Multiple OCR Modes...")
        modes = ['optimal', 'adaptive', 'enhanced']
        for mode in modes:
            try:
                result = extract_text(file_path, method=mode)
                print(f"   ✅ {mode.capitalize()}: Confidence {result['confidence']}%")
            except Exception as e:
                print(f"   ❌ {mode.capitalize()}: Failed - {e}")
                return False
        
        print("\n" + "="*50)
        print("🏆 MIGRATION TEST PASSED")
        print("="*50)
        print("\nSystem Status:")
        print("  ✅ OCR Service: Migrated to Optimal mode")
        print("  ✅ Parser: Enhanced with validation")
        print("  ✅ Phase 4: Auto-correction active")
        print("  ✅ Multi-mode support: Working")
        return True

if __name__ == "__main__":
    success = test_migration()
    sys.exit(0 if success else 1)
