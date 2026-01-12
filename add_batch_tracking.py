
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

# Add parent directory to path to allow importing backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import get_connection, init_app
from flask import Flask

def run_migration():
    print("Starting database migration for batch tracking...")
    
    # Create a minimal Flask app context to use get_connection
    app = Flask(__name__)
    # Try to load config, but fallback to environment if needed
    # We'll just assume DATABASE_URL is in env or backend/db.py handles it
    
    with app.app_context():
        try:
            # backend/db.py relies on current_app for config usually, 
            # but has a fallback to os.environ['DATABASE_URL']
            # Let's ensure we have a valid connection
            conn = get_connection()
            cur = conn.cursor()
            
            # 1. Create batch_uploads table
            print("Creating batch_uploads table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS batch_uploads (
                    id SERIAL PRIMARY KEY,
                    batch_id VARCHAR(64) UNIQUE NOT NULL,
                    batch_name VARCHAR(255),
                    total_files INTEGER DEFAULT 0,
                    processed_files INTEGER DEFAULT 0,
                    validated_files INTEGER DEFAULT 0,
                    skipped_files INTEGER DEFAULT 0,
                    failed_files INTEGER DEFAULT 0,
                    status VARCHAR(50) DEFAULT 'processing',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_by VARCHAR(255)
                );
            """)
            
            # 2. Add batch_id to vouchers_master_beta
            print("Checking vouchers_master_beta table...")
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='vouchers_master_beta' AND column_name='batch_id';
            """)
            
            if not cur.fetchone():
                print("Adding batch_id column to vouchers_master_beta...")
                cur.execute("""
                    ALTER TABLE vouchers_master_beta 
                    ADD COLUMN batch_id VARCHAR(64) REFERENCES batch_uploads(batch_id);
                """)
            else:
                print("Column batch_id already exists.")
                
            conn.commit()
            print("Migration completed successfully.")
            
        except Exception as e:
            print(f"Migration failed: {e}")
            if 'conn' in locals() and conn:
                conn.rollback()
            sys.exit(1)
        finally:
            if 'conn' in locals() and conn:
                cur.close()
                # connection close is handled by pool usually, but for script we leave it
                pass

if __name__ == "__main__":
    run_migration()
