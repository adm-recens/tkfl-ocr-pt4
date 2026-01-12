import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Load environment variables
load_dotenv()

def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("Error: DATABASE_URL not found in environment variables")
        return None
    try:
        conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def create_meta_table():
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database.")
        return

    try:
        cur = conn.cursor()
        
        print("Creating file_lifecycle_meta table...")
        
        # 1. Create Filter Function for Updated At
        cur.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        """)

        # 2. Create Table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS file_lifecycle_meta (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            original_filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL UNIQUE,
            file_path TEXT NOT NULL,
            file_size_bytes BIGINT,
            file_hash TEXT, -- MD5/SHA256 for duplicate detection
            mime_type TEXT,
            
            -- Context
            upload_batch_id TEXT,
            source_type TEXT DEFAULT 'web_upload',
            client_ip TEXT,
            user_agent TEXT,
            
            -- Status & Links
            processing_status TEXT DEFAULT 'pending', -- 'pending', 'processed', 'failed', 'archived'
            voucher_id INTEGER REFERENCES vouchers_master(id) ON DELETE SET NULL,
            
            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            archived_at TIMESTAMP,
            
            -- Extensible Data
            meta_data JSONB
        );
        """)
        
        # 3. Create Trigger
        cur.execute("""
        DROP TRIGGER IF EXISTS update_file_lifecycle_modtime ON file_lifecycle_meta;
        CREATE TRIGGER update_file_lifecycle_modtime
            BEFORE UPDATE ON file_lifecycle_meta
            FOR EACH ROW
            EXECUTE PROCEDURE update_updated_at_column();
        """)
        
        # 4. Create Indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_file_meta_batch ON file_lifecycle_meta(upload_batch_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_file_meta_hash ON file_lifecycle_meta(file_hash);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_file_meta_voucher ON file_lifecycle_meta(voucher_id);")

        conn.commit()
        print("Successfully created 'file_lifecycle_meta' table, function, and triggers.")
        
    except Exception as e:
        conn.rollback()
        print(f"Error creating table: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    create_meta_table()
