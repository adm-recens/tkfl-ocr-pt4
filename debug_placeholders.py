import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def check_placeholders():
    conn = get_connection()
    cur = conn.cursor()
    
    # Get the latest batch ID
    cur.execute("SELECT batch_id FROM batch_uploads ORDER BY created_at DESC LIMIT 1")
    batch_id = cur.fetchone()['batch_id']
    print(f"Checking Batch: {batch_id}")
    
    # Count normal vs placeholder vouchers
    cur.execute("""
        SELECT count(*) as count, supplier_name 
        FROM vouchers_master_beta 
        WHERE batch_id = %s 
        GROUP BY supplier_name
    """, (batch_id,))
    counts = cur.fetchall()
    
    print("Voucher Breakdown:")
    for c in counts:
        print(f"  {c['supplier_name']}: {c['count']}")

if __name__ == '__main__':
    try:
        check_placeholders()
    except Exception as e:
        print(f"Error: {e}")
