# -*- coding: utf-8 -*-
"""
Compare OCR confidence scores between Enhanced and Experimental modes
"""
import os
import psycopg2
from dotenv import load_dotenv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from backend.ocr_service_beta import extract_text_beta

load_dotenv('backend/.env')

def get_db_connection():
    database_url = os.getenv('DATABASE_URL')
    return psycopg2.connect(database_url)

def get_beta_receipts():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, file_name, file_storage_path FROM vouchers_master_beta ORDER BY id")
    receipts = cur.fetchall()
    cur.close()
    conn.close()
    return receipts

def test_receipt(file_path, method):
    try:
        result = extract_text_beta(file_path, method=method)
        return {
            'confidence': result.get('confidence', 0),
            'processing_time': result.get('processing_time_ms', 0),
            'text_length': len(result.get('text', '')),
            'success': True
        }
    except Exception as e:
        return {'confidence': 0, 'processing_time': 0, 'text_length': 0, 'success': False, 'error': str(e)}

def main():
    print("=" * 80)
    print("OCR MODE COMPARISON TEST")
    print("=" * 80)
    print()
    
    receipts = get_beta_receipts()
    
    if not receipts:
        print("No beta receipts found. Please upload some receipts to /beta_v2/upload first.")
        return
    
    print(f"Found {len(receipts)} beta receipt(s) to test\n")
    
    results = []
    
    for idx, (receipt_id, file_name, file_path) in enumerate(receipts, 1):
        print(f"\n{'-' * 80}")
        print(f"Receipt #{idx}: {file_name} (ID: {receipt_id})")
        print(f"{'-' * 80}")
        
        if not os.path.exists(file_path):
            print(f"WARNING: File not found: {file_path}")
            continue
        
        print("\n[ENHANCED] Testing Enhanced mode...")
        enhanced = test_receipt(file_path, 'enhanced')
        
        if enhanced['success']:
            print(f"   Confidence: {enhanced['confidence']:.1f}%")
            print(f"   Processing: {enhanced['processing_time']:.0f}ms")
            print(f"   Text length: {enhanced['text_length']} chars")
        else:
            print(f"   ERROR: {enhanced.get('error', 'Unknown error')}")
        
        print("\n[EXPERIMENTAL] Testing Experimental mode...")
        experimental = test_receipt(file_path, 'experimental')
        
        if experimental['success']:
            print(f"   Confidence: {experimental['confidence']:.1f}%")
            print(f"   Processing: {experimental['processing_time']:.0f}ms")
            print(f"   Text length: {experimental['text_length']} chars")
        else:
            print(f"   ERROR: {experimental.get('error', 'Unknown error')}")
        
        if enhanced['success'] and experimental['success']:
            diff = experimental['confidence'] - enhanced['confidence']
            if diff > 0:
                print(f"\nWINNER: Experimental (+{diff:.1f}% better)")
            elif diff < 0:
                print(f"\nWINNER: Enhanced (+{abs(diff):.1f}% better)")
            else:
                print(f"\nTIE: Both modes equal")
        
        results.append({
            'id': receipt_id,
            'file_name': file_name,
            'enhanced': enhanced,
            'experimental': experimental
        })
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    enhanced_wins = 0
    experimental_wins = 0
    ties = 0
    enhanced_total = 0
    experimental_total = 0
    count = 0
    
    for result in results:
        if result['enhanced']['success'] and result['experimental']['success']:
            count += 1
            enhanced_conf = result['enhanced']['confidence']
            experimental_conf = result['experimental']['confidence']
            
            enhanced_total += enhanced_conf
            experimental_total += experimental_conf
            
            if experimental_conf > enhanced_conf:
                experimental_wins += 1
            elif enhanced_conf > experimental_conf:
                enhanced_wins += 1
            else:
                ties += 1
    
    if count > 0:
        print(f"\nTotal receipts tested: {count}")
        print(f"\nWin/Loss Record:")
        print(f"   Enhanced wins:      {enhanced_wins}")
        print(f"   Experimental wins:  {experimental_wins}")
        print(f"   Ties:               {ties}")
        
        print(f"\nAverage Confidence:")
        print(f"   Enhanced:      {enhanced_total/count:.1f}%")
        print(f"   Experimental:  {experimental_total/count:.1f}%")
        
        diff = (experimental_total/count) - (enhanced_total/count)
        if diff > 0:
            print(f"\nRESULT: Experimental is {diff:.1f}% better on average")
        elif diff < 0:
            print(f"\nRESULT: Enhanced is {abs(diff):.1f}% better on average")
        else:
            print(f"\nRESULT: Both modes perform equally on average")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
