from backend.ocr_roi_service import extract_with_roi
from backend.parser_roi import parse_by_regions
import json

# Find the latest beta voucher image path
from backend.services.voucher_service import VoucherService
from backend.app import create_app
import os

app = create_app()
with app.app_context():
    vouchers = VoucherService.get_all_vouchers(page=1)
    beta_vouchers = [v for v in vouchers['vouchers'] if v.get('ocr_mode') == 'roi_beta']
    
    if not beta_vouchers:
        print("No beta vouchers found!")
    else:
        voucher = beta_vouchers[0]
        image_path = voucher['file_storage_path']
        
        print(f"Testing OCR on: {image_path}")
        print(f"File exists: {os.path.exists(image_path)}")
        print("\n" + "="*60)
        
        # Run OCR extraction
        print("Running extract_with_roi...")
        extracted = extract_with_roi(image_path)
        
        if 'error' in extracted:
            print(f"ERROR: {extracted['error']}")
        else:
            print("\n--- EXTRACTED REGIONS ---")
            regions = extracted.get('regions', {})
            for region_name, text in regions.items():
                print(f"\n[{region_name.upper()}] ({len(text)} chars):")
                print(text[:200] if len(text) > 200 else text)
            
            print("\n\n--- FULL TEXT (first 500 chars) ---")
            print(extracted.get('full_text', '')[:500])
            
            # Run parsing
            print("\n\n" + "="*60)
            print("Running parse_by_regions...")
            parsed = parse_by_regions(extracted)
            
            print("\n--- PARSED RESULT ---")
            print(json.dumps(parsed, indent=2))
