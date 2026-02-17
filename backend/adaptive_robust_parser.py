"""
Adaptive Robust Parser - Learns patterns from all vouchers
Uses multiple strategies, confidence scoring, and intelligent validation
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import json


class AdaptiveRobustParser:
    """
    Parser that adapts to various OCR quality levels
    Uses multiple strategies with confidence scoring and validation
    """
    
    # Common OCR error patterns learned from analysis
    OCR_VARIATIONS = {
        'voucher_number': [
            r'voucher\s*(?:number|no|#)?[:\s]*(\d{2,4})\b',
            r'(?:nuaber|nunber|nunmber|nuamber|number)[:\s]*(\d{2,4})\b',
            r'\bv[\s\.]*(?:no|num|#)?[:\s]*(\d{2,4})\b',
        ],
        'date': [
            r'(?:voucherdate|voucher\s*date|date)[:\s]*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
            r'(\d{1,2}[\/\-]\d{1,2}[\/\-]20\d{2})',
        ],
        'supplier': [
            r'(?:supp\s*name|suppname|suppnane|suppnare|name)[:\s]*(.{2,30}?)(?=\n|$|qty|total|price)',
            r'(?:supp|supplier)[:\s]*(.{2,30}?)(?=\n|$|qty)',
        ],
    }
    
    # Validation rules
    VALIDATION_RULES = {
        'voucher_number': {
            'min_length': 2,
            'max_length': 4,
            'exclude_range': (2020, 2030),  # Don't accept years
            'must_be_numeric': True,
        },
        'gross_total': {
            'min_value': 10,
            'max_value': 100000,
        },
        'deduction': {
            'min_value': 0.1,
            'max_value': 5000,
            'max_percent_of_gross': 50,  # Deduction can't be > 50% of gross
        }
    }
    
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
        self.attempts = defaultdict(list)  # Track what was tried
    
    def _log(self, msg):
        """Log debug message"""
        self.debug.append(msg)
        print(f"[ADAPTIVE] {msg}")
    
    def parse(self) -> Dict:
        """Main parsing with multiple strategies and confidence scoring"""
        self._log("Starting adaptive robust parsing...")
        
        # Extract each field with multiple attempts
        self._extract_field_adaptive('voucher_number', self._extract_voucher_number)
        self._extract_field_adaptive('voucher_date', self._extract_date)
        self._extract_field_adaptive('supplier_name', self._extract_supplier)
        self._extract_field_adaptive('gross_total', self._extract_gross_total)
        
        # These depend on previous extractions
        self._extract_items()
        self._extract_deductions()
        self._calculate_net_total()
        
        # Final confidence calculation
        self._calculate_overall_confidence()
        
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
            'attempts': dict(self.attempts),
            'debug': self.debug
        }
    
    def _extract_field_adaptive(self, field_name: str, extractor_func):
        """Extract a field with multiple strategies and pick best result"""
        self._log(f"Extracting {field_name}...")
        
        # Try multiple strategies
        results = extractor_func()
        
        if results:
            # Pick result with highest confidence that passes validation
            for result, confidence in sorted(results, key=lambda x: x[1], reverse=True):
                if self._validate_field(field_name, result):
                    self.data[field_name] = result
                    self.confidence[field_name] = confidence
                    self._log(f"✓ {field_name}: {result} (confidence: {confidence}%)")
                    return
        
        self._log(f"✗ {field_name}: Not found or failed validation")
        self.confidence[field_name] = 0
    
    def _extract_voucher_number(self) -> List[Tuple[str, int]]:
        """Extract voucher number using multiple strategies"""
        results = []
        
        # Strategy 1: Look for OCR variation patterns
        for pattern in self.OCR_VARIATIONS['voucher_number']:
            for match in re.finditer(pattern, self.raw_text, re.IGNORECASE):
                num = match.group(1)
                # Context-based confidence
                confidence = 70 if 'voucher' in match.group(0).lower() else 60
                results.append((num, confidence))
                self.attempts['voucher_number'].append(f"Pattern: {pattern[:30]}... -> {num}")
        
        # Strategy 2: Look for standalone numbers early in document
        for i, line in enumerate(self.lines[:5]):
            match = re.search(r'\b(\d{3,4})\b', line)
            if match:
                num = match.group(1)
                # Skip if it's a year
                if 2020 <= int(num) <= 2030:
                    continue
                # Check if line has voucher-related words
                if any(word in line.lower() for word in ['voucher', 'number', 'nuaber', 'nunber']):
                    results.append((num, 50))
                    self.attempts['voucher_number'].append(f"Early line {i}: {num}")
        
        return results
    
    def _extract_date(self) -> List[Tuple[str, int]]:
        """Extract date using multiple strategies"""
        results = []
        
        # Strategy 1: OCR variation patterns
        for pattern in self.OCR_VARIATIONS['date']:
            for match in re.finditer(pattern, self.raw_text, re.IGNORECASE):
                date_str = match.group(1)
                parsed = self._parse_date(date_str)
                if parsed:
                    confidence = 85 if 'voucherdate' in match.group(0).lower() else 75
                    results.append((parsed, confidence))
                    self.attempts['voucher_date'].append(f"Pattern: {pattern[:30]}... -> {parsed}")
        
        # Strategy 2: Generic date patterns
        for line in self.lines[:10]:
            match = re.search(r'(\d{1,2})[\/\-](\d{1,2})[\/\-](20\d{2})', line)
            if match:
                try:
                    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    if 2020 <= year <= 2030:
                        dt = datetime(year, month, day)
                        parsed = dt.strftime('%Y-%m-%d')
                        results.append((parsed, 60))
                        self.attempts['voucher_date'].append(f"Generic pattern: {parsed}")
                except:
                    continue
        
        return results
    
    def _extract_supplier(self) -> List[Tuple[str, int]]:
        """Extract supplier using multiple strategies"""
        results = []
        
        # Strategy 1: OCR variation patterns
        for pattern in self.OCR_VARIATIONS['supplier']:
            for match in re.finditer(pattern, self.raw_text, re.IGNORECASE):
                supplier = match.group(1).strip()
                supplier = re.sub(r'[\d\W]+$', '', supplier)  # Clean trailing garbage
                if len(supplier) >= 2:
                    confidence = 80 if 'supp' in match.group(0).lower() else 65
                    results.append((supplier, confidence))
                    self.attempts['supplier_name'].append(f"Pattern: {pattern[:30]}... -> {supplier}")
        
        # Strategy 2: Line after "Name" indicator
        for i, line in enumerate(self.lines):
            if re.search(r'\b(nane|name|nme)\b', line, re.IGNORECASE):
                # Check same line after label
                parts = re.split(r'(?:nane|name|nme)[:\s]*', line, flags=re.IGNORECASE)
                if len(parts) > 1:
                    supplier = parts[1].strip()
                    supplier = re.sub(r'[\d\W]+$', '', supplier)
                    if len(supplier) >= 2:
                        results.append((supplier, 70))
                        self.attempts['supplier_name'].append(f"Same line after Name: {supplier}")
                
                # Check next line
                if i < len(self.lines) - 1:
                    next_line = self.lines[i + 1].strip()
                    if not re.search(r'\b(qty|price|amount|total)\b', next_line, re.IGNORECASE):
                        if len(next_line) >= 2 and len(next_line) <= 30 and not next_line.isdigit():
                            results.append((next_line, 60))
                            self.attempts['supplier_name'].append(f"Next line: {next_line}")
        
        return results
    
    def _extract_gross_total(self) -> List[Tuple[float, int]]:
        """Extract gross total - prioritize 'Total' line"""
        results = []
        
        # Strategy 1: Look for "Total X YYYY.YY" pattern (TKFL format)
        pattern = r'(?:^|\s|t)(?:otal|tal)[\s]*(\d+)[\s]*(\d{1,5}\.\d{2})'
        for match in re.finditer(pattern, self.raw_text, re.IGNORECASE | re.MULTILINE):
            try:
                amount = float(match.group(2))
                if 10 <= amount <= 100000:
                    results.append((amount, 90))  # High confidence for Total line
                    self.attempts['gross_total'].append(f"Total line: {amount}")
            except:
                continue
        
        # Strategy 2: Largest reasonable amount
        amounts = []
        for match in re.finditer(r'\b(\d{3,5}\.\d{2})\b', self.raw_text):
            try:
                amount = float(match.group(1))
                if 50 <= amount <= 100000:
                    amounts.append(amount)
            except:
                continue
        
        if amounts:
            largest = max(amounts)
            results.append((largest, 50))
            self.attempts['gross_total'].append(f"Largest amount: {largest}")
        
        return results
    
    def _extract_items(self):
        """Extract line items"""
        items = []
        
        for line in self.lines:
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
    
    def _extract_deductions(self):
        """Extract deductions with validation"""
        deductions = []
        
        deduction_types = {
            'Commission': [r'comm', r'comission'],
            'Damage': [r'damage', r'damages'],
            'Unloading': [r'unload', r'unloading'],
            'L/F Cash': [r'l[/\s]*f', r'lfandcash'],
        }
        
        for ded_type, patterns in deduction_types.items():
            for pattern in patterns:
                full_pattern = rf'(?:{pattern}).*?(\d{{1,5}}\.?\d{{0,2}})'
                for match in re.finditer(full_pattern, self.raw_text, re.IGNORECASE):
                    try:
                        amount = float(match.group(1))
                        
                        # Validate
                        if not (0.1 <= amount <= 5000):
                            continue
                        
                        # Check if reasonable compared to gross
                        if self.data['gross_total']:
                            percent = (amount / self.data['gross_total']) * 100
                            if percent > 50:  # Deduction > 50% of gross is suspicious
                                continue
                        
                        # Handle commission percentage
                        if 'comm' in ded_type.lower() and amount < 100:
                            if self.data['gross_total']:
                                amount = self.data['gross_total'] * 0.04
                                ded_type = 'Commission @4%'
                        
                        deductions.append({
                            'deduction_type': ded_type,
                            'amount': round(amount, 2)
                        })
                        break
                    except:
                        continue
        
        self.data['deductions'] = deductions
        if deductions:
            self.data['total_deductions'] = sum(d['amount'] for d in deductions)
    
    def _calculate_net_total(self):
        """Calculate net total"""
        if self.data['gross_total']:
            if self.data['total_deductions']:
                self.data['net_total'] = self.data['gross_total'] - self.data['total_deductions']
            else:
                self.data['net_total'] = self.data['gross_total']
            self.confidence['net_total'] = 70
    
    def _validate_field(self, field_name: str, value) -> bool:
        """Validate extracted field value"""
        rules = self.VALIDATION_RULES.get(field_name, {})
        
        if field_name == 'voucher_number':
            if not value or not str(value).isdigit():
                return False
            num = int(value)
            if rules.get('min_length') and len(str(value)) < rules['min_length']:
                return False
            if rules.get('max_length') and len(str(value)) > rules['max_length']:
                return False
            if rules.get('exclude_range'):
                min_val, max_val = rules['exclude_range']
                if min_val <= num <= max_val:
                    return False
        
        elif field_name in ['gross_total', 'net_total']:
            if not isinstance(value, (int, float)):
                return False
            if rules.get('min_value') and value < rules['min_value']:
                return False
            if rules.get('max_value') and value > rules['max_value']:
                return False
        
        return True
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string"""
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
    
    def _calculate_overall_confidence(self):
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


def parse_receipt_text_adaptive(ocr_text: str) -> Dict:
    """Main entry point"""
    parser = AdaptiveRobustParser(ocr_text)
    return parser.parse()


# Backward compatibility
parse_receipt_text = parse_receipt_text_adaptive


if __name__ == "__main__":
    # Test with real sample
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
    
    print("Testing Adaptive Robust Parser")
    print("="*60)
    result = parse_receipt_text_adaptive(test_text)
    
    print("\n📋 EXTRACTED DATA:")
    print("-" * 40)
    for key, value in result['master'].items():
        if value is not None:
            print(f"✓ {key:20s}: {value}")
        else:
            print(f"✗ {key:20s}: NOT FOUND")
    
    print(f"\nConfidence Scores:")
    for field, conf in result['confidence'].items():
        if field != 'overall':
            print(f"  {field}: {conf}%")
    
    print(f"\nOverall Confidence: {result['confidence'].get('overall', 0):.1f}%")
    print(f"\nItems: {len(result['items'])}")
    print(f"Deductions: {len(result['deductions'])}")
