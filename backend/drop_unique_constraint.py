
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
            # In Postgres, unique constraints often have a specific name.
            # We try to drop the constraint if we can find it, or drop the index.
            # Usually strict unique constraint is named {table}_file_name_key
            
            constraint_name = f"{table}_file_name_key"
            
            print(f"Attempting to drop constraint {constraint_name}...")
            cur.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint_name};")
            
            print(f"Dropped successfully (if it existed).")
                
        except Exception as e:
            print(f"Error updating {table}: {e}")
            conn.rollback()
            continue
            
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
