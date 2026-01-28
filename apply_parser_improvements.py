"""
Script to apply parser improvements to parser.py
Handles Windows line endings correctly
"""

import re

# Read the file
with open('backend/parser.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Change 1: Add commission percentage handling
# Find the location after "if not clean_ln: continue"
pattern1 = r'(if not clean_ln: continue\r?\n)'
replacement1 = r'''\1
            # IMPROVEMENT: Handle commission percentage pattern "Comm @ ? 4.00 %"
            comm_percentage_match = re.search(r'Comm.*?(\\d+\\.?\\d*)\\s*%', clean_ln, re.IGNORECASE)
            if comm_percentage_match:
                percentage = safe_float_conversion(comm_percentage_match.group(1))
                if percentage and data.get("gross_total"):
                    amount = data["gross_total"] * (percentage / 100)
                    data["deductions"].append({
                        "deduction_type": f"Commission @ {percentage}%",
                        "amount": amount
                    })
                    continue

'''

content = re.sub(pattern1, replacement1, content, count=1)

# Change 2: Replace the post-processing comment with calculations
pattern2 = r'# --- Post-Processing Calculations ---\r?\n\s*# REMOVED:.*?\r?\n\s*# We only return what we explicitly found in the text\.'
replacement2 = '''# --- Post-Processing Calculations ---
    # IMPROVEMENT: Calculate missing totals from items/deductions (fallback only)
    
    # Calculate total_deductions if missing
    if data["total_deductions"] is None and data["deductions"]:
        data["total_deductions"] = sum(ded.get("amount", 0) for ded in data["deductions"])
    
    # Calculate gross_total if missing (from items)
    if data["gross_total"] is None and data["items"]:
        data["gross_total"] = sum(item.get("line_amount", 0) for item in data["items"])
    
    # Calculate net_total if missing
    if data["net_total"] is None:
        if data["gross_total"] is not None and data["total_deductions"] is not None:
            data["net_total"] = data["gross_total"] - data["total_deductions"]
        elif data["gross_total"] is not None:
            # No deductions found, net = gross
            data["net_total"] = data["gross_total"]'''

content = re.sub(pattern2, replacement2, content, flags=re.DOTALL)

# Write back
with open('backend/parser.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Parser improvements applied successfully!")
print("Changes made:")
print("1. Added commission percentage pattern extraction")
print("2. Added total calculation fallback")
