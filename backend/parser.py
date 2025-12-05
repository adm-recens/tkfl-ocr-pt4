print(f"[DEBUG] Loaded parser.py from: {__file__}, module: {__name__}")
# backend/parser.py
import re
from datetime import datetime

# --- Helper Function for Safe Float Conversion ---
def safe_float_conversion(value):
    """Safely converts a string to float, returning None if empty, None, or invalid."""
    if value is None:
        return None
    try:
        # Remove commas, spaces, and handle '?' or other noise
        cleaned = re.sub(r'[^\d.-]', '', str(value))
        if not cleaned:
            return None
        return float(cleaned)
    except ValueError:
        return None

def get_float_or_zero(value):
    result = safe_float_conversion(value)
    return result if result is not None else 0.0

def try_parse_date(token):
    """Try several date formats; return DD-MM-YYYY or None."""
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(token, fmt)
            return dt.strftime("%d-%m-%Y")
        except Exception:
            continue
    # try contiguous 8 digits DDMMYYYY
    m = re.fullmatch(r"(\d{2})(\d{2})(\d{4})", token)
    if m:
        d, mo, y = m.groups()
        try:
            return datetime(int(y), int(mo), int(d)).strftime("%d-%m-%Y")
        except Exception:
            return None
    return None

def parse_receipt_text(ocr_text: str) -> dict:
    """
    Advanced parser with state-based logic for deductions and flexible regex.
    """
    text = ocr_text or ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    data = {
        "voucher_number": None,
        "voucher_date": None,
        "supplier_name": None,
        "vendor_details": None,
        "gross_total": None,
        "total_deductions": None,
        "net_total": None,
        "items": [],
        "deductions": []
    }

    # --- Regex Patterns ---
    
    # Item Pattern 1: Name (text) + Qty (num) + Price (num) + Amount (num)
    item_pattern_named = re.compile(
        r"(.+?)\s+(\d{1,6}(?:[,.]?\d{1,6})?)\s+(\d{1,6}(?:[,.]?\d{1,6})?)\s+([0-9,.]+)$"
    )
    
    # Item Pattern 2: Qty (num) + Price (num) + Amount (num) (No Name)
    # Matches: "13 920.00 11960.00"
    # Added ^\s* to handle indentation if strip() wasn't enough (though we strip lines, internal spaces matter)
    item_pattern_unnamed = re.compile(
        r"^(\d{1,6}(?:[,.]?\d{1,6})?)\s+(\d{1,6}(?:[,.]?\d{1,6})?)\s+([0-9,.]+)$"
    )

    # Deduction Start Keywords
    deduction_start_pattern = re.compile(r"^(?:Less|Deductions?|Ded|Less\s*:|Deductions\s*:|\(-\))", re.IGNORECASE)
    
    # Deduction Keywords
    deduction_keywords = re.compile(
        r"(Comm|Damages?|Unloading|L\s*/?\s*F|Cash|Tax|VAT|Discount|Fee|Charge|Other)", 
        re.IGNORECASE
    )

    # State flags
    in_deduction_section = False
    
    # --- Pass 1: Global Fields & Structure ---
    for i, ln in enumerate(lines):
        
        # 1. Vendor Name (Top of receipt)
        if i < 5 and data["vendor_details"] is None:
            if len(ln) > 4 and not re.search(r"Date|Voucher|Inv|No\.|^\d+$", ln, re.IGNORECASE):
                if ln.isupper() or re.search(r"(Store|Traders|Bros|Company|Ltd|Ent|Sons)", ln, re.IGNORECASE):
                    data["vendor_details"] = ln

        # 2. Supplier Name
        if data["supplier_name"] is None:
            sn = re.search(r"(?:SUPP|Supplier)\s*(?:NAME|Name)?\s*[:\-\s]\s*(.+)", ln, re.IGNORECASE)
            if sn:
                supplier_raw = sn.group(1).strip()
                # Clean up "None" prefix if present
                supplier_raw = re.sub(r"^None\s+", "", supplier_raw, flags=re.IGNORECASE)
                if supplier_raw and len(supplier_raw) >= 1:
                    data["supplier_name"] = supplier_raw

        # 3. Voucher Number
        if data["voucher_number"] is None:
            vn = re.search(r"(?:Voucher|Invoice|Bill|Vouch|Inv)\s*(?:No|Number|Num|#)?\s*[:\-]?\s*[#]?(\d+)", ln, re.IGNORECASE)
            if vn:
                data["voucher_number"] = vn.group(1)
            else:
                vn_fallback = re.search(r"No\s*[:\-.]\s*(\d{3,})", ln, re.IGNORECASE)
                if vn_fallback:
                    data["voucher_number"] = vn_fallback.group(1)

        # 4. Date
        if data["voucher_date"] is None:
            dt = re.search(r"(?:Date|DATED|Dt)\s*[:\-]?\s*([\d/\.\-]+)", ln, re.IGNORECASE)
            if dt:
                parsed_date = try_parse_date(dt.group(1))
                if parsed_date:
                    data["voucher_date"] = parsed_date
            else:
                dt_standalone = re.search(r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", ln)
                if dt_standalone:
                     parsed_date = try_parse_date(dt_standalone.group(1))
                     if parsed_date:
                        data["voucher_date"] = parsed_date

        # 5. Totals (Gross/Net)
        # Net Total - Look for "Grand Total" or "Net Total"
        gm = re.search(r"(?:Net\s*Total|NetTotal|Net\s*Amount|Net\s*Payable|Payable|Grand\s*Total)\s*[:\-]?\s*([0-9,.]+)", ln, re.IGNORECASE)
        if gm:
            data["net_total"] = safe_float_conversion(gm.group(1))

        # Gross Total - Look for "Total" (if not Grand Total) or "Gross Total"
        # If line starts with "Total" and has a number, and NOT "Grand Total"
        if re.match(r"^Total\s*[:\-]?\s*\d*\s*([0-9,.]+)", ln, re.IGNORECASE) and not re.search(r"Grand", ln, re.IGNORECASE):
             # Matches "Total 23 15640.00" -> group 1 is 15640.00
             # We need to be careful. regex above might grab 23.
             # Let's use rsplit for "Total" lines to get the last number
             parts = ln.rsplit(None, 1)
             if len(parts) == 2:
                 val = safe_float_conversion(parts[1])
                 if val and val > 10: # Threshold to avoid grabbing small numbers
                     data["gross_total"] = val
        
        gm2 = re.search(r"(?:Gross\s*Total|Gross|GrossTotal|Sub\s*Total|SubTotal)\s*[:\-]?\s*([0-9,.]+)", ln, re.IGNORECASE)
        if gm2:
             data["gross_total"] = safe_float_conversion(gm2.group(1))


        # --- Section Detection ---
        # Check for "(-)" or "Less:"
        if deduction_start_pattern.search(ln):
            in_deduction_section = True
            # Don't skip if it contains data (like "(-) Comm...")
            # If it's JUST a header (no digits), skip.
            if not re.search(r"\d", ln):
                continue
        
        if re.search(r"Net\s*Total|Grand\s*Total", ln, re.IGNORECASE):
            in_deduction_section = False

        # --- Line Item & Deduction Parsing ---
        
        if in_deduction_section:
            # Clean up "(-)" prefix
            clean_ln = ln.replace("(-)", "").strip()
            if not clean_ln: continue

            # Strategy: Look for the LAST number on the line as the amount
            parts = clean_ln.rsplit(None, 1) # Split from right, max 1 split
            if len(parts) == 2:
                label_candidate = parts[0].strip()
                amount_candidate = parts[1].strip()
                
                amount = safe_float_conversion(amount_candidate)
                
                if amount is not None:
                    if deduction_keywords.search(label_candidate):
                        data["deductions"].append({"deduction_type": label_candidate, "amount": amount})
                    elif not label_candidate or len(label_candidate) < 3:
                        data["deductions"].append({"deduction_type": "Other", "amount": amount})
                    else:
                        # Assume it's a deduction label we don't know
                        data["deductions"].append({"deduction_type": label_candidate, "amount": amount})
            elif len(parts) == 1:
                # Just a number?
                amount = safe_float_conversion(parts[0])
                if amount is not None:
                    data["deductions"].append({"deduction_type": "Other", "amount": amount})

        else:
            # Try parsing as Item
            if re.search(r"Total|Amount|Price|Qty|Voucher|Date|Supp", ln, re.IGNORECASE):
                continue
                
            # Try Unnamed Pattern first (Qty Price Amount)
            im_unnamed = item_pattern_unnamed.search(ln)
            if im_unnamed:
                qty = safe_float_conversion(im_unnamed.group(1))
                price = safe_float_conversion(im_unnamed.group(2))
                amt = safe_float_conversion(im_unnamed.group(3))
                
                if amt is not None and amt > 0:
                     data["items"].append({
                        "item_name": "Item", # Default name
                        "quantity": qty,
                        "unit_price": price,
                        "line_amount": amt
                    })
                     continue

            # Try Named Pattern
            im = item_pattern_named.search(ln)
            if im:
                item_name = im.group(1).strip()
                qty = safe_float_conversion(im.group(2))
                price = safe_float_conversion(im.group(3))
                amt = safe_float_conversion(im.group(4))
                
                if amt is not None and amt > 0:
                     data["items"].append({
                        "item_name": item_name,
                        "quantity": qty,
                        "unit_price": price,
                        "line_amount": amt
                    })

    # --- Post-Processing Calculations ---
    # REMOVED: User requested to avoid math at parsing stage. 
    # We only return what we explicitly found in the text.

    return {
        "master": {
            "voucher_number": data["voucher_number"],
            "voucher_date": data["voucher_date"],
            "supplier_name": data["supplier_name"],
            "vendor_details": data["vendor_details"],
            "gross_total": data["gross_total"],
            "total_deductions": data["total_deductions"],
            "net_total": data["net_total"],
        },
        "items": data["items"],
        "deductions": data["deductions"]
    }
