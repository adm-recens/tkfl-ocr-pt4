import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def check_columns():
    conn = get_connection()
    cur = conn.cursor()
    
    table_name = 'voucher_items_beta'
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = %s
    """, (table_name,))
    
    cols = [c['column_name'] for c in cur.fetchall()]
    print(f"Columns in {table_name}: {cols}")
    
    if 'item_name' in cols:
        print("FOUND: item_name")
    if 'item_description' in cols:
        print("FOUND: item_description")
    else:
        print("MISSING: item_description")

if __name__ == '__main__':
    try:
        check_columns()
    except Exception as e:
        print(f"Error: {e}")
