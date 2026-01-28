#!/usr/bin/env python
"""
Populate parsed_json_original for existing vouchers that don't have it.
This prepares the database for the new training system.
"""

from backend import create_app
from backend.db import get_connection
import json

app = create_app()
with app.app_context():
    conn = get_connection()
    cur = conn.cursor()
    
    # Get all vouchers that have parsed_json but not parsed_json_original
    cur.execute("""
        SELECT id, parsed_json
        FROM vouchers_master
        WHERE parsed_json IS NOT NULL AND parsed_json_original IS NULL
        ORDER BY id
    """)
    
    vouchers = cur.fetchall()
    print(f"Found {len(vouchers)} vouchers to populate")
    
    updated = 0
    for voucher in vouchers:
        try:
            cur.execute("""
                UPDATE vouchers_master
                SET parsed_json_original = %s
                WHERE id = %s
            """, (voucher['parsed_json'], voucher['id']))
            
            updated += 1
            if updated % 10 == 0:
                print(f"  Updated {updated} vouchers...")
        except Exception as e:
            print(f"  ERROR updating voucher {voucher['id']}: {e}")
    
    conn.commit()
    print(f"[SUCCESS] Updated {updated} vouchers with original parsed data")
    
    # Now test by checking a sample
    cur.execute("""
        SELECT id, parsed_json, parsed_json_original
        FROM vouchers_master
        WHERE parsed_json_original IS NOT NULL
        LIMIT 1
    """)
    
    sample = cur.fetchone()
    if sample:
        print(f"\nSample voucher {sample['id']}:")
        parsed = json.loads(sample['parsed_json']) if isinstance(sample['parsed_json'], str) else sample['parsed_json']
        original = json.loads(sample['parsed_json_original']) if isinstance(sample['parsed_json_original'], str) else sample['parsed_json_original']
        
        print(f"  Current supplier: {parsed.get('master', {}).get('supplier_name')}")
        print(f"  Original supplier: {original.get('master', {}).get('supplier_name')}")
