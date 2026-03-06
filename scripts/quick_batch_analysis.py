#!/usr/bin/env python3
"""Quick batch analysis - OCR vs Parsing gap detection"""
import sys, os
sys.path.insert(0, 'backend')
os.environ['FLASK_ENV'] = 'development'

from pathlib import Path
import ocr_service
import parser as parser_mod

# Get latest batch
uploads = Path('uploads')
files = sorted(list(uploads.glob('*.jpg')) + list(uploads.glob('*.jpeg')), 
               key=lambda x: x.stat().st_mtime, reverse=True)

batches = {}
for f in files:
    bid = f.name.split('_')[0]
    batches.setdefault(bid, []).append(f)

bid = list(batches.keys())[0]
originals = sorted([f for f in batches[bid] if '_cropped_' not in f.name and 'preview_' not in f.name],
                   key=lambda x: x.stat().st_mtime, reverse=True)

print(f"\nBATCH ANALYSIS: {bid}")
print(f"Total Images: {len(originals)}\n")

ocr_ok = parsing_ok = 0
issues = []

for i, img in enumerate(originals[:8], 1):
    try:
        ocr = ocr_service.extract_text(str(img), method='enhanced')
        parsed = parser_mod.parse_receipt_text(ocr['text'])
        
        conf = ocr.get('confidence', 0)
        length = len(ocr.get('text', ''))
        
        missing = []
        for k in ['voucher_number', 'voucher_date', 'supplier_name', 'gross_total', 'net_total']:
            if not parsed.get(k):
                missing.append(k.split('_')[0])
        
        if conf >= 60 and length > 100:
            ocr_ok += 1
        if not missing:
            parsing_ok += 1
        else:
            issues.append((img.name, conf, missing))
        
        print(f"[{i}] OCR:{conf}% | {length:3}ch | {'OK' if not missing else 'FAIL:' + ','.join(missing)}")
    except Exception as e:
        print(f"[{i}] ERROR: {e}")

print(f"\nOCR Quality:  {ocr_ok}/8")
print(f"Parsing OK:   {parsing_ok}/8")
print(f"GAP:          {ocr_ok - parsing_ok} images with good OCR but failed parsing\n")

if issues:
    print("FAILING FIELDS:")
    field_freq = {}
    for _, _, missing in issues:
        for f in missing:
            field_freq[f] = field_freq.get(f, 0) + 1
    for f in sorted(field_freq, key=lambda x: -field_freq[x]):
        print(f"  {f}: {field_freq[f]} missing")
