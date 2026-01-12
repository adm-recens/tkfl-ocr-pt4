import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')

def check_columns():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    table_name = 'voucher_items_beta'
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = %s
    """, (table_name,))
    cols = [c[0] for c in cur.fetchall()]
    print(f"Columns in {table_name}: {cols}")
    if 'unit_price' in cols: print("FOUND: unit_price")
    if 'rate' in cols: print("FOUND: rate")

if __name__ == '__main__':
    check_columns()
