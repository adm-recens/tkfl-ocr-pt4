
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
    
    try:
        print("Creating batch_file_tracking table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS batch_file_tracking (
                id SERIAL PRIMARY KEY,
                batch_id TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("Table created successfully.")
            
        conn.commit()
    except Exception as e:
        print(f"Error creating table: {e}")
        conn.rollback()
    
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
