import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def check_last_voucher():
    conn = get_connection()
    cur = conn.cursor()
    
    print("\n--- Last 3 Vouchers in Beta ---")
    cur.execute("SELECT id, file_name, batch_id, created_at FROM vouchers_master_beta ORDER BY created_at DESC LIMIT 3")
    vouchers = cur.fetchall()
    
    for v in vouchers:
        print(f"ID: {v['id']} | File: {v['file_name']} | BatchID: {v['batch_id']} | Time: {v['created_at']}")
        
    print("\n--- Last Batch ---")
    cur.execute("SELECT batch_id, batch_name FROM batch_uploads ORDER BY created_at DESC LIMIT 1")
    batch = cur.fetchone()
    if batch:
        print(f"Batch: {batch['batch_name']} | ID: {batch['batch_id']}")
    else:
        print("No batches found")

if __name__ == '__main__':
    try:
        check_last_voucher()
    except Exception as e:
        print(f"Error: {e}")
