#!/usr/bin/env python3
"""Debug supplier name extraction step by step"""

import sys
import re

# Force reload
for mod in list(sys.modules.keys()):
    if 'backend' in mod:
        del sys.modules[mod]

from backend.text_correction import apply_text_corrections

# The actual OCR text
ocr_text = """AS
AHMEDSHARIF&BROS
LEMONPURCHASER&COMMAGENT
DARUSHAFAXROAD.HYDERABAD500024
Phone.040-24412139, 9949.00 3337.86
VoucherNumber214
YoucherDate 26/04/2024
TK
SuppNane
SrandTotal dealtge
Total 8 14580oO0
-: Comm?400: S832n
-- Less For Damages POQOn
- UnLoading S842
l4 0.00
L-FAndCash 44008.00"""

# Apply corrections
corrected = apply_text_corrections(ocr_text)

# Split into lines
lines = [ln.strip() for ln in corrected.splitlines() if ln.strip()]

print("=== LINES ===")
for i, line in enumerate(lines):
    print(f"Line {i}: {repr(line)}")

print("\n=== CHECKING SUPPLIER LOGIC ===\n")

supplier_name = None

for i, ln in enumerate(lines):
    print(f"Processing line {i}: {repr(ln)}")
    
    # Check for exact match
    pattern1 = re.compile(r"(?:Supp|SUPP)\s*(?:Name|NAME|Nam[3e])?\s*[:\-\s]\s+(.+)", re.IGNORECASE)
    match1 = pattern1.search(ln)
    if match1:
        print(f"  -> Matches exact pattern, group(1)='{match1.group(1)}'")
        supplier_name = match1.group(1).strip()
        break
    
    # Check for standalone "Supp Name"
    pattern2 = re.compile(r"^(?:Supp|SUPP)\s*(?:Name|NAME|Nam[3e])?\s*$", re.IGNORECASE)
    match2 = pattern2.search(ln)
    if match2:
        print(f"  -> Matches standalone 'Supp Name' pattern")
        
        # Check previous line
        if i > 0:
            prev_ln = lines[i - 1].strip()
            print(f"     Previous line {i-1}: {repr(prev_ln)}")
            
            # Validation
            if prev_ln and len(prev_ln) >= 2 and len(prev_ln) <= 100:
                print(f"     - Length check: OK ({len(prev_ln)} chars)")
                
                if not re.search(r"^(?:Total|Qty|Price|Amount|Date|Voucher|Phone)", prev_ln, re.IGNORECASE):
                    print(f"     - Pattern check: OK (not a label)")
                    supplier_name = prev_ln
                    print(f"     -> Using previous line as supplier: '{supplier_name}'")
                    break
                else:
                    print(f"     - Pattern check: FAILED (matches known label pattern)")
            else:
                print(f"     - Length check: FAILED")
        
        # Check next line if previous didn't work
        if supplier_name is None and i + 1 < len(lines):
            next_ln = lines[i + 1].strip()
            print(f"     Next line {i+1}: {repr(next_ln)}")
            
            if next_ln and len(next_ln) >= 2 and len(next_ln) <= 100:
                print(f"     - Length check: OK ({len(next_ln)} chars)")
                
                if not re.search(r"^(?:Total|Qty|Price|Amount|Supp|Date|Voucher)", next_ln, re.IGNORECASE):
                    print(f"     - Pattern check: OK (not a label)")
                    supplier_name = next_ln
                    print(f"     -> Using next line as supplier: '{supplier_name}'")
                    break
                else:
                    print(f"     - Pattern check: FAILED (matches known label pattern)")
            else:
                print(f"     - Length check: FAILED")

print(f"\n=== FINAL RESULT ===")
print(f"Supplier Name: {repr(supplier_name)}")
if supplier_name == 'TK':
    print("✅ CORRECT")
else:
    print("❌ WRONG")
