import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import uuid

load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def insert_test():
    batch_id = 'f12a066b-9a55-4200-af8f-7b7d28d6bdb4'
    conn = get_connection()
    cur = conn.cursor()
    
    print(f"Checking batch {batch_id}...")
    cur.execute("SELECT * FROM batch_uploads WHERE batch_id = %s", (batch_id,))
    b = cur.fetchone()
    if not b:
        print("Batch not found! Using first available batch.")
        cur.execute("SELECT batch_id FROM batch_uploads LIMIT 1")
        b = cur.fetchone()
        batch_id = b['batch_id']
        print(f"Switched to batch {batch_id}")
    
    print("Inserting test voucher...")
    try:
        cur.execute("""
            INSERT INTO vouchers_master_beta 
            (file_name, file_storage_path, ocr_mode, batch_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, ('TEST_VOUCHER_DEBUG.png', '/tmp/test.png', 'debug', batch_id))
        
        vid = cur.fetchone()['id']
        print(f"Inserted Voucher ID: {vid}")
        conn.commit()
        print("Committed.")
        
        # Verify
        cur.execute("SELECT * FROM vouchers_master_beta WHERE id = %s", (vid,))
        v = cur.fetchone()
        if v:
            print("Verification Successful: Record Found.")
        else:
            print("Verification FAILED: Record Missing.")
            
    except Exception as e:
        print(f"Insert failed: {e}")
        conn.rollback()

if __name__ == '__main__':
    insert_test()
