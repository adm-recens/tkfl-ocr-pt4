import psycopg2
from backend.db import get_connection
from backend import create_app

def add_independent_tables():
    app = create_app()
    with app.app_context():
        conn = get_connection()
        try:
            cur = conn.cursor()
            
            print("Creating 'suppliers' table...")
            cur.execute("""
            CREATE TABLE IF NOT EXISTS suppliers (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                address TEXT,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            
            print("Creating 'receipts' table...")
            cur.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                id SERIAL PRIMARY KEY,
                supplier_id INTEGER REFERENCES suppliers(id),
                
                -- Traceability (Lazy Link to Vouchers Master)
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
            print("✅ Tables 'suppliers' and 'receipts' created successfully.")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            if conn:
                conn.rollback()
        # Note: Do not close connection here as get_connection manages it within app context context logic usually, 
        # but here we are just script.


if __name__ == "__main__":
    add_independent_tables()
