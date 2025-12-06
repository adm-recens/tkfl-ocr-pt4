print(f"[DEBUG] Loaded parser_beta.py from: {__file__}, module: {__name__}")
# backend/parser_beta.py - Enhanced parser with fuzzy matching
import re
from datetime import datetime
from difflib import SequenceMatcher

import json
import os

# --- Helper Functions ---

# --- Compiled Regex Patterns ---
# Pre-compile patterns at module level for performance

# Item Pattern 1: Name (text) + Qty (num) + Price (num) + Amount (num)
ITEM_PATTERN_NAMED = re.compile(
    r"(.+?)\s+(\d{1,6}(?:[,.]?\d{1,6})?)\s+(\d{1,6}(?:[,.]?\d{1,6})?)\s+([0-9,.]+)$"
)

# Item Pattern 2: Qty (num) + Price (num) + Amount (num) (No Name)
ITEM_PATTERN_UNNAMED = re.compile(
    r"^(\d{1,6}(?:[,.]?\d{1,6})?)\s+(\d{1,6}(?:[,.]?\d{1,6})?)\s+([0-9,.]+)$"
)

# Deduction Start Keywords
DEDUCTION_START_PATTERN = re.compile(r"^(?:Less|Deductions?|Ded|Less\s*:|Deductions\s*:|\(-\))", re.IGNORECASE)

# Deduction Keywords
DEDUCTION_KEYWORDS = re.compile(
    r"(Comm|Damages?|Unloading|L\s*/?\s*F|Cash|Tax|VAT|Discount|Fee|Charge|Other)", 
    re.IGNORECASE
)

# Field Specific Regexes
RE_DATE_KEY = re.compile(r"(?:Date|DATED|Dt)\s*[:\-]?\s*([\d/\.\-]+)", re.IGNORECASE)
RE_DATE_STANDALONE = re.compile(r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})")

RE_VOUCHER_EXACT = re.compile(r"(?:Voucher|Invoice|Bill|Vouch|Inv)\s*(?:No|Number|Num|#)?\s*[:\-]?\s*[#]?(\d+)", re.IGNORECASE)
RE_VOUCHER_FALLBACK = re.compile(r"No\s*[:\-.]\s*(\d{3,})", re.IGNORECASE)

RE_SUPPLIER_PREFIX = re.compile(r"(?:SUPP|Supplier)\s*(?:NAME|Name)?\s*[:\-\s]\s*(.+)", re.IGNORECASE)
RE_VENDOR_KEYWORDS = re.compile(r"(Store|Traders|Bros|Company|Ltd|Ent|Sons)", re.IGNORECASE)

RE_NET_TOTAL = re.compile(r"(?:Net\s*Total|NetTotal|Net\s*Amount|Net\s*Payable|Payable|Grand\s*Total)\s*[:\-]?\s*([0-9,.\s]+)", re.IGNORECASE)
RE_GROSS_TOTAL_KEY = re.compile(r"(?:Gross\s*Total|Gross|GrossTotal|Sub\s*Total|SubTotal)\s*[:\-]?\s*([0-9,.\s]+)", re.IGNORECASE)
RE_TOTAL_STRICT = re.compile(r"^Total\s*[:\-]?\s*\d*\s*([0-9,.\s]+)", re.IGNORECASE)
RE_TOTAL_DEDUCTIONS = re.compile(r"(?:Total\s*Deductions?|Deductions?\s*Total)\s*[:\-]?\s*([0-9,.\s]+)", re.IGNORECASE)

RE_SKIP_KEYWORDS = re.compile(r"Date|Voucher|Inv|No\.|^\d+$", re.IGNORECASE)
RE_ITEM_HEADER = re.compile(r"Total|Amount|Price|Qty|Voucher|Date|Supp", re.IGNORECASE)

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

def load_vendor_dictionary():
    """Load known vendors from JSON."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base_dir, 'data', 'vendors.json')
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                data = json.load(f)
                return data.get('vendors', [])
    except Exception as e:
        print(f"[WARN] Failed to load vendors.json: {e}")
    return []

def fix_vendor_name(ocr_name):
    """
    Match OCR vendor name against dictionary.
    Example: 'Aman Trcders' -> 'Aman Traders'
    """
    if not ocr_name or len(ocr_name) < 4:
        return ocr_name
        
    vendors = load_vendor_dictionary()
    best_match = None
    best_score = 0
    
    for v in vendors:
        score = SequenceMatcher(None, ocr_name.lower(), v.lower()).ratio()
        if score > best_score:
            best_score = score
            best_match = v
            
    # If high similarity (> 0.8), correct it
    if best_score > 0.82:
        return best_match
    return ocr_name

def clean_amount(text_value):
    """
    Enhanced amount cleaning: swaps common OCR alpha-for-digit errors.
    Examples: 'l23' -> 123, 'S0.00' -> 50.00, '2O0' -> 200
    """
    if not text_value:
        return None
        
    val_str = str(text_value).strip().upper()
    
    # Common substitutions
    subs = {
        'O': '0', 'D': '0', 'Q': '0',
        'I': '1', 'L': '1', '|': '1', '!': '1',
        'Z': '2',
        'S': '5', '$': '5',
        'B': '8', '&': '8',
        'G': '6'
    }
    
    # Only substitute if it helps shape it into a number
    # If it's already a valid number, don't mess with it
    if extract_number(val_str) is not None:
        return extract_number(val_str)

    cleaned = ""
    for char in val_str:
        cleaned += subs.get(char, char)
        
    return extract_number(cleaned)

def validate_and_correct(data):
    """
    Phase 4: logical validation and auto-correction.
    Rules:
    1. Sum(Items) should approx equal Gross Total
    2. Gross - Deductions should approx equal Net Total
    3. Auto-fix missing fields if math allows
    """
    warnings = []
    corrections = []
    
    # Safe retrieval
    gross = get_float_or_zero(data.get('gross_total'))
    deductions = get_float_or_zero(data.get('total_deductions'))
    net = get_float_or_zero(data.get('net_total'))
    
    items = data.get('items', [])
    items_total = sum(get_float_or_zero(i.get('line_amount')) for i in items)
    
    # Rule 1: Sum(Items) vs Gross
    # If we have items but no gross, fill it
    if items and not gross:
        data['gross_total'] = items_total
        gross = items_total
        corrections.append(f"Derived Gross Total ({items_total}) from sum of items")
    elif items and gross > 0:
        # Check consistency (allow 1.0 diff)
        if abs(items_total - gross) > 5.0: # 5.0 tolerance for OCR noise
            warnings.append(f"Sum of items ({items_total}) mismatches Gross Total ({gross})")
            
            # Auto-correct preference: Trust Sum(Items) if it matches Net+Deductions
            if net > 0 and abs(items_total - (net + deductions)) < 1.0:
                 data['gross_total'] = items_total
                 gross = items_total
                 corrections.append(f"Auto-corrected Gross Total to matches Item Sum ({items_total})")

    # Rule 2: Gross - Deductions = Net
    # Case A: Have Gross & Deductions, missing Net
    if gross > 0 and not net:
        data['net_total'] = gross - deductions
        net = data['net_total']
        corrections.append(f"Derived Net Total ({net}) from Gross - Deductions")
        
    # Case B: Have Net & Deductions, missing Gross
    if net > 0 and deductions > 0 and not gross:
        data['gross_total'] = net + deductions
        gross = data['gross_total']
        corrections.append(f"Derived Gross Total ({gross}) from Net + Deductions")

    # Case C: Have all 3, check math
    if gross > 0 and net > 0:
        calc_net = gross - deductions
        if abs(calc_net - net) > 1.0:
            warnings.append(f"Math Error: {gross} - {deductions} = {calc_net}, but extracted Net is {net}")
            
            # Simple heuristic: If Gross - Deductions equals sum of items, trust Gross
            if abs(gross - items_total) < 1.0:
                 # Trust Gross, mark Net as suspicious or correct it?
                 # Let's trust logic over OCR for Net
                 data['net_total'] = calc_net
                 corrections.append(f"Corrected Net Total to {calc_net} based on verified Gross")
    
    return data, warnings, corrections

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

    # State flags
    in_deduction_section = False
    
    # --- Pass 1: Global Fields & Structure ---
    for i, ln in enumerate(lines):
        
        # 1. Vendor Name (Top of receipt)
        # 1. Vendor Name (Top of receipt) - Only check top 5 lines
        if i < 5 and data["vendor_details"] is None:
            if len(ln) > 4 and not RE_SKIP_KEYWORDS.search(ln):
                if ln.isupper() or RE_VENDOR_KEYWORDS.search(ln):
                    data["vendor_details"] = ln

        # 2. Supplier Name
        if data["supplier_name"] is None:
            sn = RE_SUPPLIER_PREFIX.search(ln)
            if sn:
                supplier_raw = sn.group(1).strip()
                # Clean up "None" prefix if present
                supplier_raw = re.sub(r"^None\s+", "", supplier_raw, flags=re.IGNORECASE)
                if supplier_raw and len(supplier_raw) >= 1:
                    data["supplier_name"] = fix_vendor_name(supplier_raw)

        # 3. Voucher Number (with fuzzy matching)
        if data["voucher_number"] is None:
            # Try exact match first
            vn = RE_VOUCHER_EXACT.search(ln)
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
                    vn_fallback = RE_VOUCHER_FALLBACK.search(ln)
                    if vn_fallback:
                        data["voucher_number"] = vn_fallback.group(1)

        # 4. Date (with fuzzy matching)
        if data["voucher_date"] is None:
            # Try exact match first
            dt = RE_DATE_KEY.search(ln)
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
                    dt_standalone = RE_DATE_STANDALONE.search(ln)
                    if dt_standalone:
                        parsed_date = try_parse_date(dt_standalone.group(1))
                        if parsed_date:
                            data["voucher_date"] = parsed_date

        # 5. Totals (Gross/Net) with fuzzy matching and better number extraction
        
        # Net Total - Look for "Grand Total" or "Net Total"
        gm = RE_NET_TOTAL.search(ln)
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
        if RE_TOTAL_STRICT.match(ln) and not re.search(r"Grand|Net", ln, re.IGNORECASE):
             # Use rsplit to get the last number
             parts = ln.rsplit(None, 1)
             if len(parts) == 2:
                 val = extract_number(parts[1])
                 if val and val > 10: # Threshold to avoid grabbing small numbers
                     data["gross_total"] = val
        
        gm2 = RE_GROSS_TOTAL_KEY.search(ln)
        if gm2:
             data["gross_total"] = extract_number(gm2.group(1))
        
        # Total Deductions - explicit extraction
        td = RE_TOTAL_DEDUCTIONS.search(ln)
        if td:
            data["total_deductions"] = extract_number(td.group(1))


        # --- Section Detection ---
        # Check for "(-)" or "Less:"
        # --- Section Detection ---
        # Check for "(-)" or "Less:"
        if DEDUCTION_START_PATTERN.search(ln):
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
                    if DEDUCTION_KEYWORDS.search(label_candidate):
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
            if RE_ITEM_HEADER.search(ln):
                continue
                
            # Try Unnamed Pattern first (Qty Price Amount)
            im_unnamed = ITEM_PATTERN_UNNAMED.search(ln)
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
            im = ITEM_PATTERN_NAMED.search(ln)
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
        data["total_deductions"] = sum(get_float_or_zero(d["amount"]) for d in data["deductions"])

    # Phase 4: Run Validation & Correction Pipeline
    data, validation_warnings, corrections = validate_and_correct(data)
    
    # Store corrections in metadata for UI
    data['corrections'] = corrections
    
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
            "validation_warnings": validation_warnings,
            "corrections": data.get('corrections', [])
        }
    }
