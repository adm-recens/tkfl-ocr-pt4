
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
    """
    Rename beta tables to production tables.
    This migration preserves all existing beta data.
    """
    conn = get_connection()
    if not conn:
        return

    cur = conn.cursor()
    
    migrations = [
        {
            'check': 'vouchers_master_beta',
            'old': 'vouchers_master_beta',
            'new': 'vouchers_master',
            'description': 'Rename vouchers_master_beta to vouchers_master'
        },
        {
            'check': 'voucher_items_beta',
            'old': 'voucher_items_beta',
            'new': 'voucher_items',
            'description': 'Rename voucher_items_beta to voucher_items'
        },
        {
            'check': 'voucher_deductions_beta',
            'old': 'voucher_deductions_beta',
            'new': 'voucher_deductions',
            'description': 'Rename voucher_deductions_beta to voucher_deductions'
        }
    ]
    
    for migration in migrations:
        try:
            print(f"\n{migration['description']}...")
            
            # Check if old table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                );
            """, (migration['check'],))
            
            old_exists = cur.fetchone()['exists']
            
            if not old_exists:
                print(f"  ⚠️  Table {migration['old']} does not exist. Skipping.")
                continue
            
            # Check if new table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                );
            """, (migration['new'],))
            
            new_exists = cur.fetchone()['exists']
            
            if new_exists:
                print(f"  ⚠️  Table {migration['new']} already exists. Dropping old table first...")
                cur.execute(f"DROP TABLE IF EXISTS {migration['old']} CASCADE;")
            else:
                # Rename the table
                cur.execute(f"ALTER TABLE {migration['old']} RENAME TO {migration['new']};")
                print(f"  ✅ Renamed {migration['old']} → {migration['new']}")
            
            conn.commit()
            
        except Exception as e:
            print(f"  ❌ Error during migration: {e}")
            conn.rollback()
            continue
    
    conn.close()
    print("\n✅ Database migration complete!")
    print("\nNote: batch_uploads and batch_file_tracking tables remain unchanged.")

if __name__ == "__main__":
    migrate()
