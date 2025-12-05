print(f"[DEBUG] Loaded parser_beta.py from: {__file__}, module: {__name__}")
# backend/parser_beta.py - Enhanced parser with fuzzy matching
import re
from datetime import datetime
from difflib import SequenceMatcher

# --- Helper Functions ---

def fuzzy_match(text, keyword, threshold=0.75):
    """
    Fuzzy match text against keyword to handle OCR errors.
    Returns True if similarity >= threshold.
    
    Examples:
        fuzzy_match("Vouchcr", "Voucher") -> True
        fuzzy_match("V0ucher", "Voucher") -> True
        fuzzy_match("Dat3", "Date") -> True
    """
    if not text or not keyword:
        return False
    return SequenceMatcher(None, text.lower(), keyword.lower()).ratio() >= threshold

def extract_number(text):
    """
    Extract number from noisy text, handling OCR errors and Indian number format.
    
    Examples:
        extract_number("1,23,456.00") -> 123456.00
        extract_number("Total:  15640.00") -> 15640.00
        extract_number("₹ 1 2 3 4") -> 1234.0
    """
    if not text:
        return None
    
    # Remove everything except digits, dots, commas, minus
    cleaned = re.sub(r'[^\d.,-]', '', str(text))
    
    # Remove commas (Indian number format: 1,23,456.00)
    cleaned = cleaned.replace(',', '')
    
    # Handle multiple dots (keep only last one as decimal point)
    parts = cleaned.split('.')
    if len(parts) > 2:
        cleaned = ''.join(parts[:-1]) + '.' + parts[-1]
    
    if not cleaned or cleaned == '.':
        return None
    
    try:
        return float(cleaned)
    except ValueError:
        return None

def safe_float_conversion(value):
    """Safely converts a string to float, returning None if empty, None, or invalid."""
    if value is None:
        return None
    return extract_number(value)

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

        # 3. Voucher Number (with fuzzy matching)
        if data["voucher_number"] is None:
            # Try exact match first
            vn = re.search(r"(?:Voucher|Invoice|Bill|Vouch|Inv)\s*(?:No|Number|Num|#)?\s*[:\-]?\s*[#]?(\d+)", ln, re.IGNORECASE)
            if vn:
                data["voucher_number"] = vn.group(1)
            else:
                # Try fuzzy matching for OCR errors
                words = ln.split()
                for i, word in enumerate(words):
                    if fuzzy_match(word, "Voucher") or fuzzy_match(word, "Invoice") or fuzzy_match(word, "Bill"):
                        # Look for number in next few words
                        for j in range(i+1, min(i+4, len(words))):
                            num_match = re.search(r'(\d{3,})', words[j])
                            if num_match:
                                data["voucher_number"] = num_match.group(1)
                                break
                        break
                
                # Fallback pattern
                if data["voucher_number"] is None:
                    vn_fallback = re.search(r"No\s*[:\-.]\s*(\d{3,})", ln, re.IGNORECASE)
                    if vn_fallback:
                        data["voucher_number"] = vn_fallback.group(1)

        # 4. Date (with fuzzy matching)
        if data["voucher_date"] is None:
            # Try exact match first
            dt = re.search(r"(?:Date|DATED|Dt)\s*[:\-]?\s*([\d/\.\-]+)", ln, re.IGNORECASE)
            if dt:
                parsed_date = try_parse_date(dt.group(1))
                if parsed_date:
                    data["voucher_date"] = parsed_date
            else:
                # Try fuzzy matching for "Date"
                words = ln.split()
                for i, word in enumerate(words):
                    if fuzzy_match(word, "Date") or fuzzy_match(word, "Dated"):
                        # Look for date pattern in next few words
                        for j in range(i+1, min(i+3, len(words))):
                            date_match = re.search(r'([\d/\-\.]+)', words[j])
                            if date_match:
                                parsed_date = try_parse_date(date_match.group(1))
                                if parsed_date:
                                    data["voucher_date"] = parsed_date
                                    break
                        break
                
                # Fallback: standalone date pattern
                if data["voucher_date"] is None:
                    dt_standalone = re.search(r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", ln)
                    if dt_standalone:
                        parsed_date = try_parse_date(dt_standalone.group(1))
                        if parsed_date:
                            data["voucher_date"] = parsed_date

        # 5. Totals (Gross/Net) with fuzzy matching and better number extraction
        
        # Net Total - Look for "Grand Total" or "Net Total"
        gm = re.search(r"(?:Net\s*Total|NetTotal|Net\s*Amount|Net\s*Payable|Payable|Grand\s*Total)\s*[:\-]?\s*([0-9,.\s]+)", ln, re.IGNORECASE)
        if gm:
            data["net_total"] = extract_number(gm.group(1))
        else:
            # Fuzzy match for "Net" or "Grand"
            words = ln.split()
            for i, word in enumerate(words):
                if (fuzzy_match(word, "Net") or fuzzy_match(word, "Grand")) and i + 1 < len(words):
                    if fuzzy_match(words[i+1], "Total"):
                        # Extract number from rest of line
                        rest = ' '.join(words[i+2:])
                        num = extract_number(rest)
                        if num and num > 10:
                            data["net_total"] = num
                        break

        # Gross Total - Look for "Total" (if not Grand Total) or "Gross Total"
        if re.match(r"^Total\s*[:\-]?\s*\d*\s*([0-9,.\s]+)", ln, re.IGNORECASE) and not re.search(r"Grand|Net", ln, re.IGNORECASE):
             # Use rsplit to get the last number
             parts = ln.rsplit(None, 1)
             if len(parts) == 2:
                 val = extract_number(parts[1])
                 if val and val > 10: # Threshold to avoid grabbing small numbers
                     data["gross_total"] = val
        
        gm2 = re.search(r"(?:Gross\s*Total|Gross|GrossTotal|Sub\s*Total|SubTotal)\s*[:\-]?\s*([0-9,.\s]+)", ln, re.IGNORECASE)
        if gm2:
             data["gross_total"] = extract_number(gm2.group(1))
        
        # Total Deductions - explicit extraction
        td = re.search(r"(?:Total\s*Deductions?|Deductions?\s*Total)\s*[:\-]?\s*([0-9,.\s]+)", ln, re.IGNORECASE)
        if td:
            data["total_deductions"] = extract_number(td.group(1))


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
    
    # Calculate total_deductions if not found but deductions exist
    if data["total_deductions"] is None and data["deductions"]:
        data["total_deductions"] = sum(d["amount"] for d in data["deductions"] if d["amount"])
    
    # Validate totals: gross_total - total_deductions should ≈ net_total
    validation_warnings = []
    if all([data["gross_total"], data["total_deductions"], data["net_total"]]):
        calculated_net = data["gross_total"] - data["total_deductions"]
        difference = abs(calculated_net - data["net_total"])
        if difference > 1.0:  # Allow 1 rupee tolerance for rounding
            validation_warnings.append(f"Totals mismatch: {data['gross_total']} - {data['total_deductions']} ≠ {data['net_total']} (diff: {difference:.2f})")
    
    # Calculate parse confidence score
    confidence_score = 0
    max_score = 0
    
    # Critical fields (20 points each)
    for field in ['voucher_number', 'voucher_date', 'net_total']:
        max_score += 20
        if data[field]:
            confidence_score += 20
    
    # Important fields (10 points each)
    for field in ['supplier_name', 'vendor_details', 'gross_total']:
        max_score += 10
        if data[field]:
            confidence_score += 10
    
    # Items (20 points if any, up to 20)
    max_score += 20
    if data['items']:
        confidence_score += min(20, len(data['items']) * 5)
    
    # Deductions (10 points if any)
    max_score += 10
    if data['deductions']:
        confidence_score += 10
    
    parse_confidence = (confidence_score / max_score) * 100 if max_score > 0 else 0

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
        "deductions": data["deductions"],
        "metadata": {
            "parse_confidence": round(parse_confidence, 2),
            "validation_warnings": validation_warnings
        }
    }
