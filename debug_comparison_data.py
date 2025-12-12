import os
import sys
from backend.db import get_connection, init_app
from flask import Flask

app = Flask(__name__)
# Use the environment variable or a default (adjust as needed if using .env)
# Assuming the user is running this in the same env as the app
# But for safety let's try to get it from os or hardcode for this check if known
# The user's previous logs showed "Database connection pool initialized", so env var should be there.

def check_data():
    try:
        init_app(app)
        with app.app_context():
            conn = get_connection()
            cur = conn.cursor()
            
            print("--- Checking vouchers_master_beta ---")
            cur.execute("SELECT COUNT(*) FROM vouchers_master_beta")
            count = cur.fetchone()['count']
            print(f"Total rows in vouchers_master_beta: {count}")
            
            cur.execute("SELECT id, file_name, file_storage_path FROM vouchers_master_beta WHERE file_storage_path IS NOT NULL ORDER BY id DESC LIMIT 5")
            rows = cur.fetchall()
            
            if not rows:
                print("No rows with file_storage_path found!")
            else:
                print(f"Found {len(rows)} sample rows:")
                for row in rows:
                    path = row['file_storage_path']
                    exists = os.path.exists(path) if path else False
                    print(f"  ID: {row['id']}, Path: {path}, Exists: {exists}")
                    
            if count > 0 and not rows:
                 cur.execute("SELECT * FROM vouchers_master_beta LIMIT 1")
                 print("Sample row (all columns):", cur.fetchone())

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_data()
