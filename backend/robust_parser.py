"""
Robust Parser - Enhanced parsing for poor quality OCR output
Uses fuzzy matching, multiple pattern attempts, and heuristics to extract data
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from difflib import get_close_matches
import json


class RobustReceiptParser:
    """
    Enhanced parser that handles poor quality OCR better than the standard parser
    Uses multiple strategies, fuzzy matching, and confidence scoring
    """
    
    # Expanded patterns for common OCR errors
    VOUCHER_PATTERNS = [
        r'(?:voucher|vouch|vou|vouc)[\s]*(?:no|num|number|#)?[:\s]*[#]?(\d{3,})',
        r'(?:v|vou)[\.\s]*(?:no|number)?[:\s]*(\d{3,})',
        r'(?:bill|invoice|receipt)[\s]*(?:no|number)?[:\s]*(\d{3,})',
        r'\b(?:no|#)[:\s]*(\d{3,})\b',
        r'(?:voucher\s*number|voucher\s*no)[:\s]*(\d{3,})',
    ]
    
    DATE_PATTERNS = [
        r'(?:date|dated|dt)[:\s]*(\d{1,2}[\-\/\.\s]\d{1,2}[\-\/\.\s]\d{2,4})',
        r'(?:date|dated)[:\s]*(\d{1,2}[\-\/\.\s]\w+[\-\/\.\s]\d{2,4})',
        r'(\d{1,2}[\-\/\.\s]\d{1,2}[\-\/\.\s]\d{4})',
        r'(\d{1,2}[\-\/\.\s]\d{1,2}[\-\/\.\s]\d{2})',
        r'(\d{8})',  # DDMMYYYY format
    ]
    
    SUPPLIER_PATTERNS = [
        r'(?:supp|supplier|sup)[\.\s]*(?:name|nam|nm)?[:\s]*(.{3,50})',
        r'(?:supp|supplier)[:\s]*(.{3,50})',
        r'(?:from|sold\s*by)[:\s]*(.{3,50})',
    ]
    
    AMOUNT_PATTERNS = [
        r'(?:total|tot|amount|amt)[:\s]*([\d,]+\.?\d{0,2})',
        r'(?:grand\s*total|net\s*total|gross)[:\s]*([\d,]+\.?\d{0,2})',
        r'(?:rs\.?|₹)\s*([\d,]+\.?\d{0,2})',
        r'\btotal\b.*?([\d,]+\.\d{2})',
    ]
    
    DEDUCTION_KEYWORDS = {
        'commission': ['comm', 'comission', 'com', 'comm.', 'commission'],
        'damage': ['damage', 'dmg', 'damages', 'less for damage'],
        'unloading': ['unload', 'unloading', 'unld', 'loading'],
        'lf_cash': ['l/f', 'lf', 'l/f and cash', 'cash'],
        'other': ['other', 'misc', 'miscellaneous']
    }
    
    def __init__(self, ocr_text: str, field_confidence: Dict[str, float] = None):
        """
        Initialize parser with OCR text and optional field confidence scores
        """
        self.raw_text = ocr_text or ""
        self.lines = [line.strip() for line in self.raw_text.split('\n') if line.strip()]
        self.field_confidence = field_confidence or {}
        self.extracted_data = {
            'master': {},
            'items': [],
            'deductions': [],
            'confidence': {}
        }
    
    def parse(self) -> Dict:
        """
        Main parsing method - tries multiple strategies
        Returns structured data with confidence scores
        """
        # Try standard extraction first
        self._extract_voucher_number()
        self._extract_date()
        self._extract_supplier()
        self._extract_totals()
        self._extract_items()
        self._extract_deductions()
        
        # If critical fields missing, try fuzzy matching
        if not self.extracted_data['master'].get('voucher_number'):
            self._fuzzy_extract_voucher()
        
        if not self.extracted_data['master'].get('voucher_date'):
            self._fuzzy_extract_date()
        
        if not self.extracted_data['master'].get('supplier_name'):
            self._fuzzy_extract_supplier()
        
        # Calculate overall confidence
        self._calculate_confidence()
        
        return self.extracted_data
    
    def _extract_voucher_number(self):
        """Extract voucher number using multiple patterns"""
        best_match = None
        best_confidence = 0
        
        for pattern in self.VOUCHER_PATTERNS:
            matches = re.finditer(pattern, self.raw_text, re.IGNORECASE)
            for match in matches:
                voucher_num = match.group(1).strip()
                # Validate: should be mostly digits and reasonable length
                if len(voucher_num) >= 3 and len(voucher_num) <= 20:
                    digits = sum(1 for c in voucher_num if c.isdigit())
                    confidence = (digits / len(voucher_num)) * 100
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = voucher_num
        
        if best_match:
            self.extracted_data['master']['voucher_number'] = best_match
            self.extracted_data['confidence']['voucher_number'] = best_confidence
    
    def _extract_date(self):
        """Extract date using multiple formats"""
        best_date = None
        best_confidence = 0
        
        for pattern in self.DATE_PATTERNS:
            matches = re.finditer(pattern, self.raw_text, re.IGNORECASE)
            for match in matches:
                date_str = match.group(1).strip()
                parsed_date = self._try_parse_date(date_str)
                
                if parsed_date:
                    # Higher confidence for standard formats
                    confidence = 80
                    if '/' in date_str or '-' in date_str:
                        confidence = 90
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_date = parsed_date
        
        if best_date:
            self.extracted_data['master']['voucher_date'] = best_date
            self.extracted_data['confidence']['voucher_date'] = best_confidence
    
    def _try_parse_date(self, date_str: str) -> Optional[str]:
        """Try to parse date from various formats"""
        date_str = date_str.strip()
        
        # Handle DDMMYYYY format
        if re.match(r'^\d{8}$', date_str):
            try:
                day = int(date_str[:2])
                month = int(date_str[2:4])
                year = int(date_str[4:])
                if year < 100:
                    year += 2000
                dt = datetime(year, month, day)
                return dt.strftime('%Y-%m-%d')
            except:
                pass
        
        # Try various separators
        for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y', 
                    '%d/%m/%y', '%d-%m-%y', '%d.%m.%y',
                    '%Y-%m-%d', '%d %b %Y', '%d %B %Y']:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except:
                continue
        
        return None
    
    def _extract_supplier(self):
        """Extract supplier name"""
        for pattern in self.SUPPLIER_PATTERNS:
            match = re.search(pattern, self.raw_text, re.IGNORECASE)
            if match:
                supplier = match.group(1).strip()
                # Clean up - remove trailing punctuation and numbers
                supplier = re.sub(r'[\d\W]+$', '', supplier)
                if len(supplier) >= 2:
                    self.extracted_data['master']['supplier_name'] = supplier
                    self.extracted_data['confidence']['supplier_name'] = 75
                    return
        
        # Fallback: Look for text in first few lines that could be supplier
        for line in self.lines[:5]:
            # Skip lines with numbers only or common headers
            if re.match(r'^(date|voucher|bill|invoice|no|#)', line, re.IGNORECASE):
                continue
            if len(line) >= 3 and len(line) <= 50 and not line.isdigit():
                words = line.split()
                if len(words) >= 1:
                    self.extracted_data['master']['supplier_name'] = line
                    self.extracted_data['confidence']['supplier_name'] = 50
                    return
    
    def _extract_totals(self):
        """Extract gross, net, and deduction totals"""
        amounts = []
        
        # Find all amounts in text
        for pattern in self.AMOUNT_PATTERNS:
            matches = re.finditer(pattern, self.raw_text, re.IGNORECASE)
            for match in matches:
                amount_str = match.group(1).replace(',', '')
                try:
                    amount = float(amount_str)
                    if amount > 0:
                        amounts.append(amount)
                except:
                    continue
        
        # Also find standalone decimal numbers
        decimal_pattern = r'\b(\d{3,}\.\d{2})\b'
        matches = re.finditer(decimal_pattern, self.raw_text)
        for match in matches:
            try:
                amount = float(match.group(1))
                if amount > 10:  # Filter out small numbers
                    amounts.append(amount)
            except:
                continue
        
        if amounts:
            # Assume largest is gross/net total
            amounts.sort(reverse=True)
            self.extracted_data['master']['net_total'] = amounts[0]
            self.extracted_data['confidence']['net_total'] = 70
            
            if len(amounts) > 1:
                # Second largest might be gross or a subtotal
                self.extracted_data['master']['gross_total'] = amounts[1]
                self.extracted_data['confidence']['gross_total'] = 65
    
    def _extract_items(self):
        """Extract line items from the receipt"""
        items = []
        
        # Pattern: description + quantity + price + amount
        item_pattern = r'(.{3,40})\s+(\d{1,5})\s+(\d+\.?\d{0,2})\s+(\d+\.?\d{0,2})'
        
        for match in re.finditer(item_pattern, self.raw_text):
            try:
                item = {
                    'item_name': match.group(1).strip(),
                    'quantity': float(match.group(2)),
                    'unit_price': float(match.group(3)),
                    'line_amount': float(match.group(4))
                }
                items.append(item)
            except:
                continue
        
        self.extracted_data['items'] = items
        self.extracted_data['confidence']['items'] = min(90, len(items) * 30) if items else 30
    
    def _extract_deductions(self):
        """Extract deduction items using keyword matching"""
        deductions = []
        
        for ded_type, keywords in self.DEDUCTION_KEYWORDS.items():
            for keyword in keywords:
                # Look for keyword followed by amount
                pattern = rf'{re.escape(keyword)}.*?([\d,]+\.?\d{{0,2}})'
                matches = re.finditer(pattern, self.raw_text, re.IGNORECASE)
                
                for match in matches:
                    try:
                        amount_str = match.group(1).replace(',', '')
                        amount = float(amount_str)
                        
                        if amount > 0:
                            deductions.append({
                                'deduction_type': ded_type.replace('_', ' ').title(),
                                'amount': amount
                            })
                            break  # Found one for this type
                    except:
                        continue
        
        self.extracted_data['deductions'] = deductions
        if deductions:
            self.extracted_data['master']['total_deductions'] = sum(d['amount'] for d in deductions)
            self.extracted_data['confidence']['deductions'] = min(85, len(deductions) * 40)
    
    def _fuzzy_extract_voucher(self):
        """Fuzzy matching for voucher number when standard patterns fail"""
        # Look for any 3+ digit numbers that might be voucher numbers
        numbers = re.findall(r'\b(\d{3,6})\b', self.raw_text)
        
        if numbers:
            # Prefer numbers that appear early in the document
            for num in numbers[:5]:
                # Check if it's not likely a date or amount
                if not re.search(rf'\d{{1,2}}[/-]{num}|{num}[/-]\d{{1,2}}', self.raw_text):
                    if float(num) < 100000:  # Reasonable voucher number range
                        self.extracted_data['master']['voucher_number'] = num
                        self.extracted_data['confidence']['voucher_number'] = 40
                        return
    
    def _fuzzy_extract_date(self):
        """Fuzzy matching for date when standard patterns fail"""
        # Look for any potential date strings
        potential_dates = re.findall(r'\b(\d{1,2}[\s/-]\d{1,2}[\s/-]\d{2,4})\b', self.raw_text)
        
        for date_str in potential_dates:
            parsed = self._try_parse_date(date_str)
            if parsed:
                self.extracted_data['master']['voucher_date'] = parsed
                self.extracted_data['confidence']['voucher_date'] = 45
                return
    
    def _fuzzy_extract_supplier(self):
        """Fuzzy matching for supplier when standard patterns fail"""
        # Look for capitalized words that might be company names
        for line in self.lines:
            words = line.split()
            if len(words) >= 2 and len(words) <= 6:
                # Check if mostly title case
                title_words = sum(1 for w in words if w and w[0].isupper())
                if title_words >= len(words) * 0.7:
                    if not any(char.isdigit() for char in line):
                        self.extracted_data['master']['supplier_name'] = line
                        self.extracted_data['confidence']['supplier_name'] = 35
                        return
    
    def _calculate_confidence(self):
        """Calculate overall extraction confidence"""
        confidences = []
        
        for field, conf in self.extracted_data['confidence'].items():
            if field != 'overall':
                confidences.append(conf)
        
        if confidences:
            avg_confidence = sum(confidences) / len(confidences)
            min_confidence = min(confidences)
            
            # Weight toward minimum (weakest link)
            self.extracted_data['confidence']['overall'] = (avg_confidence * 0.6) + (min_confidence * 0.4)
        else:
            self.extracted_data['confidence']['overall'] = 30


def parse_receipt_text_robust(ocr_text: str, field_confidence: Dict[str, float] = None) -> Dict:
    """
    Convenience function for robust parsing
    Returns data structure compatible with existing code
    """
    parser = RobustReceiptParser(ocr_text, field_confidence)
    result = parser.parse()
    
    # Format to match existing structure
    return {
        'master': result['master'],
        'items': result.get('items', []),
        'deductions': result.get('deductions', []),
        'confidence': result.get('confidence', {})
    }


# Backward compatibility wrapper
def parse_receipt_text(ocr_text: str) -> Dict:
    """
    Wrapper that maintains compatibility with existing code
    Uses robust parser internally
    """
    return parse_receipt_text_robust(ocr_text)


if __name__ == "__main__":
    # Test the robust parser
    import sys
    
    test_text = """
    TKFL Stores
    Voucner No: 457
    Date: 15/03/2024
    Supp Name: ABC Suppliers
    
    Item1              10   50.00   500.00
    Item2               5  100.00   500.00
    
    Comm                 50.00
    Damages              25.00
    
    Total                         1000.00
    """
    
    print("Testing Robust Parser")
    print("=" * 60)
    result = parse_receipt_text_robust(test_text)
    
    print("\nExtracted Master Data:")
    for key, value in result['master'].items():
        print(f"  {key}: {value}")
    
    print("\nConfidence Scores:")
    for field, conf in result['confidence'].items():
        print(f"  {field}: {conf}%")
    
    print(f"\nItems: {len(result['items'])}")
    print(f"Deductions: {len(result['deductions'])}")
