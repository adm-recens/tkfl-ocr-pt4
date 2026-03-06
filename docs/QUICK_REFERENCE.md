# QUICK REFERENCE - SUPPLIER NAME FIX

## THE ISSUE
Application was extracting "**AS**" as supplier name instead of "**TK**"

## ROOT CAUSE
Two bugs in different layers:

### Bug #1: Text Correction (text_correction.py:32)
```
OCR: "SuppNanm3" → corrected to "SuppName" (NO SPACE) ❌
Should be: "SuppNanm3" → corrected to "Supp Name" (WITH SPACE) ✓
```

### Bug #2: Parser Fallback (parser.py:116-119)
```
Fallback heuristic captured ANY short line (2-10 chars, no digits)
This matched "AS" before regex could match "Supp Name TK"
Should remove fallback and use ONLY explicit "Supp Name:" labels
```

## THE FIX
Two changes:

### Fix #1: Text Correction Mapping
**File**: `backend/text_correction.py` **Line**: 32
```python
# CHANGE:
'SuppNanm3': 'SuppName'  →  'SuppNanm3': 'Supp Name'
'SuppNam3': 'SuppName'   →  'SuppNam3': 'Supp Name'
```

### Fix #2: Remove Parser Fallback
**File**: `backend/parser.py` **Lines**: 116-119
```python
# DELETE this entire else block:
else:
    if len(ln.strip()) >= 2 and len(ln.strip()) <= 10 and not re.search(r'\d', ln):
        data["supplier_name"] = ln.strip()
```

## VERIFICATION
```
✅ Test 1: OCR error "SuppNanm3" with "AS" prefix → Extracts "TK" CORRECTLY
✅ Test 2: OCR error "SuppNam3" → Extracts supplier CORRECTLY  
✅ Test 3: Clean "Supp Name" → Extracts supplier CORRECTLY
✅ Test 4: Missing "Supp Name" label → Returns None CORRECTLY
```

## FILES MODIFIED
1. `backend/text_correction.py` (Line 32) - 1 line change
2. `backend/parser.py` (Lines 105-114) - 4 lines deleted

## STATUS
✅ FIXED AND TESTED - Ready for production
