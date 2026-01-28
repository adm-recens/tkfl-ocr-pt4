import re
from datetime import datetime

def clean_ocr_text(text):
    """
    Clean common OCR noise and normalize text.
    Removes non-ascii garbage, normalizes whitespace.
    """
    if not text:
        return ""
    # Remove weird OCR artifacts but keep basic punctuation
    text = re.sub(r'[^\x20-\x7E\n]', '', text) 
    # Normalize multiple spaces per line
    text = re.sub(r'[ \t]+', ' ', text)
    return text

def parse_header_region(text):
    """
    Parse header region to extract company name, voucher number, date, supplier.
    """
    data = {
        'vendor_details': None,
        'voucher_number': None,
        'voucher_date': None,
        'supplier_name': None
    }
    
    # Pre-clean text
    clean_text = clean_ocr_text(text)
    lines = [ln.strip() for ln in clean_text.splitlines() if ln.strip()]
    
    for i, ln in enumerate(lines):
        # Vendor name heuristics
        # Look for the first prominent line that looks like a business name
        if data['vendor_details'] is None:
            # Skip very short lines or likely labels
            if len(ln) > 4 and not re.search(r"(Date|Voucher|Supp|Phone|GST|Inv|No\.|:)", ln, re.IGNORECASE):
                # Check for business keywords or simply being the first few lines and uppercase-ish
                if (ln.isupper() or 
                    re.search(r"(Bros|Traders|Company|Ltd|Enterprises|Sons|Agent|Agency|Services)", ln, re.IGNORECASE)):
                     data['vendor_details'] = ln

        # Voucher number
        if data['voucher_number'] is None:
            vn = re.search(r"(?:Voucher)\s*(?:Number|No|#)?\s*[:\-\.]?\s*[#]?\s*(\d+)", ln, re.IGNORECASE)
            if vn:
                data['voucher_number'] = vn.group(1)
        
        # Voucher date
        if data['voucher_date'] is None:
            dt = re.search(r"(?:Voucher)\s*(?:Date|Dated|Dt)?\s*[:\-\.]?\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}|\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2})", ln, re.IGNORECASE)
            if dt:
                data['voucher_date'] = try_parse_date(dt.group(1))
        
        # Supplier name
        if data['supplier_name'] is None:
             # Be strict about supplier to avoid picking up vendor name parts
            if re.search(r"(?:M/s|Mr\.|Mrs\.|Shri|Sri)\b", ln, re.IGNORECASE):
                data['supplier_name'] = ln.strip()
            # Explicit label
            elif re.search(r"(?:Supp|SUPP)\s*(?:Name|NAME)?\s*[:\-\s]\s*(.+)", ln, re.IGNORECASE):
                sn = re.search(r"(?:Supp|SUPP)\s*(?:Name|NAME)?\s*[:\-\s]\s*(.+)", ln, re.IGNORECASE)
                if sn:
                    val = sn.group(1).strip()
                    # Determine if this captured the vendor name part by mistake (like "LEMON PURCHASER")
                    if "COMM AGENT" not in val: 
                        data['supplier_name'] = val
    
    return data

def parse_items_region(text):
    """
    Parse items table region to extract line items.
    """
    items = []
    clean_text = clean_ocr_text(text)
    lines = [ln.strip() for ln in clean_text.splitlines() if ln.strip()]
    
    # Regex for a line ending with an amount (number with optional decimals)
    # Strategy: Find the last number on the line, assume it's the Total Amount
    # Then look for the number before it as Price, and before that as Qty (optional)
    
    for ln in lines:
        # Skip likely header lines
        if re.search(r"^(Qty|Price|Amount|Item|Name|Total|Particulars)", ln, re.IGNORECASE):
            continue
        
        # Find all numbers in the line (allow commas or dots as decimal sep)
        number_tokens = re.findall(r"([\d,]+(?:[\.,]\d{1,2})?)", ln)
        
        if not number_tokens:
            continue
            
        # Try to interpret the last number as line amount (allow dividing by 100 if dot missing)
        line_amount = _parse_num_token(number_tokens[-1], allow_divide_by_100=True)
        if line_amount is None or line_amount <= 0:
            continue
            
        unit_price = None
        quantity = None
        item_name = "Item"
        
        # Heuristic: If we have at least 2 numbers, 2nd to last might be price or qty
        if len(number_tokens) >= 2:
            try:
                # Assuming simple format: [Name] [Qty] [Price] [Amount]
                # If 3 numbers: Qty, Price, Amount
                if len(number_tokens) >= 3:
                    # Qty is often integer - do not apply divide-by-100 heuristic
                    quantity = _parse_num_token(number_tokens[-3], allow_divide_by_100=False)
                    unit_price = _parse_num_token(number_tokens[-2], allow_divide_by_100=True)
                # If 2 numbers: Price, Amount (Qty assumed 1) OR Qty, Amount (Price inferred)
                elif len(number_tokens) == 2:
                    val = _parse_num_token(number_tokens[-2], allow_divide_by_100=True)
                    # Guess if it's price or qty based on division
                    if val is not None and abs(val * line_amount - line_amount) < 0.01: # Likely Qty=1
                         unit_price = val
                    elif val is not None and quantity is None and val != 0 and abs((line_amount / val) % 1) < 0.01: # Divides cleanly, maybe quantity
                         quantity = val
                         unit_price = line_amount / quantity
                    else:
                        unit_price = val # Assume Price
                        
            except:
                pass
                
        # Extract text part as Item Name (everything before the first significant number)
        # Find index of the first number used for stats
        match = re.search(r"\d", ln)
        if match and match.start() > 0:
            item_name = ln[:match.start()].strip()
            # Clean up item name
            item_name = re.sub(r"^\d+\s*\.?\s*", "", item_name) # Remove leading list numbers "1. Item"
            
        if not item_name or len(item_name) < 2:
            item_name = "Item"

        items.append({
            "item_name": item_name,
            "quantity": quantity,
            "unit_price": unit_price,
            "line_amount": line_amount
        })
    
    return items

def _normalize_num_str(s, allow_divide_by_100=False):
    """Normalize numeric OCR tokens into a standard float string.
    Handles commas as decimal separators, thousand separators, and common OCR artifacts.
    If allow_divide_by_100 is True and the token has no decimal point and is long (>=4),
    assume the last two digits are decimals (e.g. '5720' -> '57.20').
    """
    if not s:
        return None
    s = s.strip().replace(' ', '')
    # Replace common OCR dot-like characters
    s = re.sub(r'[·•‚]', '.', s)
    # If only commas and no dots, decide whether comma is decimal sep
    if ',' in s and '.' not in s:
        if re.search(r",\d{1,2}$", s):
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')
    # If both comma and dot present, remove commas (assume thousand separators)
    if ',' in s and '.' in s:
        s = s.replace(',', '')
    # Now if still no dot and heuristic allowed, try inserting decimal before last 2 digits
    if allow_divide_by_100 and '.' not in s and re.fullmatch(r'\d{4,}', s):
        s = s[:-2] + '.' + s[-2:]
    return s


def _parse_num_token(token, allow_divide_by_100=False):
    t = _normalize_num_str(token, allow_divide_by_100=allow_divide_by_100)
    if not t:
        return None
    try:
        return float(t)
    except:
        return None


def _clean_deduction_label(lbl):
    """Clean OCR noise in labels and strip trailing percentage or small numeric tokens that belong to label not amount.
    Examples: 'Comm?4.00' -> 'Comm' ; 'Commission 4%' -> 'Commission'
    """
    if not lbl:
        return lbl
    # Remove stray punctuation (keep dot so decimals remain intact for removal)
    lbl = re.sub(r'[\?\(\)\[\]]', ' ', lbl)
    # Remove one or more trailing numeric tokens or percentages (e.g. '4.00', '4 %', '4')
    lbl = re.sub(r"(?:\s+\d+(?:[\.,]\d+)?%?)+\s*$", '', lbl).strip()
    return lbl


def parse_deductions_region(text):
    """
    Parse deductions region.
    """
    deductions = []
    clean_text = clean_ocr_text(text)
    lines = [ln.strip() for ln in clean_text.splitlines() if ln.strip()]
    
    keywords = r"(Comm|Less|Damages?|Unloading|L/F|And|Cash|)"
    
    for ln in lines:
        # Try to find a trailing amount (allow comma or dot as decimal separator)
        pattern = rf"({keywords}.*?)\s*[:\-\s]\s*([\d,]+(?:[\.,]\d{{1,2}})?)$"
        match = re.search(pattern, ln, re.IGNORECASE)
        if match:
            lbl = _clean_deduction_label(match.group(1).strip())
            # Because 'keywords' contains its own capture group, the amount is in group 3
            amt = _parse_num_token(match.group(3), allow_divide_by_100=True)
            if amt is not None:
                deductions.append({
                    "deduction_type": lbl,
                    "amount": amt
                })
            continue
        else:
            # Debug: (temporary) show why some lines may not match during tests
            # print(f"[DEBUG parse_deductions_region] no match for line: '{ln}' with pattern: {pattern}")
            pass
            
        # Or Just "Commission 500" (last token numeric)
        parts = ln.rsplit(None, 1)
        if len(parts) == 2:
            amt = _parse_num_token(parts[1], allow_divide_by_100=True)
            lbl = _clean_deduction_label(parts[0])
            if amt is not None and re.search(keywords, lbl, re.IGNORECASE):
                deductions.append({
                    "deduction_type": lbl.strip(),
                    "amount": amt
                })
                
    return deductions

def parse_totals_region(text):
    """
    Parse totals region.
    """
    totals = {
        'gross_total': None,
        'total_deductions': None,
        'net_total': None
    }
    
    clean_text = clean_ocr_text(text)
    lines = [ln.strip() for ln in clean_text.splitlines() if ln.strip()]
    
    for ln in lines:
        # Net Total / Grand Total
        if re.search(r"(Grand|Net|Payable|Bill)\s*(?:Total|Amt|Amount)?", ln, re.IGNORECASE):
            # Extract last number (allow comma/dot decimals)
            nums = re.findall(r"([\d,]+(?:[\.,]\d{1,2})?)", ln)
            if nums:
                totals['net_total'] = _parse_num_token(nums[-1], allow_divide_by_100=True)
        
        # Gross Total
        elif re.search(r"(Gross|Total)", ln, re.IGNORECASE) and not re.search(r"(Net|Grand|Deduc)", ln, re.IGNORECASE):
             nums = re.findall(r"([\d,]+(?:[\.,]\d{1,2})?)", ln)
             if nums:
                totals['gross_total'] = _parse_num_token(nums[-1], allow_divide_by_100=True)
                
        # Total Deductions
        elif re.search(r"(Deduction|Less)", ln, re.IGNORECASE):
             nums = re.findall(r"([\d,]+(?:[\.,]\d{1,2})?)", ln)
             if nums:
                totals['total_deductions'] = _parse_num_token(nums[-1], allow_divide_by_100=True)

    return totals

def combine_regions(regions_data):
    """
    Combine parsed region data into final voucher structure.
    """
    header = regions_data.get('header', {})
    items = regions_data.get('items', [])
    deductions = regions_data.get('deductions', [])
    totals = regions_data.get('totals', {})
    
    # Post-processing: Calculate totals if missing
    if totals.get('gross_total') is None and items:
        # Sum items
        calc_gross = sum(item.get('line_amount', 0) or 0 for item in items)
        if calc_gross > 0:
            totals['gross_total'] = calc_gross
            
    if totals.get('net_total') is None:
        gross = totals.get('gross_total') or 0
        deduc = totals.get('total_deductions') or 0
        totals['net_total'] = gross - deduc
    
    # Merge header and totals into master
    master = {
        'voucher_number': header.get('voucher_number'),
        'voucher_date': header.get('voucher_date'),
        'supplier_name': header.get('supplier_name'),
        'vendor_details': header.get('vendor_details'),
        'gross_total': totals.get('gross_total'),
        'total_deductions': totals.get('total_deductions'),
        'net_total': totals.get('net_total')
    }
    
    return {
        'master': master,
        'items': items,
        'deductions': deductions
    }

def parse_by_regions(extracted_text):
    """
    Main parsing function.
    """
    if not extracted_text:
        return {}
        
    if 'error' in extracted_text and extracted_text['error']:
        return {'error': extracted_text['error']}
    
    # Handle case where regions might be missing or raw text passing
    regions = extracted_text.get('regions', {})
    
    parsed_regions = {
        'header': parse_header_region(regions.get('header', '')),
        'items': parse_items_region(regions.get('items', '')),
        'deductions': parse_deductions_region(regions.get('deductions', '')),
        'totals': parse_totals_region(regions.get('totals', ''))
    }
    
    return combine_regions(parsed_regions)

# Helper functions
def try_parse_date(token):
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%y", "%d/%m/%y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(token.replace('.', '-'), fmt.replace('.', '-'))
            return dt.strftime("%Y-%m-%d") # Standard SQL format
        except Exception:
            continue
    return None
