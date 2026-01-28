from backend import parser_roi
print('COMM TEST ->', parser_roi.parse_deductions_region('Comm 4.00 57.20'))
print('UNLOADING TEST ->', parser_roi.parse_deductions_region('Unloading 4000'))
print('RAW LNS ->', [ln.strip() for ln in parser_roi.clean_ocr_text('Comm 4.00 57.20').splitlines() if ln.strip()])
