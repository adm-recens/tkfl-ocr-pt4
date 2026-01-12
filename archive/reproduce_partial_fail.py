import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def test_savepoint():
    conn = get_connection()
    cur = conn.cursor()
    
    print("Starting transaction...")
    
    # Valid Insert 1
    try:
        cur.execute("SAVEPOINT sp1")
        print("Inserting Valid 1...")
        cur.execute("""
            INSERT INTO vouchers_master_beta (file_name, ocr_mode) VALUES ('VALID_1.png', 'test')
        """)
        cur.execute("RELEASE SAVEPOINT sp1")
    except Exception as e:
        print(f"Valid 1 failed: {e}")
        cur.execute("ROLLBACK TO SAVEPOINT sp1")
        
    # Invalid Insert 2
    try:
        cur.execute("SAVEPOINT sp2")
        print("Inserting Invalid 2...")
        # Intentionally passing string to float column 'gross_total' 
        # Actually simplest is to violate not null or data type
        # Let's try inserting text into integer/numeric field
        cur.execute("""
            INSERT INTO vouchers_master_beta (file_name, gross_total) VALUES ('INVALID_2.png', 'not_a_number')
        """)
        cur.execute("RELEASE SAVEPOINT sp2")
        print("Invalid 2 Inserted? (Should not happen)")
    except Exception as e:
        print(f"Caught expected error for Invalid 2: {e}")
        cur.execute("ROLLBACK TO SAVEPOINT sp2")
        
    # Valid Insert 3
    try:
        cur.execute("SAVEPOINT sp3")
        print("Inserting Valid 3...")
        cur.execute("""
            INSERT INTO vouchers_master_beta (file_name, ocr_mode) VALUES ('VALID_3.png', 'test')
        """)
        cur.execute("RELEASE SAVEPOINT sp3")
    except Exception as e:
        print(f"Valid 3 failed: {e}")
        cur.execute("ROLLBACK TO SAVEPOINT sp3")
        
    print("Committing...")
    conn.commit()
    
    # Verification
    cur.execute("SELECT file_name FROM vouchers_master_beta WHERE file_name LIKE 'VALID_%.png'")
    rows = cur.fetchall()
    print(f"Found {len(rows)} valid records: {[r['file_name'] for r in rows]}")
    
    if len(rows) == 2:
        print("SUCCESS: Partial failure handled correctly!")
    else:
        print("FAILURE: Transactions were lost.")
        
    # Cleanup
    cur.execute("DELETE FROM vouchers_master_beta WHERE file_name LIKE 'VALID_%.png'")
    conn.commit()

if __name__ == '__main__':
    test_savepoint()
