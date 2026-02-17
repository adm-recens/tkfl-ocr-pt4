"""
Enhanced Field Parser - Aggressive field extraction from OCR text
Optimized for real-world voucher formats and poor quality OCR
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import json


class EnhancedFieldParser:
    """
    Aggressive parser that extracts fields even from messy OCR output
    Uses multiple strategies, context awareness, and fuzzy matching
    """
    
    def __init__(self, ocr_text: str):
        self.raw_text = ocr_text or ""
        # Keep both original and cleaned versions
        self.cleaned_text = self._clean_text(ocr_text)
        self.lines = [line.strip() for line in self.raw_text.split('\n') if line.strip()]
        self.cleaned_lines = [line.strip() for line in self.cleaned_text.split('\n') if line.strip()]
        
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
        self.debug_info = []
    
    def _clean_text(self, text: str) -> str:
        """Clean OCR text while preserving structure"""
        if not text:
            return ""
        
        # Fix common OCR errors
        corrections = {
            'O': '0',  # Letter O to number 0 in numeric contexts
            'l': '1',  # Lowercase L to number 1
            'I': '1',  # Capital I to number 1
            'S': '5',  # S to 5
            'B': '8',  # B to 8
            'Z': '2',  # Z to 2
        }
        
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Clean the line
            cleaned = line
            
            # Replace multiple spaces with single space
            cleaned = re.sub(r' +', ' ', cleaned)
            
            # Fix common voucher terms
            cleaned = re.sub(r'\bvouc[hn]?er\b', 'Voucher', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\bsupp\.?\s*name\b', 'Supp Name', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\bdate[\s:]*', 'Date ', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\btotal\b', 'Total', cleaned, flags=re.IGNORECASE)
            
            # Only apply character substitutions in numeric contexts
            # Look for patterns like ": 123" or " = 456"
            for old, new in corrections.items():
                # Replace only when followed by digits or when part of a number-like pattern
                pattern = rf'({old})(?=\d|\s*[=:]\s*\d)'
                cleaned = re.sub(pattern, new, cleaned)
            
            cleaned_lines.append(cleaned)
        
        return '\n'.join(cleaned_lines)
    
    def parse(self) -> Dict:
        """Main parsing method"""
        self._debug("Starting enhanced field extraction...")
        
        # Extract fields in order of reliability
        self._extract_voucher_number_aggressive()
        self._extract_date_aggressive()
        self._extract_supplier_aggressive()
        self._extract_totals_aggressive()
        self._extract_items_aggressive()
        self._extract_deductions_aggressive()
        
        # Calculate totals if needed
        self._calculate_missing_totals()
        
        # Calculate confidence
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
            'debug': self.debug_info
        }
    
    def _extract_voucher_number_aggressive(self):
        """Extract voucher number using multiple aggressive strategies"""
        self._debug("Extracting voucher number...")
        
        strategies = [
            # Strategy 1: Look for "Voucher" followed by numbers
            (r'(?:voucher|vouch|vou|v\.?)[\s#:]*(?:no|num|number)?[\s#:]*(\d{3,})', 'voucher_label'),
            # Strategy 2: Standalone number after "No" or "#"
            (r'(?:no\.?|#)\s*:?\s*(\d{3,})', 'no_prefix'),
            # Strategy 3: Look for VoucherNumber pattern
            (r'vouchernumber\s*(\d+)', 'voucher_number_pattern'),
            # Strategy 4: Number at start of line (early in document)
            (r'^\s*(\d{3,5})\s*$', 'standalone_number'),
            # Strategy 5: Any 3-5 digit number preceded by text on same line
            (r'(?:bill|inv|voucher|receipt|no)[:\s]*(\d{3,})', 'context_number'),
        ]
        
        best_match = None
        best_confidence = 0
        best_strategy = None
        
        for pattern, strategy_name in strategies:
            matches = list(re.finditer(pattern, self.cleaned_text, re.IGNORECASE | re.MULTILINE))
            
            for match in matches:
                number = match.group(1).strip()
                
                # Validate it's a reasonable voucher number
                if len(number) < 3 or len(number) > 10:
                    continue
                
                # Calculate confidence based on context
                confidence = 50  # Base confidence
                
                # Higher confidence if has voucher label
                if strategy_name == 'voucher_label':
                    confidence = 90
                elif strategy_name == 'voucher_number_pattern':
                    confidence = 85
                elif strategy_name == 'no_prefix':
                    confidence = 75
                elif strategy_name == 'context_number':
                    confidence = 65
                else:
                    confidence = 50
                
                # Boost if it's early in the document
                match_pos = match.start() / max(len(self.cleaned_text), 1)
                if match_pos < 0.3:  # In first 30% of text
                    confidence += 10
                
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = number
                    best_strategy = strategy_name
        
        if best_match:
            self.data['voucher_number'] = best_match
            self.confidence['voucher_number'] = min(95, best_confidence)
            self._debug(f"Found voucher number: {best_match} (confidence: {best_confidence}%, strategy: {best_strategy})")
        else:
            self._debug("No voucher number found")
            self.confidence['voucher_number'] = 0
    
    def _extract_date_aggressive(self):
        """Extract date using multiple format strategies"""
        self._debug("Extracting date...")
        
        date_formats = [
            # DD/MM/YYYY or DD-MM-YYYY
            (r'(\d{1,2})[\-/](\d{1,2})[\-/](\d{4})', 'DMY'),
            # DD/MM/YY or DD-MM-YY
            (r'(\d{1,2})[\-/](\d{1,2})[\-/](\d{2})', 'DMY_short'),
            # YYYY-MM-DD
            (r'(\d{4})[\-/](\d{1,2})[\-/](\d{1,2})', 'YMD'),
            # DD.MM.YYYY
            (r'(\d{1,2})\.(\d{1,2})\.(\d{4})', 'DMY_dot'),
            # DD Mon YYYY (e.g., 15 Jan 2024)
            (r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})', 'DMY_text'),
        ]
        
        best_date = None
        best_confidence = 0
        
        # First try with "Date" label
        date_section_pattern = r'(?:date|dated)[\s:]*(.*?)(?:\n|$)'
        date_section = re.search(date_section_pattern, self.cleaned_text, re.IGNORECASE)
        
        search_text = date_section.group(1) if date_section else self.cleaned_text
        
        for pattern, fmt_type in date_formats:
            matches = re.finditer(pattern, search_text, re.IGNORECASE)
            
            for match in matches:
                try:
                    if fmt_type == 'DMY':
                        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                        date_obj = datetime(year, month, day)
                    elif fmt_type == 'DMY_short':
                        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                        year = 2000 + year if year < 50 else 1900 + year
                        date_obj = datetime(year, month, day)
                    elif fmt_type == 'YMD':
                        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                        date_obj = datetime(year, month, day)
                    elif fmt_type == 'DMY_dot':
                        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                        date_obj = datetime(year, month, day)
                    elif fmt_type == 'DMY_text':
                        day = int(match.group(1))
                        month_str = match.group(2)
                        year = int(match.group(3))
                        month_map = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                                   'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}
                        month = month_map.get(month_str[:3].title(), 1)
                        date_obj = datetime(year, month, day)
                    else:
                        continue
                    
                    # Validate date is reasonable (not too old, not in future)
                    now = datetime.now()
                    if date_obj.year < 2000 or date_obj > now:
                        continue
                    
                    confidence = 80 if date_section else 70
                    if fmt_type == 'DMY':
                        confidence += 5
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_date = date_obj.strftime('%Y-%m-%d')
                        
                except ValueError:
                    continue
        
        # Try DDMMYYYY format (no separators)
        if not best_date:
            dmy_pattern = r'\b(\d{2})(\d{2})(\d{4})\b'
            match = re.search(dmy_pattern, search_text)
            if match:
                try:
                    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    if 1 <= day <= 31 and 1 <= month <= 12 and 2000 <= year <= 2030:
                        date_obj = datetime(year, month, day)
                        best_date = date_obj.strftime('%Y-%m-%d')
                        best_confidence = 60
                except:
                    pass
        
        if best_date:
            self.data['voucher_date'] = best_date
            self.confidence['voucher_date'] = min(95, best_confidence)
            self._debug(f"Found date: {best_date} (confidence: {best_confidence}%)")
        else:
            self._debug("No date found")
            self.confidence['voucher_date'] = 0
    
    def _extract_supplier_aggressive(self):
        """Extract supplier name using aggressive strategies"""
        self._debug("Extracting supplier...")
        
        # Strategy 1: Look for "Supp Name" pattern
        supp_patterns = [
            r'(?:supp\.?|supplier)[\s:]*(?:name|nm)?[\s:]*(.{2,60}?)(?=\n|$|date|voucher)',
            r'(?:supp\.?|supplier)[\s:]*(.{2,60}?)(?=\n|$|date|voucher)',
            r'(?:from|sold by)[:\s]*(.{2,60}?)(?=\n|$)',
        ]
        
        for pattern in supp_patterns:
            match = re.search(pattern, self.cleaned_text, re.IGNORECASE)
            if match:
                supplier = match.group(1).strip()
                # Clean up
                supplier = re.sub(r'[\d\W]+$', '', supplier).strip()
                if len(supplier) >= 2:
                    self.data['supplier_name'] = supplier
                    self.confidence['supplier_name'] = 80
                    self._debug(f"Found supplier: {supplier}")
                    return
        
        # Strategy 2: Look for text on lines after "Supp" or before "Date"
        for i, line in enumerate(self.cleaned_lines):
            if re.search(r'\bsupp', line, re.IGNORECASE):
                # Check if value is on same line after colon
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        value = parts[1].strip()
                        if len(value) >= 2 and not value.isdigit():
                            self.data['supplier_name'] = value
                            self.confidence['supplier_name'] = 75
                            self._debug(f"Found supplier (same line): {value}")
                            return
                
                # Check previous line
                if i > 0:
                    prev_line = self.cleaned_lines[i-1].strip()
                    if len(prev_line) >= 2 and len(prev_line) <= 50:
                        if not re.search(r'\b(date|voucher|no|total|amount)\b', prev_line, re.IGNORECASE):
                            if not prev_line.isdigit():
                                self.data['supplier_name'] = prev_line
                                self.confidence['supplier_name'] = 70
                                self._debug(f"Found supplier (previous line): {prev_line}")
                                return
                
                # Check next line
                if i < len(self.cleaned_lines) - 1:
                    next_line = self.cleaned_lines[i+1].strip()
                    if len(next_line) >= 2 and len(next_line) <= 50:
                        if not re.search(r'\b(date|voucher|no|total|amount)\b', next_line, re.IGNORECASE):
                            if not next_line.isdigit():
                                self.data['supplier_name'] = next_line
                                self.confidence['supplier_name'] = 70
                                self._debug(f"Found supplier (next line): {next_line}")
                                return
        
        # Strategy 3: Look for company-like names in first few lines
        for line in self.cleaned_lines[:5]:
            # Look for lines that look like company names (all caps or title case)
            if line.isupper() and len(line) >= 3 and len(line) <= 40:
                if not any(word in line.lower() for word in ['date', 'voucher', 'total', 'amount', 'no']):
                    self.data['supplier_name'] = line.title()
                    self.confidence['supplier_name'] = 50
                    self._debug(f"Found supplier (company name pattern): {line.title()}")
                    return
        
        self._debug("No supplier found")
        self.confidence['supplier_name'] = 0
    
    def _extract_totals_aggressive(self):
        """Extract totals using aggressive strategies"""
        self._debug("Extracting totals...")
        
        # Find all decimal numbers in the text
        decimal_pattern = r'\b(\d{1,6}\.\d{2})\b'
        all_amounts = []
        
        for match in re.finditer(decimal_pattern, self.cleaned_text):
            try:
                amount = float(match.group(1))
                position = match.start()
                context = self.cleaned_text[max(0, position-50):position+50]
                all_amounts.append((amount, position, context))
            except:
                continue
        
        if not all_amounts:
            self._debug("No amounts found")
            return
        
        # Sort by amount (largest first)
        all_amounts.sort(key=lambda x: x[0], reverse=True)
        
        # Strategy 1: Look for "Grand Total" or "Net Total"
        net_total = None
        gross_total = None
        
        for amount, position, context in all_amounts:
            context_lower = context.lower()
            
            # Check for net/grand total
            if any(word in context_lower for word in ['grand total', 'net total', 'net amount', 'payable']):
                if net_total is None:
                    net_total = amount
                    self._debug(f"Found net total: {amount}")
            
            # Check for gross/subtotal
            elif any(word in context_lower for word in ['gross', 'sub total', 'subtotal', 'total amount']):
                if gross_total is None:
                    gross_total = amount
                    self._debug(f"Found gross total: {amount}")
        
        # Strategy 2: Use largest amounts if not found with labels
        if net_total is None and all_amounts:
            # Usually the last or second-to-last amount is the total
            # Check context for "total" keyword
            for amount, position, context in all_amounts[:5]:
                if 'total' in context.lower() or amount > 100:
                    net_total = amount
                    self._debug(f"Found net total (by value): {amount}")
                    break
            
            if net_total is None:
                net_total = all_amounts[0][0]
                self._debug(f"Using largest amount as net total: {net_total}")
        
        if gross_total is None and len(all_amounts) > 1:
            # Second largest might be gross
            for amount, position, context in all_amounts[1:5]:
                if amount < net_total and amount > net_total * 0.5:
                    gross_total = amount
                    self._debug(f"Found gross total (by value): {amount}")
                    break
        
        if net_total:
            self.data['net_total'] = net_total
            self.confidence['net_total'] = 75
        
        if gross_total:
            self.data['gross_total'] = gross_total
            self.confidence['gross_total'] = 70
        else:
            # If no gross but have net, assume they're the same
            self.data['gross_total'] = net_total
            self.confidence['gross_total'] = 50
    
    def _extract_items_aggressive(self):
        """Extract line items"""
        self._debug("Extracting items...")
        
        items = []
        
        # Pattern: Description Qty Price Amount
        # Look for lines with 3-4 numeric values
        for line in self.cleaned_lines:
            # Find all numbers in the line
            numbers = re.findall(r'\b(\d+\.?\d*)\b', line)
            
            if len(numbers) >= 3:
                # Check if last 3 numbers could be qty, price, amount
                try:
                    qty = float(numbers[-3])
                    price = float(numbers[-2])
                    amount = float(numbers[-1])
                    
                    # Validate: amount should roughly equal qty * price
                    if abs(amount - (qty * price)) < 1 or abs(amount - (qty * price)) / max(amount, 1) < 0.05:
                        # Extract item name (everything before the numbers)
                        item_part = line
                        for num in numbers[-3:]:
                            item_part = item_part.replace(num, '', 1)
                        item_name = re.sub(r'[^\w\s]', '', item_part).strip()
                        
                        if len(item_name) >= 2:
                            items.append({
                                'item_name': item_name or 'Item',
                                'quantity': qty,
                                'unit_price': price,
                                'line_amount': amount
                            })
                            self._debug(f"Found item: {item_name} x {qty} @ {price} = {amount}")
                except:
                    continue
        
        self.data['items'] = items
        self.confidence['items'] = min(90, len(items) * 30) if items else 20
    
    def _extract_deductions_aggressive(self):
        """Extract deductions"""
        self._debug("Extracting deductions...")
        
        deductions = []
        
        deduction_keywords = {
            'Commission': [r'comm', r'comission'],
            'Damage': [r'damage', r'damages', r'less for damage'],
            'Unloading': [r'unload', r'unloading'],
            'L/F Cash': [r'l[/\s]*f', r'cash'],
            'Other': [r'other', r'misc']
        }
        
        for ded_type, patterns in deduction_keywords.items():
            for pattern in patterns:
                # Look for keyword followed by amount
                full_pattern = rf'(?:{pattern}).*?(\d+\.?\d*)'
                match = re.search(full_pattern, self.cleaned_text, re.IGNORECASE)
                
                if match:
                    try:
                        amount = float(match.group(1))
                        if amount > 0 and amount < 100000:  # Reasonable amount
                            deductions.append({
                                'deduction_type': ded_type,
                                'amount': amount
                            })
                            self._debug(f"Found deduction: {ded_type} = {amount}")
                            break  # Found one for this type
                    except:
                        continue
        
        self.data['deductions'] = deductions
        if deductions:
            self.data['total_deductions'] = sum(d['amount'] for d in deductions)
            self.confidence['deductions'] = min(85, len(deductions) * 40)
        else:
            self.confidence['deductions'] = 30
    
    def _calculate_missing_totals(self):
        """Calculate missing totals from items and deductions"""
        if self.data['gross_total'] is None and self.data['items']:
            self.data['gross_total'] = sum(item['line_amount'] for item in self.data['items'])
            self.confidence['gross_total'] = self.confidence.get('gross_total', 0) + 10
        
        if self.data['net_total'] is None:
            if self.data['gross_total'] and self.data['total_deductions']:
                self.data['net_total'] = self.data['gross_total'] - self.data['total_deductions']
                self.confidence['net_total'] = 60
            elif self.data['gross_total']:
                self.data['net_total'] = self.data['gross_total']
                self.confidence['net_total'] = 55
    
    def _calculate_confidence(self):
        """Calculate overall confidence"""
        field_confs = []
        for field in ['voucher_number', 'voucher_date', 'supplier_name', 'net_total']:
            conf = self.confidence.get(field, 0)
            field_confs.append(conf)
        
        if field_confs:
            avg_conf = sum(field_confs) / len(field_confs)
            min_conf = min(field_confs)
            # Weight toward minimum
            self.confidence['overall'] = (avg_conf * 0.6) + (min_conf * 0.4)
        else:
            self.confidence['overall'] = 0
    
    def _debug(self, message: str):
        """Add debug message"""
        self.debug_info.append(message)
        print(f"[PARSER] {message}")


def parse_receipt_text_enhanced(ocr_text: str) -> Dict:
    """Main entry point for enhanced parsing"""
    parser = EnhancedFieldParser(ocr_text)
    return parser.parse()


# Backward compatibility
parse_receipt_text = parse_receipt_text_enhanced


if __name__ == "__main__":
    # Test with sample OCR text
    test_text = """
    TKFL STORES
    Voucher No: 1234
    Date: 15/03/2024
    Supp Name: ABC Suppliers Pvt Ltd
    
    Item One          10    50.00    500.00
    Item Two           5   100.00    500.00
    
    Commission          50.00
    Damages             25.00
    
    Gross Total       1000.00
    Net Total          925.00
    """
    
    print("Testing Enhanced Parser")
    print("=" * 60)
    result = parse_receipt_text_enhanced(test_text)
    
    print("\n📋 EXTRACTED DATA:")
    print("-" * 40)
    for key, value in result['master'].items():
        conf = result['confidence'].get(key, 0)
        status = "✅" if conf >= 70 else "⚠️" if conf >= 50 else "❌"
        print(f"{status} {key:20s}: {value} ({conf:.0f}%)")
    
    print(f"\nItems: {len(result['items'])}")
    print(f"Deductions: {len(result['deductions'])}")
    print(f"\nOverall Confidence: {result['confidence'].get('overall', 0):.1f}%")
