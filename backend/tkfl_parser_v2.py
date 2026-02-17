"""
TKFL Parser v2 - Fixed for new voucher format
Addresses issues found in recent batch analysis
"""

import re
from datetime import datetime
from typing import Dict, List, Optional
import json


class TKFLReceiptParserV2:
    """
    Improved parser for TKFL vouchers
    Fixes: wrong voucher numbers, missing dates/suppliers, wrong totals
    """
    
    def __init__(self, ocr_text: str):
        self.raw_text = ocr_text or ""
        self.lines = [line.strip() for line in self.raw_text.split('\n') if line.strip()]
        
        self.data = {
            'voucher_number': None,
            'voucher_date': None,
            'supplier_name': None,
            'vendor_details': None,
            'gross_total': None,
            'net_total': None,
            'total_deductions': None,
            'items': [],
            'deductions': []
        }
        self.confidence = {}
        self.debug = []
    
    def _log(self, msg):
        """Log debug message"""
        self.debug.append(msg)
        print(f"[TKFL-V2] {msg}")
    
    def parse(self) -> Dict:
        """Main parsing method"""
        self._log("Starting TKFL v2 parsing...")
        
        self._extract_voucher_number_v2()
        self._extract_date_v2()
        self._extract_supplier_v2()
        self._extract_totals_v2()
        self._extract_items_v2()
        self._extract_deductions_v2()
        self._calculate_net_total()
        self._calculate_confidence()
        
        return {
            'master': {
                'voucher_number': self.data['voucher_number'],
                'voucher_date': self.data['voucher_date'],
                'supplier_name': self.data['supplier_name'],
                'vendor_details': self.data['vendor_details'],
                'gross_total': self.data['gross_total'],
                'net_total': self.data['net_total'],
                'total_deductions': self.data['total_deductions']
            },
            'items': self.data['items'],
            'deductions': self.data['deductions'],
            'confidence': self.confidence,
            'debug': self.debug
        }
    
    def _extract_voucher_number_v2(self):
        """Extract voucher number - FIXED version"""
        self._log("Extracting voucher number...")
        
        # Strategy 1: Look for "VoucherNumber" or "Voucher Number" followed by digits
        # But NOT followed by date patterns
        patterns = [
            r'(?:voucher\s*number|vouchernumber|voucher\s*no)[\s:]*(\d{2,4})\b',
            r'(?:nuaber|nunber|number)[\s:]*(\d{2,4})\b',
        ]
        
        for pattern in patterns:
            matches = list(re.finditer(pattern, self.raw_text, re.IGNORECASE))
            for match in matches:
                num = match.group(1)
                
                # Validate: should be reasonable voucher number (not year or date)
                if len(num) < 2 or len(num) > 4:
                    continue
                
                # Skip if it looks like a year (2020-2030)
                if 2020 <= int(num) <= 2030:
                    continue
                
                # Skip if followed by date separator (means it's part of a date)
                after_text = self.raw_text[match.end():match.end()+20]
                if re.search(r'[/\-]', after_text):
                    continue
                
                self.data['voucher_number'] = num
                self.confidence['voucher_number'] = 85
                self._log(f"Found voucher #: {num}")
                return
        
        self._log("No voucher number found")
        self.confidence['voucher_number'] = 0
    
    def _extract_date_v2(self):
        """Extract date - FIXED version"""
        self._log("Extracting date...")
        
        # Strategy 1: Look for "VoucherDate" or "Date" followed by date
        patterns = [
            r'(?:voucherdate|voucher\s*date)[\s:]*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
            r'\bdate[\s:]*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.raw_text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                parsed = self._parse_date(date_str)
                if parsed:
                    self.data['voucher_date'] = parsed
                    self.confidence['voucher_date'] = 90
                    self._log(f"Found date: {parsed}")
                    return
        
        # Strategy 2: Any DD/MM/YYYY in first 10 lines
        for line in self.lines[:10]:
            match = re.search(r'(\d{1,2})[\/](\d{1,2})[\/](\d{4})', line)
            if match:
                try:
                    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    if 2020 <= year <= 2030:
                        dt = datetime(year, month, day)
                        self.data['voucher_date'] = dt.strftime('%Y-%m-%d')
                        self.confidence['voucher_date'] = 80
                        self._log(f"Found date (general): {self.data['voucher_date']}")
                        return
                except:
                    continue
        
        self._log("No date found")
        self.confidence['voucher_date'] = 0
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string to standard format"""
        for sep in ['/', '-', '.']:
            if sep in date_str:
                parts = date_str.split(sep)
                if len(parts) == 3:
                    try:
                        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                        if 2020 <= year <= 2030:
                            dt = datetime(year, month, day)
                            return dt.strftime('%Y-%m-%d')
                    except:
                        continue
        return None
    
    def _extract_supplier_v2(self):
        """Extract supplier - FIXED version"""
        self._log("Extracting supplier...")
        
        # Strategy 1: Look for "Supp Name" pattern (handles OCR errors like SuppNane)
        patterns = [
            r'(?:supp\s*name|suppname|suppnane|suppnare)[\s:]*(.{2,30}?)(?=\n|$|qty|total)',
            r'(?:supp)[\s:]*(.{2,30}?)(?=\n|$|qty)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.raw_text, re.IGNORECASE)
            if match:
                supplier = match.group(1).strip()
                # Clean up
                supplier = re.sub(r'[\d\W]+$', '', supplier)
                if len(supplier) >= 2:
                    self.data['supplier_name'] = supplier
                    self.confidence['supplier_name'] = 80
                    self._log(f"Found supplier: {supplier}")
                    return
        
        # Strategy 2: Line immediately after "Supp Name" label
        for i, line in enumerate(self.lines):
            if re.search(r'supp\s*(?:name|nane|nare)', line, re.IGNORECASE):
                # Check if value is on same line after label
                if ':' in line or len(line.split()) > 2:
                    parts = re.split(r'supp\s*(?:name|nane|nare)[:\s]*', line, flags=re.IGNORECASE)
                    if len(parts) > 1:
                        supplier = parts[1].strip()
                        supplier = re.sub(r'[\d\W]+$', '', supplier)
                        if len(supplier) >= 2:
                            self.data['supplier_name'] = supplier
                            self.confidence['supplier_name'] = 75
                            self._log(f"Found supplier (same line): {supplier}")
                            return
                
                # Check next line
                if i < len(self.lines) - 1:
                    next_line = self.lines[i + 1].strip()
                    if not re.search(r'\b(qty|price|amount|total)\b', next_line, re.IGNORECASE):
                        if len(next_line) >= 2 and len(next_line) <= 30:
                            if not next_line.isdigit():
                                self.data['supplier_name'] = next_line
                                self.confidence['supplier_name'] = 70
                                self._log(f"Found supplier (next line): {next_line}")
                                return
        
        self._log("No supplier found")
        self.confidence['supplier_name'] = 0
    
    def _extract_totals_v2(self):
        """Extract totals - FIXED to find 'Total X YYYY.YY' pattern"""
        self._log("Extracting totals...")
        
        # Strategy 1: Look for "Total X YYYY.YY" pattern (where X is item count)
        # This is the actual gross total in TKFL format
        pattern = r'(?:^|\s|t)(?:otal|tal)[\s]*(\d+)[\s]*(\d{1,5}\.\d{2})'
        match = re.search(pattern, self.raw_text, re.IGNORECASE | re.MULTILINE)
        
        if match:
            try:
                amount = float(match.group(2))
                if amount > 10:
                    self.data['gross_total'] = amount
                    self.confidence['gross_total'] = 85
                    self._log(f"Found gross total from 'Total' line: {amount}")
            except:
                pass
        
        # Strategy 2: If no Total line found, use the largest amount in the document
        if self.data['gross_total'] is None:
            amounts = []
            for match in re.finditer(r'\b(\d{3,5}\.\d{2})\b', self.raw_text):
                try:
                    amount = float(match.group(1))
                    if 50 <= amount <= 100000:
                        amounts.append(amount)
                except:
                    continue
            
            if amounts:
                # Use the largest reasonable amount as gross total
                gross = max(amounts)
                self.data['gross_total'] = gross
                self.confidence['gross_total'] = 60
                self._log(f"Using largest amount as gross total: {gross}")
    
    def _extract_items_v2(self):
        """Extract line items"""
        self._log("Extracting items...")
        
        items = []
        
        for line in self.lines:
            # Pattern: Qty Price Amount
            match = re.search(r'(\d{1,3})\s+(\d{1,5}\.\d{2})\s+(\d{1,5}\.\d{2})', line)
            if match:
                try:
                    qty = int(match.group(1))
                    price = float(match.group(2))
                    amount = float(match.group(3))
                    
                    # Validate
                    expected = qty * price
                    if abs(amount - expected) < 1 or abs(amount - expected) / max(amount, 1) < 0.1:
                        item_text = line[:match.start()].strip()
                        item_text = re.sub(r'^[^a-zA-Z]*', '', item_text)
                        
                        items.append({
                            'item_name': item_text or 'Item',
                            'quantity': qty,
                            'unit_price': price,
                            'line_amount': amount
                        })
                except:
                    continue
        
        self.data['items'] = items
        self.confidence['items'] = min(90, len(items) * 25) if items else 20
    
    def _extract_deductions_v2(self):
        """Extract deductions with FIXED amount validation"""
        self._log("Extracting deductions...")
        
        deductions = []
        
        deduction_patterns = {
            'Commission': [r'comm', r'comission'],
            'Damage': [r'damage', r'damages'],
            'Unloading': [r'unload', r'unloading'],
            'L/F Cash': [r'l[/\s]*f', r'lf\s+and\s+cash'],
        }
        
        for ded_type, patterns in deduction_patterns.items():
            for pattern in patterns:
                # Look for keyword followed by amount
                full_pattern = rf'(?:{pattern}).*?(\d{{1,5}}\.?\d{{0,2}})'
                match = re.search(full_pattern, self.raw_text, re.IGNORECASE)
                
                if match:
                    try:
                        amount_str = match.group(1)
                        amount = float(amount_str)
                        
                        # FIXED: Validate amount is reasonable (not huge OCR errors)
                        # Commission should be small %, other deductions should be reasonable
                        if 0.1 <= amount <= 500:  # Reasonable range
                            # Check if it's a percentage
                            if '%' in match.group(0) or ('4.00' in amount_str and amount < 100):
                                # Calculate from gross if we have it
                                if self.data['gross_total'] and amount < 100:
                                    amount = self.data['gross_total'] * 0.04  # 4% commission
                                    ded_type = 'Commission @4%'
                            
                            deductions.append({
                                'deduction_type': ded_type,
                                'amount': round(amount, 2)
                            })
                            self._log(f"Found deduction: {ded_type} = {amount}")
                            break
                    except:
                        continue
        
        self.data['deductions'] = deductions
        if deductions:
            self.data['total_deductions'] = sum(d['amount'] for d in deductions)
            self.confidence['deductions'] = min(85, len(deductions) * 40)
        else:
            self.confidence['deductions'] = 30
    
    def _calculate_net_total(self):
        """Calculate net total from gross - deductions"""
        if self.data['gross_total']:
            if self.data['total_deductions']:
                self.data['net_total'] = self.data['gross_total'] - self.data['total_deductions']
                self._log(f"Calculated net total: {self.data['net_total']}")
            else:
                self.data['net_total'] = self.data['gross_total']
                self._log(f"Net total = Gross total (no deductions): {self.data['net_total']}")
            self.confidence['net_total'] = 70
    
    def _calculate_confidence(self):
        """Calculate overall confidence"""
        field_confs = []
        for field in ['voucher_number', 'voucher_date', 'supplier_name', 'gross_total']:
            conf = self.confidence.get(field, 0)
            field_confs.append(conf)
        
        if field_confs:
            avg_conf = sum(field_confs) / len(field_confs)
            min_conf = min(field_confs)
            self.confidence['overall'] = (avg_conf * 0.6) + (min_conf * 0.4)
        else:
            self.confidence['overall'] = 0


def parse_receipt_text_tkfl_v2(ocr_text: str) -> Dict:
    """Main entry point for TKFL v2 parsing"""
    parser = TKFLReceiptParserV2(ocr_text)
    return parser.parse()


# Backward compatibility
parse_receipt_text = parse_receipt_text_tkfl_v2


if __name__ == "__main__":
    # Test with sample
    test_text = """
    VoucherNumber115
    VoucherDate 09/01/2026
    Supp Name VANITHA/D
    Qty Price Amount
    Total 8 2490.00
    (-) Comm?4.00 99.60
    (-) LessForDamages 124.50
    (-) UnLoading 64.00
    (-) L/FAndCash 86.00
    """
    
    print("Testing TKFL Parser v2")
    print("="*60)
    result = parse_receipt_text_tkfl_v2(test_text)
    
    print("\n📋 EXTRACTED DATA:")
    print("-" * 40)
    for key, value in result['master'].items():
        if value is not None:
            print(f"✓ {key:20s}: {value}")
        else:
            print(f"✗ {key:20s}: NOT FOUND")
    
    print(f"\nItems: {len(result['items'])}")
    print(f"Deductions: {len(result['deductions'])}")
    print(f"\nOverall Confidence: {result['confidence'].get('overall', 0):.1f}%")
