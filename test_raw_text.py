import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(r'C:\Users\ramst\Documents\apps\tkfl_ocr\pt5\.env')

conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

# Get 3 recent vouchers with raw text but poor parsing
cur.execute('''
    SELECT id, file_name, raw_ocr_text, parsed_json 
    FROM vouchers_master 
    WHERE raw_ocr_text IS NOT NULL 
    ORDER BY created_at DESC 
    LIMIT 3
''')

rows = cur.fetchall()
results = []
for row in rows:
    vid, fname, text, parsed = row
    results.append({
        "voucher_id": vid,
        "filename": fname,
        "raw_text": text,
        "parsed_json": parsed
    })

import json
with open("raw_text_output.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=4)

conn.close()
