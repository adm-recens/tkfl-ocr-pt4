#!/usr/bin/env python
"""
Migration: Add parsed_json_original column to preserve OCR output for ML training.

This allows the ML training system to see the difference between what was OCR'd
and what the user corrected, enabling the models to learn from corrections.
"""

from backend import create_app
from backend.db import get_connection

def add_parsed_json_original_column():
    """Add column to store original OCR data"""
    app = create_app()
    with app.app_context():
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            # Check if column already exists
            cur.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'vouchers_master' AND column_name = 'parsed_json_original'
            """)
            
            if cur.fetchone():
                print("[OK] Column 'parsed_json_original' already exists")
                return
            
            # Add the column
            cur.execute("""
                ALTER TABLE vouchers_master 
                ADD COLUMN parsed_json_original JSON DEFAULT NULL
            """)
            
            conn.commit()
            print("[OK] Added column 'parsed_json_original'")
            
            # Now populate it with current parsed_json values for already validated vouchers
            cur.execute("""
                UPDATE vouchers_master 
                SET parsed_json_original = parsed_json 
                WHERE validation_status = 'VALIDATED' AND parsed_json_original IS NULL
            """)
            
            conn.commit()
            affected = cur.rowcount
            print(f"[OK] Populated original data for {affected} existing validated vouchers")
            
        except Exception as e:
            print(f"[ERROR] {e}")
            conn.rollback()

if __name__ == '__main__':
    add_parsed_json_original_column()
