import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def repair_stats():
    conn = get_connection()
    cur = conn.cursor()
    
    # Get the latest batch ID
    cur.execute("""
        SELECT batch_id, batch_name, total_files 
        FROM batch_uploads 
        ORDER BY created_at DESC 
        LIMIT 1
    """)
    batch = cur.fetchone()
    batch_id = batch['batch_id']
    print(f"Repairing Batch: {batch['batch_name']} ({batch_id})")
    
    # Check actual counts from vouchers table
    cur.execute("""
        SELECT count(*) as count 
        FROM vouchers_master_beta 
        WHERE batch_id = %s AND supplier_name = 'UPLOAD FAILED'
    """, (batch_id,))
    failed_count = cur.fetchone()['count']
    
    cur.execute("""
        SELECT count(*) as count 
        FROM vouchers_master_beta 
        WHERE batch_id = %s AND (supplier_name != 'UPLOAD FAILED' OR supplier_name IS NULL)
    """, (batch_id,))
    valid_count = cur.fetchone()['count']
    
    print(f"Found: {valid_count} Valid, {failed_count} Failed")
    
    # Update Stats
    cur.execute("""
        UPDATE batch_uploads 
        SET validated_files = %s,
            failed_files = %s,
            status = CASE WHEN %s > 0 THEN 'partial_failure' ELSE 'completed' END
        WHERE batch_id = %s
    """, (valid_count, failed_count, failed_count, batch_id))
    
    conn.commit()
    print("Stats repaired.")

if __name__ == '__main__':
    try:
        repair_stats()
    except Exception as e:
        print(f"Error: {e}")
