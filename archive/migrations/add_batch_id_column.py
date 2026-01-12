import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def add_batch_id_column():
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    cur = conn.cursor()
    
    try:
        # Check if batch_id column exists
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'vouchers_master' AND column_name = 'batch_id'
        """)
        
        if cur.fetchone():
            print("✅ batch_id column already exists")
        else:
            print("Adding batch_id column to vouchers_master...")
            cur.execute("ALTER TABLE vouchers_master ADD COLUMN batch_id TEXT;")
            conn.commit()
            print("✅ Successfully added batch_id column")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    add_batch_id_column()
