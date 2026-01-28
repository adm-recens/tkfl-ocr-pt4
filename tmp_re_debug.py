import re
from backend import parser_roi

lines = ["Comm 4.00 57.20", "Unloading 4000"]
keywords = r"(Less|Comm|Damages?|Unloading|Labor|Hamali|Cash|Tax|VAT|Discount|Fee|Charge|Adv)"
pattern = rf"({keywords}.*?)\s*[:\-\s]\s*([\d,]+(?:[\.,]\d{{1,2}})?)$"
for ln in lines:
    print('LINE:', repr(ln))
    m = re.search(pattern, ln, re.IGNORECASE)
    print('PATTERN:', pattern)
    print('MATCH:', bool(m))
    if m:
        print('G1:', m.group(1), 'G2:', m.group(2))
    parts = ln.rsplit(None,1)
    print('PARTS:', parts)
    # test fallback parse
    if len(parts)==2:
        amt = parser_roi._parse_num_token(parts[1], allow_divide_by_100=True)
        lbl = parser_roi._clean_deduction_label(parts[0])
        print('FALLBACK ->', lbl, amt)
