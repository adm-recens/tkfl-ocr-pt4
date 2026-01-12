
import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("DATABASE_URL not set.")
        return None
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)

def migrate():
    conn = get_connection()
    if not conn:
        return

    cur = conn.cursor()
    
    tables = ['vouchers_master_beta', 'vouchers_master']
    
    for table in tables:
        try:
            print(f"Checking table: {table}")
            # Check if column exists
            cur.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='{table}' AND column_name='ocr_confidence';
            """)
            if cur.fetchone():
                print(f"Column ocr_confidence already exists in {table}.")
            else:
                print(f"Adding ocr_confidence to {table}...")
                cur.execute(f"ALTER TABLE {table} ADD COLUMN ocr_confidence NUMERIC(5, 2);")
                print(f"Added successfully.")
                
        except Exception as e:
            print(f"Error updating {table}: {e}")
            conn.rollback()
            continue
            
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
