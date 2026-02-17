"""
TKFL-Specific Parser - Optimized for your actual voucher format
Based on analysis of real OCR output from your vouchers
"""

import re
from datetime import datetime
from typing import Dict, List, Optional
import json


class TKFLReceiptParser:
    """
    Parser specifically tuned for TKFL voucher format
    Based on analysis of 168 real vouchers in your database
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
        print(f"[TKFL-PARSER] {msg}")
    
    def parse(self) -> Dict:
        """Main parsing method"""
        self._log("Starting TKFL-specific parsing...")
        
        self._extract_voucher_number_tkfl()
        self._extract_date_tkfl()
        self._extract_supplier_tkfl()
        self._extract_totals_tkfl()
        self._extract_items_tkfl()
        self._extract_deductions_tkfl()
        self._calculate_missing()
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
    
    def _extract_voucher_number_tkfl(self):
        """Extract voucher number using TKFL-specific patterns"""
        self._log("Extracting voucher number...")
        
        # Pattern 1: Look for "Number" followed by digits (handles OCR errors like Nuaber, Nunber, etc)
        # This should catch: "herNuaber151", "rNunber133", "sherNunber149"
        pattern1 = r'(?:^|\s|er|r|her|cher|sher)(?:nu|Nu|NU)(?:m|a|o|u)?ber[:\s]*(\d{2,4})'
        match = re.search(pattern1, self.raw_text, re.IGNORECASE)
        if match:
            num = match.group(1)
            if len(num) >= 2 and len(num) <= 4:
                self.data['voucher_number'] = num
                self.confidence['voucher_number'] = 85
                self._log(f"Found voucher # from 'Number' pattern: {num}")
                return
        
        # Pattern 2: Look for standalone 2-4 digit numbers in first few lines
        # that appear BEFORE "VoucherNumber" text
        lines_before_voucherword = []
        found_voucherword = False
        for line in self.lines[:15]:  # Check first 15 lines
            if 'vouchernumber' in line.lower().replace(' ', ''):
                found_voucherword = True
                break
            lines_before_voucherword.append(line)
        
        # Search those lines for voucher number
        search_text = '\n'.join(lines_before_voucherword)
        numbers = re.findall(r'\b(\d{2,4})\b', search_text)
        for num in numbers:
            # Skip if it looks like a date part
            if not re.search(rf'\d{{1,2}}[/-]{num}|{num}[/-]\d{{1,2}}', search_text):
                self.data['voucher_number'] = num
                self.confidence['voucher_number'] = 75
                self._log(f"Found voucher # before VoucherNumber text: {num}")
                return
        
        # Pattern 3: Any standalone 3-digit number early in document
        for i, line in enumerate(self.lines[:8]):
            match = re.search(r'^\s*(\d{3})\s*$', line)
            if match:
                self.data['voucher_number'] = match.group(1)
                self.confidence['voucher_number'] = 60
                self._log(f"Found standalone 3-digit voucher #: {match.group(1)}")
                return
        
        self._log("No voucher number found")
        self.confidence['voucher_number'] = 0
    
    def _extract_date_tkfl(self):
        """Extract date - TKFL uses DD/MM/YYYY format"""
        self._log("Extracting date...")
        
        # Pattern 1: Date followed by voucher word (most common in your data)
        # Examples: "07/01/2026", "Date 07/01/2026", "rDate 07/01/2026"
        pattern1 = r'(?:date|rdate|Date|DATE)[\s:]*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})'
        match = re.search(pattern1, self.raw_text, re.IGNORECASE)
        
        if match:
            date_str = match.group(1)
            parsed = self._parse_date(date_str)
            if parsed:
                self.data['voucher_date'] = parsed
                self.confidence['voucher_date'] = 90
                self._log(f"Found date: {parsed}")
                return
        
        # Pattern 2: Any DD/MM/YYYY or DD-MM-YYYY in first 10 lines
        for line in self.lines[:10]:
            match = re.search(r'(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})', line)
            if match:
                try:
                    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    dt = datetime(year, month, day)
                    self.data['voucher_date'] = dt.strftime('%Y-%m-%d')
                    self.confidence['voucher_date'] = 80
                    self._log(f"Found date (general pattern): {self.data['voucher_date']}")
                    return
                except:
                    continue
        
        self._log("No date found")
        self.confidence['voucher_date'] = 0
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string to standard format"""
        date_str = date_str.strip()
        separators = ['/', '-', '.']
        
        for sep in separators:
            if sep in date_str:
                parts = date_str.split(sep)
                if len(parts) == 3:
                    try:
                        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                        # Validate
                        if 1 <= day <= 31 and 1 <= month <= 12 and 2020 <= year <= 2030:
                            dt = datetime(year, month, day)
                            return dt.strftime('%Y-%m-%d')
                    except:
                        continue
        return None
    
    def _extract_supplier_tkfl(self):
        """Extract supplier - handles 'Nane', 'lane', 'Name' OCR errors"""
        self._log("Extracting supplier...")
        
        # Pattern 1: Look for Name/Name/Nane followed by supplier (case insensitive)
        # Common patterns seen: "Nane JPYK", "lane KARTHIK/V", "Nane JNMK", "pNane TK"
        patterns = [
            r'(?:^|\s|p)(?:nane|lane|name|Nane|Lane|Name)[\s:]*(.{2,30}?)(?=\n|$|qty|date|voucher)',
            r'(?:^|\s)(?:ane|nme|nane)[\s:]*(.{2,30}?)(?=\n|$|qty)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.raw_text, re.IGNORECASE)
            if match:
                supplier = match.group(1).strip()
                # Clean up - remove trailing punctuation and qty/price text
                supplier = re.sub(r'[\d\W]+$', '', supplier)
                supplier = re.sub(r'\s*(?:qty|price|amount).*$', '', supplier, flags=re.IGNORECASE)
                
                if len(supplier) >= 2:
                    self.data['supplier_name'] = supplier
                    self.confidence['supplier_name'] = 80
                    self._log(f"Found supplier from Name pattern: {supplier}")
                    return
        
        # Pattern 2: Line after "Name" label
        for i, line in enumerate(self.lines):
            if re.search(r'\b(nane|lane|name|ane)\b', line, re.IGNORECASE):
                # Check if supplier is on this line after the word
                parts = re.split(r'(?:nane|lane|name|ane)[:\s]*', line, flags=re.IGNORECASE)
                if len(parts) > 1:
                    supplier = parts[1].strip()
                    supplier = re.sub(r'[\d\W]+$', '', supplier)
                    if len(supplier) >= 2:
                        self.data['supplier_name'] = supplier
                        self.confidence['supplier_name'] = 75
                        self._log(f"Found supplier on same line: {supplier}")
                        return
                
                # Check next line
                if i < len(self.lines) - 1:
                    next_line = self.lines[i + 1].strip()
                    # Make sure it's not a table header
                    if not re.search(r'\b(qty|price|amount|total)\b', next_line, re.IGNORECASE):
                        if len(next_line) >= 2 and len(next_line) <= 30:
                            if not next_line.isdigit():
                                self.data['supplier_name'] = next_line
                                self.confidence['supplier_name'] = 70
                                self._log(f"Found supplier on next line: {next_line}")
                                return
        
        self._log("No supplier found")
        self.confidence['supplier_name'] = 0
    
    def _extract_totals_tkfl(self):
        """Extract totals - TKFL format: 'al 3 400.00' means total 400.00"""
        self._log("Extracting totals...")
        
        amounts = []
        
        # Pattern 1: Look for "al X YYYY.YY" pattern (Total line)
        # This catches: "al 3 400.00", "tal 3 400.00", "al ? 400.00"
        pattern1 = r'(?:^|\s|t)(?:al|tal)[\s]*(?:\d+|\?)?[\s]*(\d{1,5}\.\d{2})'
        matches = list(re.finditer(pattern1, self.raw_text, re.IGNORECASE | re.MULTILINE))
        
        for match in matches:
            try:
                amount = float(match.group(1))
                if amount > 10:  # Reasonable amount threshold
                    amounts.append(('gross', amount, match.start()))
                    self._log(f"Found gross total from 'al' pattern: {amount}")
            except:
                continue
        
        # Pattern 2: Look for "Grand Total" or standalone totals at end
        pattern2 = r'(?:grand\s*total|total)[\s:]*(\d{1,5}\.\d{2})'
        match = re.search(pattern2, self.raw_text, re.IGNORECASE)
        if match:
            try:
                amount = float(match.group(1))
                if amount > 10:
                    amounts.append(('net', amount, 99999))  # High position = end of doc
                    self._log(f"Found net total from 'Grand Total': {amount}")
            except:
                pass
        
        # Pattern 3: Find all X.XX amounts and use heuristics
        all_amounts = []
        for match in re.finditer(r'\b(\d{3,5}\.\d{2})\b', self.raw_text):
            try:
                amount = float(match.group(1))
                if amount > 50:  # Filter small values
                    all_amounts.append((amount, match.start()))
            except:
                pass
        
        # Sort by position in document
        all_amounts.sort(key=lambda x: x[1])
        
        # Last significant amount is often the total
        if all_amounts and not amounts:
            gross = all_amounts[-1][0]
            amounts.append(('gross', gross, all_amounts[-1][1]))
            self._log(f"Using last amount as gross total: {gross}")
        
        # Set the values
        gross_amounts = [a[1] for a in amounts if a[0] == 'gross']
        net_amounts = [a[1] for a in amounts if a[0] == 'net']
        
        if gross_amounts:
            self.data['gross_total'] = max(gross_amounts)  # Take largest if multiple
            self.confidence['gross_total'] = 75
        
        if net_amounts:
            self.data['net_total'] = net_amounts[0]
            self.confidence['net_total'] = 70
        elif gross_amounts:
            # If no net total found, calculate from gross minus deductions
            self.data['net_total'] = self.data['gross_total']
            self.confidence['net_total'] = 50
    
    def _extract_items_tkfl(self):
        """Extract line items from table"""
        self._log("Extracting items...")
        
        items = []
        
        # Look for lines with Qty Price Amount pattern
        # Example: "2 220.00 440.00" or "1 280.00 280.00"
        for line in self.lines:
            # Pattern: Qty (integer) + Price (decimal) + Amount (decimal)
            match = re.search(r'(\d{1,3})\s+(\d{1,5}\.\d{2})\s+(\d{1,5}\.\d{2})', line)
            if match:
                try:
                    qty = int(match.group(1))
                    price = float(match.group(2))
                    amount = float(match.group(3))
                    
                    # Validate: amount should be qty * price (with small tolerance)
                    expected = qty * price
                    if abs(amount - expected) < 1 or abs(amount - expected) / max(amount, 1) < 0.05:
                        # Extract item name (text before the numbers)
                        item_text = line[:match.start()].strip()
                        # Clean up
                        item_text = re.sub(r'^[^a-zA-Z]*', '', item_text)  # Remove leading non-letters
                        item_name = item_text if item_text else 'Item'
                        
                        items.append({
                            'item_name': item_name,
                            'quantity': qty,
                            'unit_price': price,
                            'line_amount': amount
                        })
                        self._log(f"Found item: {item_name} x {qty} @ {price} = {amount}")
                except:
                    continue
        
        self.data['items'] = items
        self.confidence['items'] = min(90, len(items) * 25) if items else 20
    
    def _extract_deductions_tkfl(self):
        """Extract deductions"""
        self._log("Extracting deductions...")
        
        deductions = []
        
        deduction_patterns = {
            'Commission': [r'comm', r'comission', r'com?\s*\d'],
            'Damage': [r'damage', r'damages', r'less\s*for\s*damage'],
            'Unloading': [r'unload', r'unloading', r'unld'],
            'L/F Cash': [r'l[/\s]*f', r'lf\s+and\s+cash', r'lfandcash'],
        }
        
        for ded_type, patterns in deduction_patterns.items():
            for pattern in patterns:
                # Look for pattern followed by amount
                full_pattern = rf'(?:{pattern}).*?(\d{{1,5}}\.?\d{{0,2}})'
                match = re.search(full_pattern, self.raw_text, re.IGNORECASE)
                
                if match:
                    try:
                        amount_str = match.group(1)
                        amount = float(amount_str)
                        
                        # Filter unreasonable amounts
                        if 0.1 <= amount <= 5000:
                            # Check for percentage (commission)
                            if '%' in match.group(0) or '4.00' in amount_str or '4.008' in match.group(0):
                                # This might be a percentage - calculate from gross
                                if self.data['gross_total']:
                                    percent = 4.0  # Standard commission %
                                    amount = self.data['gross_total'] * (percent / 100)
                                    ded_type = f'Commission @{percent}%'
                            
                            deductions.append({
                                'deduction_type': ded_type,
                                'amount': round(amount, 2)
                            })
                            self._log(f"Found deduction: {ded_type} = {amount}")
                            break  # Found one for this type
                    except:
                        continue
        
        self.data['deductions'] = deductions
        if deductions:
            self.data['total_deductions'] = sum(d['amount'] for d in deductions)
            self.confidence['deductions'] = min(85, len(deductions) * 40)
        else:
            self.confidence['deductions'] = 30
    
    def _calculate_missing(self):
        """Calculate missing values"""
        # Calculate net from gross - deductions
        if self.data['gross_total'] and self.data['total_deductions']:
            calculated_net = self.data['gross_total'] - self.data['total_deductions']
            
            # If we don't have net, or calculated is more accurate
            if self.data['net_total'] is None:
                self.data['net_total'] = calculated_net
                self.confidence['net_total'] = 70
                self._log(f"Calculated net total: {calculated_net}")
            elif abs(calculated_net - self.data['net_total']) > 100:
                # Large discrepancy - use calculated
                self.data['net_total'] = calculated_net
                self._log(f"Corrected net total to: {calculated_net}")
    
    def _calculate_confidence(self):
        """Calculate overall confidence"""
        field_confs = []
        for field in ['voucher_number', 'voucher_date', 'supplier_name', 'gross_total']:
            conf = self.confidence.get(field, 0)
            field_confs.append(conf)
        
        if field_confs:
            avg_conf = sum(field_confs) / len(field_confs)
            min_conf = min(field_confs)
            # Weight toward minimum (weakest link)
            self.confidence['overall'] = (avg_conf * 0.6) + (min_conf * 0.4)
        else:
            self.confidence['overall'] = 0


def parse_receipt_text_tkfl(ocr_text: str) -> Dict:
    """Main entry point for TKFL-specific parsing"""
    parser = TKFLReceiptParser(ocr_text)
    return parser.parse()


# Backward compatibility alias
parse_receipt_text = parse_receipt_text_tkfl


if __name__ == "__main__":
    # Test with real OCR sample from your data
    test_text = """
    herNuaber151, herDate 07/01/2026
    )Nane JPYK
    a
    Qty Price Amount
    a
    1 280.00 280.00
    2 60.00 120.00
    al 3 400.00
    Comm?4.008 16.00
    1essForDanages 20.00
    Un1oading 24.00
    4.00
    1/FAndCash 120.00
    """
    
    print("Testing TKFL Parser with real sample")
    print("="*60)
    result = parse_receipt_text_tkfl(test_text)
    
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
