# backend/db.py (PostgreSQL Version with Connection Pooling)

import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from flask import current_app, g

# Global connection pool
_pool = None

def init_app(app):
    """Initialize the database connection pool with the app."""
    global _pool
    database_url = app.config.get('DATABASE_URL')
    
    if not database_url:
        # Fallback for local dev if not in config (though it should be)
        database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        app.logger.warning("DATABASE_URL not set. Database features will fail.")
        return
        
    try:
        # Initialize the threaded connection pool
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=20,
            dsn=database_url,
            cursor_factory=RealDictCursor
        )
        app.logger.info("Database connection pool initialized.")
    except Exception as e:
        app.logger.error(f"Failed to initialize database pool: {e}")
        raise e

    # Register teardown to close connection if it was opened in this request
    app.teardown_appcontext(close_db_connection)

def get_connection():
    """
    Get a connection from the pool.
    Stores it in flask.g so it can be reused within the same request.
    """
    global _pool
    if 'db_conn' not in g:
        if _pool is None:
            # Fallback for scripts/tests that might not call init_app
            # Or if init_app wasn't called. 
            if current_app:
                 init_app(current_app)
            
            # If still None (e.g. standalone script), try to create a temp pool or connection
            if _pool is None:
                 dsn = os.environ.get('DATABASE_URL')
                 if dsn:
                     try:
                         # Create a temporary single connection for this context
                         # This is not ideal for high load but works for scripts
                         conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
                         g.db_conn = conn
                         return conn
                     except Exception as e:
                         print(f"Error creating standalone connection: {e}")
                         raise e
                 else:
                     raise RuntimeError("Database pool not initialized and DATABASE_URL not found.")
        
        try:
            g.db_conn = _pool.getconn()
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error getting connection from pool: {e}")
            raise e
            
    return g.db_conn

def close_db_connection(error=None):
    """Return the connection to the pool at the end of the request."""
    conn = g.pop('db_conn', None)
    if conn is not None:
        if _pool is not None:
            try:
                _pool.putconn(conn)
            except Exception as e:
                if current_app:
                    current_app.logger.error(f"Error returning connection to pool: {e}")
        else:
            # If it was a standalone connection, close it
            try:
                conn.close()
            except Exception as e:
                print(f"Error closing standalone connection: {e}")

def get_db():
    """Alias for get_connection for compatibility."""
    return get_connection()

def init_db():
    """Creates all four normalized tables in PostgreSQL."""
    conn = None
    try:
        # We use get_connection() which ensures RealDictCursor is used
        conn = get_connection()
        cur = conn.cursor()
        
        # 1. Vouchers Master Table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS vouchers_master (
            id SERIAL PRIMARY KEY,
            file_name TEXT UNIQUE NOT NULL,
            file_mime_type TEXT,
            file_storage_path TEXT,
            validation_status TEXT DEFAULT 'RAW',
            ocr_mode TEXT DEFAULT 'default', 
            parsed_json JSONB,
            raw_ocr_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- Normalized fields for querying
            voucher_number TEXT,
            voucher_date DATE,
            supplier_name TEXT,
            vendor_details TEXT,
            gross_total NUMERIC(12, 2),
            total_deductions NUMERIC(12, 2),
            net_total NUMERIC(12, 2),
            ocr_confidence NUMERIC(5, 2),
            batch_id TEXT
        );
        """)

        # 2. Items Table (One-to-Many)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS voucher_items (
            id SERIAL PRIMARY KEY,
            master_id INTEGER NOT NULL REFERENCES vouchers_master(id) ON DELETE CASCADE,
            item_name TEXT,
            quantity NUMERIC(10, 2),
            unit_price NUMERIC(10, 2),
            line_amount NUMERIC(12, 2)
        );
        """)

        # 3. Deductions Table (One-to-Many)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS voucher_deductions (
            id SERIAL PRIMARY KEY,
            master_id INTEGER NOT NULL REFERENCES vouchers_master(id) ON DELETE CASCADE,
            deduction_type TEXT,
            amount NUMERIC(12, 2)
        );
        """)
        
        # 4. Bounding Boxes Table (Optional/Advanced)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS voucher_bboxes (
            id SERIAL PRIMARY KEY,
            master_id INTEGER NOT NULL REFERENCES vouchers_master(id) ON DELETE CASCADE,
            field_type TEXT NOT NULL, 
            ground_truth_value TEXT,
            box_x INTEGER,
            box_y INTEGER,
            box_w INTEGER,
            box_h INTEGER
        );
        """)

        # 5. File Lifecycle Meta Table (Tracks all uploads)
        cur.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        """)

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
            processing_status TEXT DEFAULT 'pending', 
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

        cur.execute("""
        DROP TRIGGER IF EXISTS update_file_lifecycle_modtime ON file_lifecycle_meta;
        CREATE TRIGGER update_file_lifecycle_modtime
            BEFORE UPDATE ON file_lifecycle_meta
            FOR EACH ROW
            EXECUTE PROCEDURE update_updated_at_column();
        """)

        # 6. Suppliers Table (Independent)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            address TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # 7. Receipts Table (Independent Production Data)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS receipts (
            id SERIAL PRIMARY KEY,
            supplier_id INTEGER REFERENCES suppliers(id),
            
            -- Traceability
            ocr_voucher_id INTEGER, 
            
            -- Business Data
            receipt_number TEXT,
            receipt_date DATE,
            
            -- Totals
            gross_total NUMERIC(12, 2),
            total_deductions NUMERIC(12, 2),
            net_total NUMERIC(12, 2),
            
            -- Mapped Deductions
            deduction_commission NUMERIC(10, 2) DEFAULT 0,
            deduction_damage NUMERIC(10, 2) DEFAULT 0,
            deduction_unloading NUMERIC(10, 2) DEFAULT 0,
            deduction_lf_cash NUMERIC(10, 2) DEFAULT 0,
            deduction_other NUMERIC(10, 2) DEFAULT 0,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        conn.commit()
        print("✅ Database tables initialized successfully.")
        
    except Exception as e:
        print(f"Error during DB initialization: {e}")
        if conn:
            conn.rollback()
        raise e
    # Note: Connection closing is handled by teardown_appcontext or manually if script
