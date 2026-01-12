import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def check_nulls():
    conn = get_connection()
    cur = conn.cursor()
    
    print("\n--- Recent Vouchers (ID | BatchID) ---")
    cur.execute("SELECT id, batch_id FROM vouchers_master_beta ORDER BY created_at DESC LIMIT 5")
    recent = cur.fetchall()
    for v in recent:
        bid = v['batch_id'] if v['batch_id'] else "NULL"
        print(f"ID: {v['id']} | BatchID: {bid}")

if __name__ == '__main__':
    try:
        check_nulls()
    except Exception as e:
        print(f"Error: {e}")
