# SUPPLIER NAME PARSING FIX - ROOT CAUSE ANALYSIS & SOLUTION

## PROBLEM
The application was incorrectly extracting the vendor designation "**AS**" as the supplier name instead of the actual supplier name "**TK**" that is marked with "SUPP NAME" in the voucher.

## ROOT CAUSE - TWO-LAYER BUG

### Layer 1: Text Correction (text_correction.py) ❌
**File**: `backend/text_correction.py` line 32

**The Bug**:
```python
RECEIPT_TERMS = {
    'SuppName': 'Supp Name',      # ✓ Correct: converts to spaced version
    'SuppNanm3': 'SuppName',       # ❌ BUG: converts to non-spaced version
    'SuppNam3': 'SuppName',        # ❌ BUG: converts to non-spaced version
}
```

**Problem**: When OCR reads "SuppNanm3" (OCR error), it corrects to "SuppName" (NO SPACE), but the parser expects "Supp Name" (WITH SPACE).

**Result**: Text correction pipeline produced:
- "SuppNanm3 TK" → "SuppName TK" ❌ (no space)

Instead of:
- "SuppNanm3 TK" → "Supp Name TK" ✓ (with space)

### Layer 2: Parser Fallback Logic (parser.py) ❌
**File**: `backend/parser.py` lines 105-119

**The Bug**:
```python
if data["supplier_name"] is None:
    # Try exact match first
    sn = RE_SUPPLIER_PREFIX.search(ln)  # Looks for "Supp Name:" pattern
    if sn:
        data["supplier_name"] = sn.group(1).strip()
    else:
        # ❌ FALLBACK: Too broad - captures ANY short line without digits
        if len(ln.strip()) >= 2 and len(ln.strip()) <= 10 and not re.search(r'\d', ln):
            data["supplier_name"] = ln.strip()  # Matches "AS"!
```

**Problem**: The fallback logic was processing lines in order:
1. Line 0: "AS" → matches fallback condition (short, no digits) → sets `supplier_name = "AS"` ✓ WRONG!
2. Line 7: "Supp Name TK" → regex matches but `supplier_name` is already set, so skipped

**Result**: Parser used "AS" instead of the properly labeled "Supp Name TK"

## SOLUTION - TWO FIXES

### Fix 1: Text Correction (backend/text_correction.py)
**Changed line 32 from**:
```python
'SuppNanm3': 'SuppName', 'SuppNam3': 'SuppName',
```

**Changed to**:
```python
'SuppNanm3': 'Supp Name', 'SuppNam3': 'Supp Name',
```

**Effect**: Now all OCR errors for supplier name are corrected consistently to "Supp Name" (WITH SPACE):
- "SuppNanm3 TK" → "Supp Name TK" ✓
- "SuppNam3 TK" → "Supp Name TK" ✓
- "SuppName TK" → "Supp Name TK" ✓

### Fix 2: Parser Strict Extraction (backend/parser.py)
**Removed the problematic fallback logic** (lines 117-119)

**Changed from**:
```python
if data["supplier_name"] is None:
    sn = RE_SUPPLIER_PREFIX.search(ln)
    if sn:
        # extract supplier name
    else:
        # ❌ FALLBACK: Too broad - captures "AS"
        if len(ln.strip()) >= 2 and len(ln.strip()) <= 10 and not re.search(r'\d', ln):
            data["supplier_name"] = ln.strip()
```

**Changed to**:
```python
if data["supplier_name"] is None:
    # STRICT EXTRACTION: Only extract supplier names explicitly labeled
    sn = RE_SUPPLIER_PREFIX.search(ln)
    if sn:
        # extract supplier name from "Supp Name: VALUE" pattern
```

**Effect**: Parser now ONLY extracts supplier names that are explicitly marked with "Supp Name:" label. No random short lines are captured.

## TEST RESULTS

### Before Fix
```
Test 1 (with "AS" at top): supplier_name = "AS" ❌ WRONG
Test 2 (without "AS"):     supplier_name = "TK" ✓ correct
```

### After Fix
```
Test 1 (with "AS" at top): supplier_name = "TK" ✓ CORRECT
Test 2 (without "AS"):     supplier_name = "TK" ✓ CORRECT
Test 3 (no "Supp Name"):   supplier_name = None ✓ CORRECT
```

## APPLICATION FLOW - CORRECTED

1. **OCR Extraction** (ocr_service.py)
   - Raw Tesseract output

2. **Text Correction** (text_correction.py) - NOW FIXED
   - Corrects "SuppNanm3" → "Supp Name" (WITH SPACE) ✓

3. **Decimal Correction** (decimal_correction.py)
   - Fixes number formatting

4. **Parsing** (parser.py) - NOW FIXED
   - STRICT extraction: Only matches "Supp Name: VALUE" pattern
   - No fallback heuristics that could capture wrong text

5. **Result**
   - Correct supplier name extracted ✓

## FILES MODIFIED

1. `backend/text_correction.py` - Line 32
   - Fixed OCR error correction mapping for supplier name

2. `backend/parser.py` - Lines 105-114
   - Removed problematic fallback logic
   - Now uses strict extraction only

## VALIDATION

Both fixes are essential:
- **Text correction fix alone** would ensure correct text is available but parser still wouldn't match it
- **Parser fix alone** would prevent "AS" capture but text wouldn't have proper spacing from text_correction

Together they ensure:
1. Correct text from OCR corrections ✓
2. Proper parsing of that text ✓
