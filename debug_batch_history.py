import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def check_batches():
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT batch_name, status, total_files, validated_files, failed_files 
        FROM batch_uploads 
        ORDER BY created_at DESC 
        LIMIT 3
    """)
    batches = cur.fetchall()
    
    for b in batches:
        print(f"{b['batch_name']} | S:{b['status']} | T:{b['total_files']} V:{b['validated_files']} F:{b['failed_files']}")

if __name__ == '__main__':
    try:
        check_batches()
    except Exception as e:
        print(f"Error: {e}")
