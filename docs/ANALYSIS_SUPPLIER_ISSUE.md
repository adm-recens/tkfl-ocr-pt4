APPLICATION FLOW ANALYSIS - SUPPLIER NAME PARSING ISSUE
========================================================

## COMPLETE APPLICATION FLOW:

1. IMAGE UPLOAD
   └─> OCR Extraction (backend/ocr_service.py - extract_text())
       └─> Raw Tesseract Output
       └─> Text Corrections Applied (backend/text_correction.py)
           ├─ Whitespace cleaning
           ├─ Term corrections (e.g., "SuppNanm3" -> "SuppName")
           └─ Digit substitution corrections
       └─> Decimal Corrections Applied (backend/decimal_correction.py)
       └─> FINAL CORRECTED TEXT returned

2. TEXT PARSING
   └─> parse_receipt_text() in backend/parser.py
       └─ Iterates through lines
       └─ Extracts: supplier_name, vendor_details, voucher_number, etc.

## CRITICAL FINDING:

The extract_text() function returns:
    {
        'text': final_corrected_text,    # <- This is what goes to parser
        'raw_text': raw_text,            # <- Original Tesseract output
        'confidence': avg_confidence,
        ...
    }

In api_queue.py line 256-257:
    raw_text = ocr_result.get('text', '')  # <- Gets CORRECTED text
    parsed_data = parse_receipt_text(raw_text)

## THE REAL ISSUE:

The text_correction.py has:
    RECEIPT_TERMS = {
        'SuppName': 'Supp Name',
        'SuppNanm3': 'SuppName',  # Corrects OCR error to 'SuppName' (WITHOUT space)
        ...
    }

So when OCR reads "SuppNanm3" -> corrects to "SuppName" (no space)
But the parser regex looks for:
    RE_SUPPLIER_PREFIX = r"(?:Supp|SUPP)\s*(?:Name|NAME|Nam[3e])?\s*[:\-\s]\s*(.+)"

This regex expects at least one whitespace (\s*) after "Supp" but text_correction.py
converts "SuppNanm3" to "SuppName" (no space).

## WHAT HAPPENS WITH "AS" PROBLEM:

From queue_store.json example:
    Raw OCR:  "AS\nAHMEDSHARIF&BROS\n...SuppName      TK"
    After correction: "AS\nAHMED SHARIF & BROS\n...SuppName TK"

When parser iterates:
    Line 1: "AS" -> Too short but matches fallback logic
    Line 2: "AHMED SHARIF & BROS" -> Matches vendor heuristics
    Line N: "SuppName TK" -> Doesn't match regex because text_correction
            converts OCR errors to "SuppName" (no space), but regex needs space

Result: Parser picks "AS" from fallback logic instead of waiting for "SuppName TK"

## ROOT CAUSE ANALYSIS:

There's a MISMATCH between:
1. text_correction.py output: "SuppName" (no space)
2. parser.py regex expectation: "Supp\s+Name" (requires space)

The text correction SHOULD produce "Supp Name" (with space) to match the regex.
