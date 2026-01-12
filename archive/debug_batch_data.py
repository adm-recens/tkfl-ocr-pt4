import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def check_data():
    conn = get_connection()
    cur = conn.cursor()
    
    print("\n--- Recent Batches ---")
    cur.execute("SELECT batch_id, batch_name, total_files, created_at FROM batch_uploads ORDER BY created_at DESC LIMIT 3")
    batches = cur.fetchall()
    
    if not batches:
        print("No batches found.")
        return

    for b in batches:
        print(f"Batch: {b['batch_name']} | ID: {b['batch_id']}")
        
        print(f"--- Vouchers for Batch {b['batch_id']} ---")
        cur.execute("SELECT id, file_name, batch_id FROM vouchers_master_beta WHERE batch_id = %s", (b['batch_id'],))
        vouchers = cur.fetchall()
        if not vouchers:
             print("  NO VOUCHERS FOUND WITH THIS BATCH ID")
        for v in vouchers:
            print(f"  Voucher {v['id']}: {v['file_name']} | BatchID: {v['batch_id']}")
            
    print("\n--- Recent Vouchers (All) ---")
    cur.execute("SELECT id, file_name, batch_id, created_at FROM vouchers_master_beta ORDER BY created_at DESC LIMIT 5")
    recent = cur.fetchall()
    for v in recent:
        print(f"  Voucher {v['id']}: {v['file_name']} | BatchID: {v['batch_id']}")

if __name__ == '__main__':
    try:
        check_data()
    except Exception as e:
        print(f"Error: {e}")
