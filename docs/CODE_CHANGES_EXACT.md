# CODE CHANGES - EXACT MODIFICATIONS

## File 1: backend/text_correction.py

### Location: Line 32 in RECEIPT_TERMS dictionary

**BEFORE (BUGGY)**:
```python
        # Supplier related (critical for supplier extraction)
        'SuppName': 'Supp Name', 'SuppNanm3': 'SuppName', 'SuppNam3': 'SuppName',
```

**AFTER (FIXED)**:
```python
        # Supplier related (critical for supplier extraction)
        'SuppName': 'Supp Name', 'SuppNanm3': 'Supp Name', 'SuppNam3': 'Supp Name',
```

### What Changed:
- Line 32, first OCR variant: `'SuppNanm3': 'SuppName'` → `'SuppNanm3': 'Supp Name'`
  - Added space between "Supp" and "Name"
- Line 32, second OCR variant: `'SuppNam3': 'SuppName'` → `'SuppNam3': 'Supp Name'`
  - Added space between "Supp" and "Name"

### Why This Fix:
- Ensures all OCR errors for supplier name are corrected to "Supp Name" (WITH SPACE)
- Allows the parser regex to match the corrected text
- Maintains consistency with the first mapping `'SuppName': 'Supp Name'`

### Impact:
```
BEFORE: "SuppNanm3 TK" → "SuppName TK" (no space) ❌
AFTER:  "SuppNanm3 TK" → "Supp Name TK" (with space) ✅
```

---

## File 2: backend/parser.py

### Location: Lines 105-119 (in function parse_receipt_text)

**BEFORE (BUGGY)**:
```python
# 2. Supplier Name
        if data["supplier_name"] is None:
            # Try exact match first
            sn = RE_SUPPLIER_PREFIX.search(ln)
            if sn:
                supplier_raw = sn.group(1).strip()
                # Clean up "None" prefix if present
                supplier_raw = re.sub(r"^None\s+", "", supplier_raw, flags=re.IGNORECASE)
                if supplier_raw and len(supplier_raw) >= 1:
                    data["supplier_name"] = supplier_raw
            else:
                # Handle standalone supplier names (like "TK")
                if len(ln.strip()) >= 2 and len(ln.strip()) <= 10 and not re.search(r'\d', ln):
                    # Likely a supplier name
                    data["supplier_name"] = ln.strip()
```

**AFTER (FIXED)**:
```python
# 2. Supplier Name
        if data["supplier_name"] is None:
            # Try exact match first with "Supp Name:" pattern - STRICT EXTRACTION
            # Only extract supplier names that are explicitly labeled, don't use fallback heuristics
            sn = RE_SUPPLIER_PREFIX.search(ln)
            if sn:
                supplier_raw = sn.group(1).strip()
                # Clean up "None" prefix if present
                supplier_raw = re.sub(r"^None\s+", "", supplier_raw, flags=re.IGNORECASE)
                if supplier_raw and len(supplier_raw) >= 1:
                    data["supplier_name"] = supplier_raw
```

### What Changed:
1. **Comments Updated** (Lines 107-108):
   - OLD: `# Try exact match first`
   - NEW: `# Try exact match first with "Supp Name:" pattern - STRICT EXTRACTION`
   - Added explanation about strict extraction and removal of fallback

2. **Removed Fallback Logic** (Lines 116-119 deleted):
   - Deleted entire `else:` block that contained fallback heuristic
   - This block was:
     ```python
     else:
         if len(ln.strip()) >= 2 and len(ln.strip()) <= 10 and not re.search(r'\d', ln):
             data["supplier_name"] = ln.strip()
     ```

### Why This Fix:
- The fallback logic was too broad and captured "AS" (which is 2 chars, no digits)
- Fallback would trigger on first iteration, preventing regex match on actual supplier name
- Strict extraction ensures only explicitly labeled "Supp Name:" entries are extracted

### Impact:
```
BEFORE: Line 0 "AS" → matches fallback → supplier_name = "AS" ❌
AFTER:  Line 0 "AS" → no match, no fallback → supplier_name = None
        Line 7 "Supp Name TK" → regex matches → supplier_name = "TK" ✅
```

---

## Summary of Changes

| File | Lines | Change Type | What | Why |
|------|-------|-------------|------|-----|
| text_correction.py | 32 | Mapping Fix | Add space to OCR error corrections | Ensure regex match in parser |
| parser.py | 105-119 | Logic Removal | Remove fallback heuristic | Prevent capture of unrelated text |

## Testing Evidence

Both changes have been validated with comprehensive tests:
- ✅ Text correction test: All variants → "Supp Name" with space
- ✅ Parser regex test: Confirmed pattern matches "Supp Name VALUE"
- ✅ Full flow test: OCR errors → corrected text → parsed correctly
- ✅ Edge case test: Missing labels handled correctly

## Git Diff Format

If using version control:
```bash
git diff backend/text_correction.py
# Shows: line 32 changes 'SuppName' to 'Supp Name' in two places

git diff backend/parser.py
# Shows: lines 105-119 deletion of else block with fallback logic
```

---

**Status**: ✅ PRODUCTION READY - Changes tested and verified
