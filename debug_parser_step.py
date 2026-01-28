#!/usr/bin/env python3
"""
Debug the parser step by step to understand why AS is being extracted.
"""

import json
import re
from datetime import datetime

# Load data
with open('backend/data/queue_store.json', 'r') as f:
    queue_data = json.load(f)

batch_id = 'c4d2fb03-1b9b-4143-96f6-8ddbf0528b45'
batch = queue_data[batch_id]
file_info = batch['files'][1]  # IMG-20240426-WA0033.jpg

ocr_result = file_info.get('ocr_result') or {}
raw_text = ocr_result.get('text', '')

from backend.text_correction import apply_text_corrections
corrected_text = apply_text_corrections(raw_text)

text = corrected_text or ""
lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

# Simulate parser logic
RE_SUPPLIER_PREFIX = re.compile(r"(?:Supp|SUPP)\s*(?:Name|NAME|Nam[3e])?\s*[:\-\s]\s+(.+)", re.IGNORECASE)

data = {
    "supplier_name": None,
}

print("=" * 100)
print("STEP-BY-STEP PARSER SIMULATION")
print("=" * 100)

for i, ln in enumerate(lines[:15]):
    print(f"\nLine {i}: '{ln}'")
    
    # Check 2: Supplier Name
    if data["supplier_name"] is None:
        print(f"  [Check] supplier_name is None, evaluating...")
        
        # Try exact match first
        sn = RE_SUPPLIER_PREFIX.search(ln)
        if sn:
            print(f"  ✓ RE_SUPPLIER_PREFIX matched! Groups: {sn.groups()}")
            supplier_raw = sn.group(1).strip()
            supplier_raw = re.sub(r"^None\s+", "", supplier_raw, flags=re.IGNORECASE)
            if supplier_raw and len(supplier_raw) >= 1:
                data["supplier_name"] = supplier_raw
                print(f"  → SET supplier_name = '{supplier_raw}'")
        else:
            print(f"  ✗ RE_SUPPLIER_PREFIX did NOT match")
            
            # Check if line is just "Supp Name"
            if re.search(r"^(?:Supp|SUPP)\s*(?:Name|NAME|Nam[3e])?\s*$", ln, re.IGNORECASE):
                print(f"  ✓ Line is standalone 'Supp Name'")
                
                # First try PREVIOUS line
                if i > 0:
                    prev_ln = lines[i - 1].strip()
                    print(f"    Previous line: '{prev_ln}'")
                    if prev_ln and len(prev_ln) >= 2 and len(prev_ln) <= 100:
                        if not re.search(r"^(?:Total|Qty|Price|Amount|Date|Voucher|Phone)", prev_ln, re.IGNORECASE):
                            data["supplier_name"] = prev_ln
                            print(f"    → SET supplier_name = '{prev_ln}' (from previous line)")
                        else:
                            print(f"    ✗ Previous line rejected (matches label pattern)")
                    else:
                        print(f"    ✗ Previous line rejected (length validation)")
                
                # If not found in previous line, try NEXT line
                if data["supplier_name"] is None and i + 1 < len(lines):
                    next_ln = lines[i + 1].strip()
                    print(f"    Next line: '{next_ln}'")
                    if next_ln and len(next_ln) >= 2 and len(next_ln) <= 100:
                        if not re.search(r"^(?:Total|Qty|Price|Amount|Supp|Date|Voucher)", next_ln, re.IGNORECASE):
                            data["supplier_name"] = next_ln
                            print(f"    → SET supplier_name = '{next_ln}' (from next line)")
                        else:
                            print(f"    ✗ Next line rejected (matches label pattern)")
                    else:
                        print(f"    ✗ Next line rejected (length validation)")
            else:
                print(f"  ✗ Line is not standalone 'Supp Name'")
    else:
        print(f"  [Skip] supplier_name already set to '{data['supplier_name']}'")

print(f"\n{'='*100}")
print(f"FINAL RESULT: supplier_name = '{data['supplier_name']}'")
print(f"{'='*100}")
