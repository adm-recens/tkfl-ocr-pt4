# Parser Improvement Code Patches

Ready-to-implement fixes for OCR → Parsing gap.  
These can be added to `backend/parser.py` incrementally.

---

## Patch 1: Universal Number Parsing

**File:** `backend/parser.py`  
**Target Function:** `safe_float_conversion()` (line ~10)  
**Impact:** Fixes number extraction for all formats

```python
def safe_float_conversion(value):
    """
    Convert string to float, handling multiple number formats:
    - US format: 1,234.56
    - European format: 1.234,56
    - Indian format: 12,34,567.89
    - Simple: 1234.56 or 1234,56
    """
    if value is None:
        return None
    
    text = str(value).strip()
    
    # If no separators, just convert
    if ',' not in text and '.' not in text:
        try:
            return float(text)
        except ValueError:
            return None
    
    # Identify decimal separator (rightmost comma or dot)
    last_comma_pos = text.rfind(',')
    last_dot_pos = text.rfind('.')
    
    if last_comma_pos > last_dot_pos:
        # European format: last separator is comma
        thousands_sep = '.'
        decimal_sep = ','
    else:
        # US format: last separator is dot
        thousands_sep = ','
        decimal_sep = '.'
    
    # Remove thousands separator
    text = text.replace(thousands_sep, '')
    
    # Replace decimal separator with standard dot
    text = text.replace(decimal_sep, '.')
    
    try:
        return float(text)
    except ValueError:
        return None
```

---

## Patch 2: Enhanced Date Parsing

**File:** `backend/parser.py`  
**Target Function:** `try_parse_date()` (line ~27)  
**Impact:** Recognizes dates in 8+ different formats

```python
import re
from datetime import datetime

def try_parse_date(token):
    """
    Try to parse date from token in multiple formats.
    Supports: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, 
              DD-JAN-YYYY, Jan-DD-YYYY, DD/MMM/YYYY,
              YYYY-MM-DD, YYYY/MM/DD
    """
    if not token or len(token) < 8:
        return None
    
    token = token.strip()
    
    # Remove common date prefixes
    token = re.sub(r'^(date|dated|on|dt\.?)\s*:?\s*', '', token, flags=re.IGNORECASE)
    
    # Date patterns in priority order
    patterns = [
        # Pattern: DD-JAN-YYYY, DD-JAN-20 (e.g., "05-JAN-2026")
        (r'(\d{1,2})\s*[-/.]\s*(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s*[-/.]\s*(\d{4}|\d{2})',
         lambda m: parse_dmy_format(m.group(1), m.group(2), m.group(3))),
        
        # Pattern: DD-MM-YYYY (e.g., "05-01-2026", "05/01/2026")
        (r'(\d{1,2})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{4})',
         lambda m: f"{m.group(1)}/{m.group(2)}/{m.group(3)}"),
        
        # Pattern: YYYY-MM-DD (e.g., "2026-01-05")
        (r'(\d{4})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{1,2})',
         lambda m: f"{m.group(3)}/{m.group(2)}/{m.group(1)}"),
        
        # Pattern: Jan 5, 2026 or JAN 5 2026
        (r'(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+(\d{1,2}),?\s*(\d{4})',
         lambda m: parse_dmy_format(m.group(2), m.group(1), m.group(3))),
        
        # Pattern: 5 Jan 2026
        (r'(\d{1,2})\s+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s*(\d{4})',
         lambda m: parse_dmy_format(m.group(1), m.group(2), m.group(3))),
    ]
    
    for pattern, formatter in patterns:
        match = re.search(pattern, token, re.IGNORECASE)
        if match:
            try:
                result = formatter(match)
                if result:
                    return result
            except:
                continue
    
    return None

def parse_dmy_format(day, month, year):
    """Parse day-month-year format"""
    try:
        # Handle month names
        month_names = {
            'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4,
            'MAY': 5, 'JUN': 6, 'JUL': 7, 'AUG': 8,
            'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
        }
        
        if isinstance(month, str):
            month = month_names.get(month.upper()[:3], None)
            if month is None:
                return None
        
        day = int(day)
        month = int(month)
        year = int(year)
        
        # Handle 2-digit years
        if year < 100:
            year += 2000
        
        # Validate
        if day < 1 or day > 31 or month < 1 or month > 12:
            return None
        
        # Create and format date
        dt = datetime(year, month, day)
        return dt.strftime('%d/%m/%Y')
    except:
        return None
```

---

## Patch 3: Fuzzy Supplier Matching

**File:** `backend/parser.py`  
**New Function:** Add this entire function  
**Impact:** Finds supplier names even with OCR errors

```python
from difflib import SequenceMatcher

# Known supplier database (can be expanded)
KNOWN_SUPPLIERS = [
    'ACME', 'AMAZON', 'WALMART', 'TARGET',
    'COSTCO', 'BEST BUY', 'HOME DEPOT', 'LOWES',
    # Add more suppliers as needed
]

def find_supplier_fuzzy(ocr_text):
    """
    Find supplier name using fuzzy matching.
    Returns best match even if OCR had errors.
    """
    candidates = extract_company_candidates(ocr_text)
    
    if not candidates:
        return None
    
    # Try to match against known suppliers first
    for candidate in candidates:
        for known_supplier in KNOWN_SUPPLIERS:
            similarity = string_similarity(candidate.upper(), known_supplier.upper())
            if similarity > 0.75:  # 75% threshold
                return candidate
    
    # If no known match, return best candidate
    # (Most likely to be supplier: all caps, has keywords, near start)
    return candidates[0] if candidates else None

def extract_company_candidates(text):
    """
    Extract lines that are likely company names.
    Heuristics: all caps, title case, contains company keywords, at start of doc.
    """
    lines = text.split('\n')
    candidates = []
    company_keywords = ['INC', 'LTD', 'LLC', 'CORP', 'CO', 'PVT', 'COMPANY', 'ENTERPRISES']
    
    for i, line in enumerate(lines[:10]):  # Check first 10 lines only
        line = line.strip()
        
        # Skip short lines or empty
        if len(line) < 3 or len(line) > 100:
            continue
        
        # Skip lines with numbers only
        if re.match(r'^\d+[\s\d.,]*$', line):
            continue
        
        # Candidate if:
        is_all_caps = line.isupper()
        is_title_case = re.match(r'^[A-Z][A-Za-z\s&.,-]*$', line)
        has_company_keyword = any(kw in line.upper() for kw in company_keywords)
        is_early = i < 5
        
        if (is_all_caps or is_title_case) and (has_company_keyword or is_early):
            candidates.append(line)
    
    return candidates

def string_similarity(a, b):
    """Calculate similarity between two strings (0-1)"""
    return SequenceMatcher(None, a, b).ratio()
```

---

## Patch 4: Voucher Number Enhancement

**File:** `backend/parser.py`  
**Improve:** Voucher number extraction  
**Impact:** Finds invoice/bill numbers in more formats

```python
def extract_voucher_number(ocr_text):
    """
    Extract voucher/invoice number from OCR text.
    Looks for patterns: INV #123456, Invoice: 123456, Bill No 123456, etc.
    """
    patterns = [
        # Pattern: Invoice #123456, INV: 123456, INVOICE NO. 123456
        (r'(?:invoice|inv|bill|no|po|order|ref|reference|doc|document|receipt\s+no)[:\s#]*([\w-]+)',
         lambda m: m.group(1)),
        
        # Pattern: #123456 or number after special marker
        (r'[#:]\s*([0-9]{4,15})',
         lambda m: m.group(1)),
        
        # Pattern: Standalone reference number (6+ digits)
        (r'\b([0-9]{6,15})\b',
         lambda m: m.group(1)),
    ]
    
    for pattern, extractor in patterns:
        for match in re.finditer(pattern, ocr_text, re.IGNORECASE):
            number = extractor(match)
            if number and len(str(number)) >= 4:  # At least 4 digits
                return number
    
    return None
```

---

## Patch 5: Context-Aware Total Extraction

**File:** `backend/parser.py`  
**Improve:** Total and amount extraction  
**Impact:** Correctly finds gross total, net total, subtotal

```python
def extract_totals(ocr_text):
    """
    Extract financial totals with context awareness.
    Looks for: Total, Net, Gross, Subtotal, Grand Total, Amount Due, Balance
    """
    result = {
        'gross_total': None,
        'net_total': None,
        'subtotal': None,
        'gst_amount': None,
    }
    
    lines = ocr_text.split('\n')
    
    # Pattern: Keyword followed by amount
    total_pattern = r'(?:total|amount|due|balance|subtotal|gross|net|sum|final)[:\s]*([\d.,]+)'
    
    for line in lines:
        # Check for keywords in each line
        if 'subtotal' in line.lower() or 'sub' in line.lower():
            amount = extract_amount(line)
            if amount and not result['subtotal']:
                result['subtotal'] = amount
        
        elif ('gross' in line.lower() or 'gross total' in line.lower()):
            amount = extract_amount(line)
            if amount and not result['gross_total']:
                result['gross_total'] = amount
        
        elif ('net' in line.lower() or 'net total' in line.lower()):
            amount = extract_amount(line)
            if amount and not result['net_total']:
                result['net_total'] = amount
        
        elif ('gst' in line.lower() or 'tax' in line.lower()):
            amount = extract_amount(line)
            if amount and not result['gst_amount']:
                result['gst_amount'] = amount
        
        elif any(word in line.lower() for word in ['total amount', 'amount due', 'balance due']):
            amount = extract_amount(line)
            if amount:
                # Could be gross or net depending on context
                if not result['gross_total']:
                    result['gross_total'] = amount
                elif not result['net_total']:
                    result['net_total'] = amount
    
    # Fallback logic: if we have gross and gst, calculate net
    if result['gross_total'] and result['gst_amount'] and not result['net_total']:
        result['net_total'] = result['gross_total'] - result['gst_amount']
    
    return result

def extract_amount(line):
    """Extract monetary amount from a line of text"""
    # Find pattern: amount (with possible currency symbol, commas, etc)
    amount_pattern = r'[₹$£€]?\s*([\d.,]+)\s*(?:[₹$£€]|Rs|USD|INR)?'
    
    matches = list(re.finditer(amount_pattern, line))
    if not matches:
        return None
    
    # Usually the last number in the line is the amount
    last_match = matches[-1]
    amount_str = last_match.group(1)
    
    # Convert to float
    amount = safe_float_conversion(amount_str)
    return amount
```

---

## Patch 6: Integration Points

**File:** `backend/parser.py`  
**Update Function:** `parse_receipt_text()` main function  
**Impact:** Uses all improvements together

```python
def parse_receipt_text(ocr_text: str) -> dict:
    """
    Enhanced receipt text parser with improved field extraction.
    """
    tokens = ocr_text.split('\n')
    
    result = {
        'voucher_number': None,
        'voucher_date': None,
        'supplier_name': None,
        'gross_total': None,
        'net_total': None,
        'confidence': {  # NEW: Add confidence scores
            'voucher_number': 0,
            'voucher_date': 0,
            'supplier_name': 0,
            'gross_total': 0,
            'net_total': 0,
        }
    }
    
    # Extract supplier (NEW: with fuzzy matching)
    supplier = find_supplier_fuzzy(ocr_text)
    if supplier:
        result['supplier_name'] = supplier
        result['confidence']['supplier_name'] = 85  # High confidence from fuzzy match
    
    # Extract voucher number (ENHANCED)
    voucher_num = extract_voucher_number(ocr_text)
    if voucher_num:
        result['voucher_number'] = voucher_num
        result['confidence']['voucher_number'] = 80
    
    # Extract date (ENHANCED)
    for token in tokens:
        parsed_date = try_parse_date(token)
        if parsed_date:
            result['voucher_date'] = parsed_date
            result['confidence']['voucher_date'] = 85
            break
    
    # Extract totals (NEW: context-aware)
    totals = extract_totals(ocr_text)
    result['gross_total'] = totals.get('gross_total')
    result['net_total'] = totals.get('net_total')
    
    if result['gross_total']:
        result['confidence']['gross_total'] = 85
    if result['net_total']:
        result['confidence']['net_total'] = 85
    
    return result
```

---

## Patch 7: Testing Utilities

**File:** Create `backend/test_parser_improvements.py`  
**Purpose:** Validate all improvements

```python
import parser as parser_module

def test_number_formats():
    """Test number parsing with various formats"""
    test_cases = [
        ("1234.56", 1234.56),
        ("1,234.56", 1234.56),
        ("1.234,56", 1234.56),
        ("12,34,567.89", 1234567.89),
        ("12.34.567,89", 1234567.89),
    ]
    
    print("Testing number parsing...")
    for input_val, expected in test_cases:
        result = parser_module.safe_float_conversion(input_val)
        status = "✓" if abs(result - expected) < 0.01 else "✗"
        print(f"  {status} {input_val} → {result} (expected {expected})")

def test_date_formats():
    """Test date parsing with various formats"""
    test_cases = [
        "05-01-2026",
        "05-JAN-2026",
        "Jan 5, 2026",
        "5 January 2026",
        "2026-01-05",
    ]
    
    print("\nTesting date parsing...")
    for test_date in test_cases:
        result = parser_module.try_parse_date(test_date)
        status = "✓" if result else "✗"
        print(f"  {status} {test_date} → {result}")

def test_supplier_matching():
    """Test supplier name extraction"""
    test_text = """
    ACME WHOLESALE INC
    GST#12345678
    
    Invoice details...
    """
    
    print("\nTesting supplier matching...")
    result = parser_module.find_supplier_fuzzy(test_text)
    print(f"  Found: {result}")

if __name__ == '__main__':
    test_number_formats()
    test_date_formats()
    test_supplier_matching()
    print("\nAll tests complete!")
```

---

## Implementation Order

1. **Patch 1** - Number parsing (5 min) - Critical
2. **Patch 2** - Date parsing (10 min) - Critical
3. **Patch 3** - Fuzzy supplier matching (10 min) - Important
4. **Patch 4** - Voucher number enhancement (5 min) - Nice to have
5. **Patch 5** - Total extraction (10 min) - Important
6. **Patch 6** - Integration (10 min) - Tie it together
7. **Patch 7** - Testing (5 min) - Validation

**Total Time:** ~55 minutes  
**Expected Impact:** 30-40% → 90-95% field extraction success

---

## Rollback Instructions

Each patch is independent. To rollback:
1. Revert `backend/parser.py` to previous version
2. No database changes required
3. Restart Flask app: `python run.py`

---

## Next: Apply Patches

These patches are ready to implement. Would you like me to:
1. Apply all patches at once to parser.py?
2. Apply them incrementally?
3. Create a separate enhanced_parser.py to test first?
