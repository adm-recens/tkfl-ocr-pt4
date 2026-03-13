"""
Quality-Focused Extraction Engine (QFEE)
Prioritizes accuracy over speed through multi-strategy extraction and rigorous validation
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
from enum import Enum
import json


class ExtractionStatus(Enum):
    HIGH_CONFIDENCE = "high_confidence"      # > 85% - Auto-accept
    MEDIUM_CONFIDENCE = "medium_confidence"  # 60-85% - Flag for review
    LOW_CONFIDENCE = "low_confidence"        # < 60% - Reject/flag
    VALIDATION_FAILED = "validation_failed"  # Failed validation rules
    NOT_FOUND = "not_found"                  # No extraction possible


@dataclass
class ExtractionAttempt:
    """Represents a single extraction attempt"""
    strategy: str
    value: Any
    confidence: int
    context: str  # The text context where found
    validation_passed: bool
    validation_errors: List[str]


@dataclass
class FieldResult:
    """Final result for a field extraction"""
    value: Any
    confidence: int
    status: ExtractionStatus
    attempts: List[ExtractionAttempt]
    best_attempt: Optional[ExtractionAttempt]
    recommendation: str  # What to do with this field


class ValidationRules:
    """Centralized validation rules for all fields"""
    
    @staticmethod
    def validate_voucher_number(value: str) -> Tuple[bool, List[str]]:
        """Validate voucher number"""
        errors = []
        
        if not value:
            return False, ["Empty value"]
        
        # Must be numeric
        if not value.isdigit():
            errors.append("Must be numeric")
            return False, errors
        
        num = int(value)
        
        # Length check
        if len(value) < 2:
            errors.append("Too short (minimum 2 digits)")
        if len(value) > 5:
            errors.append("Too long (maximum 5 digits)")
        
        # CRITICAL: Can't be a year
        if 2020 <= num <= 2030:
            errors.append("Value is a year (2020-2030), not a voucher number")
        
        # Can't be a month/day
        if 1 <= num <= 31:
            errors.append("Value looks like a day/month")
        
        # Reasonable range for voucher numbers
        if num < 1 or num > 99999:
            errors.append("Outside reasonable voucher number range")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_date(value: str) -> Tuple[bool, List[str]]:
        """Validate date"""
        errors = []
        
        if not value:
            return False, ["Empty value"]
        
        # Try to parse
        try:
            dt = datetime.strptime(value, '%Y-%m-%d')
            
            # Must be reasonable date
            if dt.year < 2020 or dt.year > 2030:
                errors.append(f"Year {dt.year} outside reasonable range (2020-2030)")
            
            # Can't be future date
            if dt > datetime.now():
                errors.append("Date is in the future")
                
        except ValueError:
            errors.append("Invalid date format")
            return False, errors
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_supplier(value: str) -> Tuple[bool, List[str]]:
        """Validate supplier name"""
        errors = []
        
        if not value:
            return False, ["Empty value"]
        
        value = value.strip()
        
        # Length check
        if len(value) < 2:
            errors.append("Too short (minimum 2 characters)")
        if len(value) > 50:
            errors.append("Too long (maximum 50 characters)")
        
        # Can't be purely numeric
        if value.isdigit():
            errors.append("Cannot be purely numeric")
        
        # Can't be a year
        if value.isdigit() and 2020 <= int(value) <= 2030:
            errors.append("Value is a year, not a supplier name")
        
        # Must contain at least one letter
        if not re.search(r'[a-zA-Z]', value):
            errors.append("Must contain at least one letter")
        
        # Check for common non-supplier words
        non_supplier_words = ['total', 'amount', 'date', 'voucher', 'qty', 'price', 'grand']
        if any(word in value.lower() for word in non_supplier_words):
            errors.append("Contains non-supplier keywords")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_amount(value: float, field_name: str = "amount") -> Tuple[bool, List[str]]:
        """Validate monetary amount"""
        errors = []
        
        if value is None:
            return False, ["Empty value"]
        
        # Must be positive
        if value < 0:
            errors.append("Cannot be negative")
        
        # Reasonable range
        if value < 0.01:
            errors.append("Too small (minimum 0.01)")
        if value > 100000:
            errors.append(f"Too large (maximum 100000)")
        
        # Check for suspicious precision (e.g., 2490.00000001)
        decimal_str = str(value)
        if '.' in decimal_str:
            decimals = len(decimal_str.split('.')[1])
            if decimals > 2:
                errors.append(f"Too many decimal places ({decimals})")
        
        return len(errors) == 0, errors


class QualityFocusedExtractor:
    """
    Main extraction engine that prioritizes quality through:
    1. Multiple extraction strategies
    2. Rigorous validation
    3. Confidence scoring
    4. Cross-field validation
    """
    
    def __init__(self, ocr_text: str):
        self.raw_text = ocr_text or ""
        
        # Immediate OCR hallucination fixes globally
        self.raw_text = re.sub(r'(\d{2})7(\d{2})7(20\d{2})', r'\1/\2/\3', self.raw_text)
        self.raw_text = re.sub(r'[6S]rand\s*Total', 'GrandTotal', self.raw_text, flags=re.IGNORECASE)
        self.raw_text = re.sub(r'1ess\s*For\s*Da[mn]', 'LessForDam', self.raw_text, flags=re.IGNORECASE)
        self.raw_text = re.sub(r'Un1oading', 'UnLoading', self.raw_text, flags=re.IGNORECASE)
        self.raw_text = re.sub(r'(?:1YF|1/F).*Cash', 'L/FAndCash', self.raw_text, flags=re.IGNORECASE)
        
        self.lines = [line.strip() for line in self.raw_text.split('\n') if line.strip()]
        self.debug_log = []
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
    
    def _log(self, message: str):
        """Log debug message"""
        self.debug_log.append(message)
        print(f"[QFEE] {message}")
    
    def extract_all(self) -> Dict:
        """
        Extract all fields with quality-focused approach
        Returns comprehensive results with confidence scores
        """
        self._log("=" * 80)
        self._log("STARTING QUALITY-FOCUSED EXTRACTION")
        self._log("=" * 80)
        
        results = {}
        
        # Extract each field with multiple strategies
        results['voucher_number'] = self._extract_with_quality('voucher_number')
        results['voucher_date'] = self._extract_with_quality('voucher_date')
        results['supplier_name'] = self._extract_with_quality('supplier_name')
        results['gross_total'] = self._extract_with_quality('gross_total')
        results['net_total'] = self._extract_with_quality('net_total')
        
        # Update self.data with extracted values for cross-referencing
        self.data['voucher_number'] = results['voucher_number'].value
        self.data['voucher_date'] = results['voucher_date'].value
        self.data['supplier_name'] = results['supplier_name'].value
        self.data['gross_total'] = results['gross_total'].value
        self.data['net_total'] = results['net_total'].value
        
        # Extract line items
        self._log("\nExtracting line items...")
        items = self._extract_items_table()
        if not items:
            items = self._extract_items_relaxed()
        self.data['items'] = items
        self._log(f"  Found {len(items)} line items")
        
        # Extract deductions
        self._log("\nExtracting deductions...")
        deductions = []
        
        # Always calculate Commission @ 4% of gross
        if self.data.get('gross_total'):
            gross = self.data['gross_total']
            commission = gross * 0.04
            deductions.append({
                'deduction_type': 'Commission @4%',
                'amount': round(commission, 2)
            })
            self._log(f"  Commission @4%: {commission:.2f}")
        
        # Always calculate Less for Damages @ 5% of gross  
        if self.data.get('gross_total'):
            gross = self.data['gross_total']
            damage = gross * 0.05
            deductions.append({
                'deduction_type': 'Less for Damages',
                'amount': round(damage, 2)
            })
            self._log(f"  Less for Damages @5%: {damage:.2f}")
        
        # Extract other deductions from OCR (Unloading, L/F Cash, Other)
        other_deductions = self._extract_other_deductions()
        
        # Deduplicate by type - prefer extracted over calculated
        final_deductions = []
        seen_types = set()
        
        # First add extracted deductions (higher priority)
        for ded in other_deductions:
            ded_type_normalized = ded['deduction_type'].lower().replace(' ', '')
            if 'commission' in ded_type_normalized:
                ded_type_normalized = 'commission'
            elif 'damage' in ded_type_normalized:
                ded_type_normalized = 'damage'
            
            if ded_type_normalized not in seen_types:
                final_deductions.append(ded)
                seen_types.add(ded_type_normalized)
        
        # Then add calculated deductions only if type not already present
        for ded in deductions:
            ded_type_normalized = ded['deduction_type'].lower().replace(' ', '')
            if 'commission' in ded_type_normalized:
                ded_type_normalized = 'commission'
            elif 'damage' in ded_type_normalized:
                ded_type_normalized = 'damage'
            
            if ded_type_normalized not in seen_types:
                final_deductions.append(ded)
                seen_types.add(ded_type_normalized)
        
        deductions = final_deductions
        
        self.data['deductions'] = deductions
        self._log(f"  Total deductions: {len(deductions)}")
        
        # Cross-validate fields
        self._cross_validate(results)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(results)
        
        return {
            'fields': results,
            'items': self.data.get('items', []),
            'deductions': self.data.get('deductions', []),
            'recommendations': recommendations,
            'overall_confidence': self._calculate_overall_confidence(results),
            'requires_review': any(
                r.status in [ExtractionStatus.MEDIUM_CONFIDENCE, ExtractionStatus.LOW_CONFIDENCE, ExtractionStatus.VALIDATION_FAILED]
                for r in results.values()
            ),
            'debug_log': self.debug_log
        }
    
    def _extract_with_quality(self, field_name: str) -> FieldResult:
        """
        Extract a single field using multiple strategies
        Returns best valid result with confidence scoring
        """
        self._log(f"\nExtracting {field_name}...")
        self._log("-" * 60)
        
        # Get extraction strategies for this field
        strategies = self._get_strategies(field_name)
        
        attempts = []
        
        # Try each strategy
        for i, (strategy_name, extractor_func) in enumerate(strategies, 1):
            self._log(f"  Strategy {i}/{len(strategies)}: {strategy_name}")
            
            try:
                result = extractor_func()
                
                if result is None:
                    self._log(f"    -> No result")
                    continue
                
                # Validate the result
                is_valid, validation_errors = self._validate_field(field_name, result)
                
                # Calculate confidence
                confidence = self._calculate_confidence(field_name, strategy_name, result, is_valid)
                
                # Create attempt record
                attempt = ExtractionAttempt(
                    strategy=strategy_name,
                    value=result,
                    confidence=confidence,
                    context="",  # Would capture actual context
                    validation_passed=is_valid,
                    validation_errors=validation_errors
                )
                
                attempts.append(attempt)
                
                status = "PASS" if is_valid else "FAIL"
                error_str = f" (Errors: {', '.join(validation_errors)})" if validation_errors else ""
                self._log(f"    -> {status}: {result} [Confidence: {confidence}%]{error_str}")
                
            except Exception as e:
                self._log(f"    -> ERROR: {e}")
                continue
        
        # Select best attempt
        if not attempts:
            return FieldResult(
                value=None,
                confidence=0,
                status=ExtractionStatus.NOT_FOUND,
                attempts=[],
                best_attempt=None,
                recommendation="No extraction possible - manual entry required"
            )
        
        # Filter to only valid attempts
        valid_attempts = [a for a in attempts if a.validation_passed]
        
        if not valid_attempts:
            # No valid attempts - pick highest confidence invalid one and flag
            best_attempt = max(attempts, key=lambda x: x.confidence)
            return FieldResult(
                value=best_attempt.value,
                confidence=best_attempt.confidence,
                status=ExtractionStatus.VALIDATION_FAILED,
                attempts=attempts,
                best_attempt=best_attempt,
                recommendation=f"Validation failed: {', '.join(best_attempt.validation_errors)}. Manual review required."
            )
        
        # Pick best valid attempt
        best_attempt = max(valid_attempts, key=lambda x: x.confidence)
        
        # Determine status based on confidence
        if best_attempt.confidence >= 85:
            status = ExtractionStatus.HIGH_CONFIDENCE
            recommendation = "High confidence extraction - auto-accept"
        elif best_attempt.confidence >= 60:
            status = ExtractionStatus.MEDIUM_CONFIDENCE
            recommendation = "Medium confidence - verify this field"
        else:
            status = ExtractionStatus.LOW_CONFIDENCE
            recommendation = "Low confidence - manual review recommended"
        
        self._log(f"  [OK] Best result: {best_attempt.value} [Confidence: {best_attempt.confidence}%]")
        
        return FieldResult(
            value=best_attempt.value,
            confidence=best_attempt.confidence,
            status=status,
            attempts=attempts,
            best_attempt=best_attempt,
            recommendation=recommendation
        )
    
    def _get_strategies(self, field_name: str) -> List[Tuple[str, Callable]]:
        """Get extraction strategies for a field"""
        
        strategies = {
            'voucher_number': [
                ("VoucherNumber label", self._extract_vn_label),
                ("Nuaber/Nunber variants", self._extract_vn_ocr_variants),
                ("Standalone number early", self._extract_vn_standalone),
                ("Number after voucher", self._extract_vn_after_voucher),
            ],
            'voucher_date': [
                ("VoucherDate label", self._extract_date_label),
                ("Date pattern general", self._extract_date_general),
                ("DD/MM/YYYY pattern", self._extract_date_ddmmyyyy),
            ],
            'supplier_name': [
                ("Supp Name label", self._extract_supp_label),
                ("Name line after label", self._extract_supp_after_label),
                ("Line after Supp", self._extract_supp_next_line),
                ("Capitalized text", self._extract_supp_capitalized),
            ],
            'gross_total': [
                ("Total line pattern", self._extract_total_line),
                ("Largest amount", self._extract_largest_amount),
                ("Sum of items", self._extract_sum_of_items),
            ],
            'net_total': [
                ("Calculated from gross", self._extract_net_calculated),
            ]
        }
        
        return strategies.get(field_name, [])
    
    # ==================== VOUCHER NUMBER STRATEGIES ====================
    
    def _extract_vn_label(self) -> Optional[str]:
        """Strategy 1: Look for VoucherNumber label"""
        pattern = r'(?:voucher\s*number|vouchernumber)[:\s]*(\d{2,4})\b'
        match = re.search(pattern, self.raw_text, re.IGNORECASE)
        return match.group(1) if match else None
    
    def _extract_vn_ocr_variants(self) -> Optional[str]:
        """Strategy 2: Look for OCR error variants"""
        pattern = r'(?:nu[a-z]*ber|no|number|num|#)[:\s]*(\d{2,4})\b'
        match = re.search(pattern, self.raw_text, re.IGNORECASE)
        return match.group(1) if match else None
    
    def _extract_vn_standalone(self) -> Optional[str]:
        """Strategy 3: Standalone 2-4 digit number early in doc"""
        for line in self.lines[:5]:
            match = re.search(r'^\s*(\d{2,4})\s*$', line)
            if match:
                return match.group(1)
        return None
    
    def _extract_vn_after_voucher(self) -> Optional[str]:
        """Strategy 4: Number after 'Voucher' keyword"""
        pattern = r'voucher[:\s#]*(\d{2,4})\b'
        match = re.search(pattern, self.raw_text, re.IGNORECASE)
        return match.group(1) if match else None
    
    # ==================== DATE STRATEGIES ====================
    
    def _extract_date_label(self) -> Optional[str]:
        """Strategy 1: VoucherDate label"""
        pattern = r'(?:voucherdate|voucher\s*date)[:\s]*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})'
        match = re.search(pattern, self.raw_text, re.IGNORECASE)
        if match:
            return self._parse_date(match.group(1))
        return None
    
    def _extract_date_general(self) -> Optional[str]:
        """Strategy 2: Generic date pattern"""
        for line in self.lines[:10]:
            match = re.search(r'(\d{1,2})[\/\-](\d{1,2})[\/\-](20\d{2})', line)
            if match:
                try:
                    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    dt = datetime(year, month, day)
                    return dt.strftime('%Y-%m-%d')
                except:
                    continue
        return None
    
    def _extract_date_ddmmyyyy(self) -> Optional[str]:
        """Strategy 3: DDMMYYYY without separators"""
        pattern = r'\b(\d{2})(\d{2})(20\d{2})\b'
        match = re.search(pattern, self.raw_text)
        if match:
            try:
                day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if 1 <= day <= 31 and 1 <= month <= 12:
                    dt = datetime(year, month, day)
                    return dt.strftime('%Y-%m-%d')
            except:
                pass
        return None
    
    # ==================== SUPPLIER STRATEGIES ====================
    
    def _extract_supp_label(self) -> Optional[str]:
        """Strategy 1: Supp Name label"""
        pattern = r'(?:supp\s*name|suppname|suppnane|nane|nare|ne)[:\s]*([A-Z]{2,30}(?:/[A-Z])?|.{2,30}?)(?=\n|$|qty|total|price)'
        match = re.search(pattern, self.raw_text, re.IGNORECASE)
        if match:
            return self._clean_supplier(match.group(1))
        return None
    
    def _extract_supp_after_label(self) -> Optional[str]:
        """Strategy 2: Text after Name/Nane label on same line"""
        for line in self.lines:
            match = re.search(r'(?:name|nane|nme)[:\s]*(.{2,30}?)(?=\n|$|qty|total)', line, re.IGNORECASE)
            if match:
                return self._clean_supplier(match.group(1))
        return None
    
    def _extract_supp_next_line(self) -> Optional[str]:
        """Strategy 3: Line after Supp/Name indicator"""
        for i, line in enumerate(self.lines):
            if re.search(r'\b(supp|name|nane)\b', line, re.IGNORECASE):
                if i < len(self.lines) - 1:
                    next_line = self.lines[i + 1]
                    if not re.search(r'\b(qty|price|amount|total)\b', next_line, re.IGNORECASE):
                        return self._clean_supplier(next_line)
        return None
    
    def _extract_supp_capitalized(self) -> Optional[str]:
        """Strategy 4: Capitalized text in first few lines"""
        for line in self.lines[:5]:
            # Look for text that's mostly uppercase (company names often are)
            if line.isupper() and 3 <= len(line) <= 30:
                if not any(word in line.lower() for word in ['date', 'voucher', 'total', 'qty']):
                    return self._clean_supplier(line)
        return None

    def _extract_supp_positional(self) -> Optional[str]:
        """Strategy 5: Next line after date"""
        date_line_idx = -1
        for i, line in enumerate(self.lines):
            if re.search(r'\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}', line):
                date_line_idx = i
                break
        
        if date_line_idx != -1 and date_line_idx + 1 < len(self.lines):
            for next_idx in range(date_line_idx + 1, min(date_line_idx + 3, len(self.lines))):
                pot_supp = self.lines[next_idx].strip()
                pot_supp = re.sub(r'^[a-z]{1,2}\s+', '', pot_supp)
                if not re.search(r'\b(qty|price|amount|total|comm)\b', pot_supp, re.IGNORECASE) and 2 <= len(pot_supp) <= 30:
                    if pot_supp.isupper() or '/' in pot_supp:
                        return self._clean_supplier(pot_supp)
        return None
    
    def _clean_supplier(self, text: str) -> str:
        """Clean supplier name"""
        text = text.strip()
        # Remove trailing non-word characters
        text = re.sub(r'[\d\W]+$', '', text)
        # Remove common artifacts
        text = re.sub(r'\s*(?:qty|price|amount|total).*$', '', text, flags=re.IGNORECASE)
        return text.strip()
    
    # ==================== TOTAL STRATEGIES ====================
    
    def _extract_total_line(self) -> Optional[float]:
        """Strategy 1: Total line pattern"""
        pattern = r'(?:^|\s|t)(?:otal|tal)[\s]*(\d+)[\s]*(\d{1,5}\.\d{2})'
        match = re.search(pattern, self.raw_text, re.IGNORECASE | re.MULTILINE)
        if match:
            try:
                amount = float(match.group(2))
                if 10 <= amount <= 100000:
                    return amount
            except:
                pass
        return None
    
    def _extract_largest_amount(self) -> Optional[float]:
        """Strategy 2: Largest reasonable amount"""
        amounts = []
        for match in re.finditer(r'\b(\d{3,5}\.\d{2})\b', self.raw_text):
            try:
                amount = float(match.group(1))
                if 50 <= amount <= 100000:
                    amounts.append(amount)
            except:
                continue
        
        if amounts:
            return max(amounts)
        return None
    
    def _extract_sum_of_items(self) -> Optional[float]:
        """Strategy 3: Sum of line items"""
        # Would extract and sum items - simplified for now
        return None
    
    def _extract_net_explicit(self) -> Optional[float]:
        """Extract explicit net total string match"""
        pattern = r'(?:grand|net)[\s\w]*total[\s:]*(-?\d{1,7}(?:\.\d{2})?)'
        match = re.search(pattern, self.raw_text, re.IGNORECASE)
        if match:
             try:
                 net = float(match.group(1))
                 return net
             except:
                 pass
        return None

    def _extract_net_calculated(self) -> Optional[float]:
        """Calculate net from gross - deductions"""
        # This is calculated after gross is known
        return None
    
    # ==================== LINE ITEMS STRATEGIES ====================

    def _extract_items_table(self) -> List[Dict]:
        """Extract line items from Qty/Price/Amount table with enhanced detection"""
        items = []

        # Find table boundaries more intelligently
        table_start_idx = None
        table_end_idx = None

        # Look for table header
        for i, line in enumerate(self.lines):
            # Detect table header - various OCR variations
            if re.search(r'(?:qty|quantity|qty|q)[\s\-._]*(?:price|pr|p)[\s\-._]*(?:amount|amt|amnt)', line, re.IGNORECASE):
                table_start_idx = i + 1
                self._log(f"  Table header found at line {i}: {line}")
                continue

            # Detect table end markers (but allow "Total X XXX.XX" format which contains item data)
            if table_start_idx:
                # Check if line looks like a deduction or summary (not item data)
                # Deductions usually start with (-), Comm, Damage, etc.
                # But "Total 8 2490.00" is actually item summary data
                is_deduction = re.search(r'^(?:\(\s*-\s*\)|comm|damage|less|unloading|lf|grand\s*total|deduction)', line, re.IGNORECASE)
                is_summary_without_data = re.search(r'^(?:total|subtotal)\s*$', line, re.IGNORECASE)  # Just "Total" with no numbers
                
                if is_deduction or is_summary_without_data:
                    table_end_idx = i
                    self._log(f"  Table end at line {i}: {line}")
                    break

        # If we didn't find explicit end, try to detect by content change
        if table_start_idx and not table_end_idx:
            for i in range(table_start_idx, len(self.lines)):
                line = self.lines[i]
                # If line doesn't have 2-3 numbers, it's probably not an item line
                numbers = re.findall(r'\d+(?:\.\d{2})?', line)
                if len(numbers) < 2 and not re.search(r'(?:item|product|name)', line, re.IGNORECASE):
                    table_end_idx = i
                    break
            if not table_end_idx:
                table_end_idx = len(self.lines)

        # Extract items from table section
        if table_start_idx:
            self._log(f"  Processing table lines {table_start_idx} to {table_end_idx or len(self.lines)}")

            for i in range(table_start_idx, table_end_idx or len(self.lines)):
                line = self.lines[i]

                # Skip empty lines
                if not line.strip():
                    continue

                # Skip total/summary lines
                if re.search(r'^(?:total|subtotal|grand|sum)', line, re.IGNORECASE):
                    continue

                # Try to extract item with enhanced patterns
                item = self._extract_single_item(line, i, items)
                if item:
                    items.append(item)
                    self._log(f"    Found item: {item['item_name'][:30]}... Qty:{item['quantity']} Price:{item['unit_price']} Amount:{item['line_amount']}")

        return items

    def _extract_single_item(self, line: str, line_idx: int, existing_items: List[Dict]) -> Optional[Dict]:
        """Extract a single item from a line with comprehensive pattern matching"""

        # Pattern 1: Standard Qty Price Amount (3 numbers)
        # Examples: "Apple 2 50.00 100.00", "2 50.00 100.00", "Apple 2 50 100"
        pattern1 = r'^(.*?)\s+(\d{1,4})\s+(\d{1,6}(?:\.\d{1,2})?)\s+(\d{1,7}(?:\.\d{1,2})?)$'
        match = re.match(pattern1, line)

        if match:
            try:
                item_name = match.group(1).strip()
                qty = int(match.group(2))
                price = float(match.group(3))
                amount = float(match.group(4))

                # Smart decimal correction
                price, amount = self._fix_item_amounts(qty, price, amount)

                # Validation
                if self._validate_item(qty, price, amount):
                    # Clean item name
                    item_name = self._clean_item_name(item_name, line_idx)

                    return {
                        'item_name': item_name if item_name else f'Item {len(existing_items) + 1}',
                        'quantity': qty,
                        'unit_price': round(price, 2),
                        'line_amount': round(amount, 2)
                    }
            except:
                pass

        # Pattern 2: Amount Price Qty (reversed order) - sometimes OCR mixes them up
        pattern2 = r'^(.*?)\s+(\d{1,7}(?:\.\d{1,2})?)\s+(\d{1,6}(?:\.\d{1,2})?)\s+(\d{1,4})$'
        match = re.match(pattern2, line)

        if match:
            try:
                item_name = match.group(1).strip()
                amount = float(match.group(2))
                price = float(match.group(3))
                qty = int(match.group(4))

                # Check if qty * price ≈ amount (reversed order check)
                expected = qty * price
                if abs(amount - expected) <= max(expected * 0.3, 10):
                    price, amount = self._fix_item_amounts(qty, price, amount)

                    if self._validate_item(qty, price, amount):
                        item_name = self._clean_item_name(item_name, line_idx)

                        return {
                            'item_name': item_name if item_name else f'Item {len(existing_items) + 1}',
                            'quantity': qty,
                            'unit_price': round(price, 2),
                            'line_amount': round(amount, 2)
                        }
            except:
                pass

        # Pattern 3: Just numbers (no name, common in poor OCR)
        pattern3 = r'^(\d{1,4})\s+(\d{1,6}(?:\.\d{1,2})?)\s+(\d{1,7}(?:\.\d{1,2})?)$'
        match = re.match(pattern3, line.strip())

        if match and not re.search(r'[a-zA-Z]', line):
            try:
                qty = int(match.group(1))
                price = float(match.group(2))
                amount = float(match.group(3))

                price, amount = self._fix_item_amounts(qty, price, amount)

                if self._validate_item(qty, price, amount):
                    return {
                        'item_name': f'Item {len(existing_items) + 1}',
                        'quantity': qty,
                        'unit_price': round(price, 2),
                        'line_amount': round(amount, 2)
                    }
            except:
                pass

        return None

    def _fix_item_amounts(self, qty: int, price: float, amount: float) -> tuple:
        """Fix common OCR decimal errors in item amounts"""
        expected = qty * price

        # If price seems way off (e.g., 4000 instead of 40.00)
        if price > 1000 and amount < price * 0.1:
            price = price / 100
            expected = qty * price

        # If amount seems way off
        if amount > 10000 and amount > expected * 10:
            amount = amount / 100

        # If still not matching, try alternative interpretations
        tolerance = max(expected * 0.25, 5)

        if abs(amount - expected) > tolerance:
            # Maybe price and amount are swapped?
            if abs(price - expected) <= tolerance:
                price, amount = amount, price

        return price, amount

    def _validate_item(self, qty: int, price: float, amount: float) -> bool:
        """Validate extracted item data"""
        # Basic sanity checks
        if qty <= 0 or qty > 10000:
            return False

        if price <= 0 or price > 100000:
            return False

        if amount <= 0 or amount > 1000000:
            return False

        # Check mathematical relationship
        expected = qty * price
        tolerance = max(expected * 0.3, 1)  # 30% tolerance or at least 1

        if abs(amount - expected) > tolerance:
            # Allow some slack for OCR errors
            if abs(amount - expected) > expected * 0.5:
                return False

        return True

    def _clean_item_name(self, name: str, line_idx: int) -> str:
        """Clean and enhance item name extraction"""
        # Remove leading non-word characters
        name = re.sub(r'^[^\w]*', '', name)

        # Remove common artifacts
        name = re.sub(r'\s*(?:qty|price|amount|total|\d+\.\d{2}).*$', '', name, flags=re.IGNORECASE)

        # If name is empty, try to get it from previous line
        if not name and line_idx > 0:
            prev_line = self.lines[line_idx - 1]
            # Check if previous line looks like a name (no numbers or just a name)
            if not re.search(r'\d{2,}', prev_line) or re.match(r'^[A-Za-z\s]+$', prev_line.strip()):
                name = prev_line.strip()
                name = re.sub(r'^[^\w]*', '', name)

        # Clean up
        name = name.strip()
        name = re.sub(r'\s+', ' ', name)  # Normalize spaces

        return name[:100]  # Limit length

    def _extract_items_relaxed(self) -> List[Dict]:
        """Extract items with relaxed validation (fallback for poor OCR)"""
        items = []

        for line in self.lines:
            # Skip lines that are clearly not items
            if re.search(r'^(?:total|date|voucher|supplier|qty|price|amount)', line, re.IGNORECASE):
                continue

            # Look for any 3 numbers that could be qty, price, amount
            numbers = re.findall(r'\b(\d{1,4})\s+(\d{1,6}(?:\.\d{1,2})?)\s+(\d{1,7}(?:\.\d{1,2})?)\b', line)

            for match in numbers:
                try:
                    qty = int(match[0])
                    price = float(match[1])
                    amount = float(match[2])

                    # Very relaxed validation
                    if qty > 0 and price > 0 and amount > 0:
                        expected = qty * price

                        # Allow 40% tolerance for poor OCR
                        if qty * price * 0.6 <= amount <= qty * price * 1.4:
                            # Try to extract name
                            item_name = ''
                            num_match = re.search(r'\b' + re.escape(match[0]) + r'\s+' + re.escape(match[1]), line)
                            if num_match:
                                item_name = line[:num_match.start()].strip()
                                item_name = re.sub(r'^[^\w]*', '', item_name)

                            items.append({
                                'item_name': item_name if item_name else f'Item {len(items) + 1}',
                                'quantity': qty,
                                'unit_price': round(price, 2),
                                'line_amount': round(amount, 2)
                            })
                            break  # Only take first match per line
                except:
                    continue

        return items
    
    # ==================== DEDUCTIONS STRATEGIES ====================
    
    def _extract_other_deductions(self) -> List[Dict]:
        """Extract Unloading, L/F Cash, and Other (unnamed) deductions from OCR with comprehensive patterns"""
        deductions = []
        found_amounts = set()  # Track amounts to prevent duplicates
        
        # Enhanced patterns with OCR error variations
        deduction_patterns = {
            'Unloading': {
                'patterns': [
                    r'(?:unloading|unload|unld|unlod|unlodin)[^\d\n]*(-?\s*[\d,]+\.?\d{0,2})',
                    r'(?:unloading|unload)[^\d\n]*\(?\s*-\s*\)?[^\d\n]*([\d,]+\.?\d{0,2})',
                ],
                'max_amount': 200,
                'typical_range': (10, 150)
            },
            'L/F Cash': {
                'patterns': [
                    r'(?:l[/\s]*f|lf|l\s*f|lfand|l\.f)[^\d\n]*(?:and)?[^\d\n]*(?:cash)?[^\d\n]*(-?\s*[\d,]+\.?\d{0,2})',
                    r'(?:lfandcash|lfcash|lf\s+cash)[^\d\n]*(-?\s*[\d,]+\.?\d{0,2})',
                    r'(?:cash)[^\d\n]*(?:lf)?[^\d\n]*(-?\s*[\d,]+\.?\d{0,2})',
                    r'\(\s*-\s*\)[^\d\n]*(?:l[/\s]*f|lf)[^\d\n]*(-?\s*[\d,]+\.?\d{0,2})',
                ],
                'max_amount': 500,
                'typical_range': (20, 400)
            },
            'Commission': {
                'patterns': [
                    r'(?:comm|comission|commision|com)[^\d\n]*(?:@)?[^\d\n]*(-?\s*[\d,]+\.?\d{0,2})\s*(?:%)?',
                    r'(?:comm|comission)[^\d\n]*(?:@)?[^\d\n]*(?:4\.?\d*)?\s*(?:%)?[^\d\n]*(-?\s*[\d,]+\.?\d{0,2})',
                    r'\(\s*-\s*\)[^\d\n]*(?:comm|com)[^\d\n]*(-?\s*[\d,]+\.?\d{0,2})',
                ],
                'max_amount': 5000,
                'typical_range': (10, 1000),
                'is_percentage': True
            },
            'Less for Damages': {
                'patterns': [
                    r'(?:less\s*for\s*damages|lessfordamages|damages|damage)[^\d\n]*(-?\s*[\d,]+\.?\d{0,2})',
                    r'(?:less\s*for)[^\d\n]*(?:damages)?[^\d\n]*(-?\s*[\d,]+\.?\d{0,2})',
                    r'\(\s*-\s*\)[^\d\n]*(?:damage|less)[^\d\n]*(-?\s*[\d,]+\.?\d{0,2})',
                ],
                'max_amount': 1000,
                'typical_range': (20, 500),
                'is_percentage': True
            },
        }
        
        found_types = set()
        
        # Process each deduction type
        for ded_type, config in deduction_patterns.items():
            if ded_type in found_types:
                continue
            
            patterns = config['patterns']
            max_amount = config.get('max_amount', 1000)
            typical_range = config.get('typical_range', (0.1, 1000))
            is_percentage = config.get('is_percentage', False)
                
            for pattern in patterns:
                matches = list(re.finditer(pattern, self.raw_text, re.IGNORECASE))
                
                for match in matches:
                    try:
                        amount_str = match.group(1).replace(',', '').replace('-', '').strip()
                        if not amount_str:
                            continue
                            
                        amount = float(amount_str)
                        
                        # Enhanced decimal error correction
                        # Check if amount seems wrong based on context
                        amount = self._smart_decimal_fix(amount, ded_type, match.group(0))
                        
                        rounded_amount = round(amount, 2)
                        
                        # Skip if we already have this amount (prevents duplicates)
                        if rounded_amount in found_amounts:
                            continue
                        
                        # Skip if amount is unreasonably small
                        if amount < 0.01:
                            continue
                        
                        # For percentage-based deductions, calculate from gross
                        if is_percentage and self.data.get('gross_total'):
                            # Check if amount is actually a percentage (usually < 100)
                            if amount < 100 and '%' in match.group(0):
                                if ded_type == 'Commission':
                                    amount = self.data['gross_total'] * (amount / 100)
                                    ded_type = f'Commission @{int(amount)}%'
                                elif ded_type == 'Less for Damages':
                                    # Usually 5% for damages
                                    amount = self.data['gross_total'] * 0.05
                                    ded_type = 'Less for Damages'
                        
                        # Final validation
                        if amount <= max_amount and typical_range[0] <= amount <= typical_range[1] * 2:
                            deductions.append({
                                'deduction_type': ded_type,
                                'amount': rounded_amount
                            })
                            found_types.add(ded_type)
                            found_amounts.add(rounded_amount)
                            self._log(f"  {ded_type}: {rounded_amount:.2f}")
                            break
                    except Exception as e:
                        continue
        
        return deductions
    
    def _fix_decimal_error(self, amount: float, context: str) -> float:
        """Fix common OCR decimal point errors"""
        # Common error: 75.00 becomes 7500, 480.00 becomes 48000
        # If amount is suspiciously large for the context
        
        # Commission should be small (usually 4% of gross)
        if 'comm' in context.lower():
            if amount > 1000:
                return amount / 100
            return amount
        
        # Damage should be reasonable (usually < 200)
        if 'damage' in context.lower():
            if amount > 1000:
                return amount / 100
            return amount
        
        # Unloading should be reasonable (usually < 100)
        if 'unload' in context.lower():
            if amount > 1000:
                return amount / 100
            return amount
        
        # L/F Cash should be reasonable (usually < 500)
        if 'cash' in context.lower() or 'lf' in context.lower():
            if amount > 5000:
                return amount / 100
            return amount
        
        return amount
    
    def _smart_decimal_fix(self, amount: float, ded_type: str, context: str = "") -> float:
        """Intelligently fix decimal errors based on deduction type and amount magnitude"""
        if amount < 100:
            return amount
        
        # Define typical maximums for each deduction type
        typical_max = {
            'Unloading': 150,
            'L/F Cash': 400,
            'Commission': 1000,
            'Less for Damages': 500,
            'Other': 500,
        }
        
        max_expected = typical_max.get(ded_type, 1000)
        
        # If amount is way too high, try dividing by 100
        if amount > max_expected * 10:
            return amount / 100
        
        # If amount is still too high but closer, try dividing by 10
        if amount > max_expected * 5:
            return amount / 10
        
        return amount
    
    # ==================== VALIDATION & CONFIDENCE ====================
    
    def _validate_field(self, field_name: str, value: Any) -> Tuple[bool, List[str]]:
        """Validate extracted value"""
        if field_name == 'voucher_number':
            return ValidationRules.validate_voucher_number(str(value))
        elif field_name == 'voucher_date':
            return ValidationRules.validate_date(str(value))
        elif field_name == 'supplier_name':
            return ValidationRules.validate_supplier(str(value))
        elif field_name in ['gross_total', 'net_total']:
            return ValidationRules.validate_amount(float(value) if value else 0, field_name)
        return True, []
    
    def _calculate_confidence(self, field_name: str, strategy: str, value: Any, is_valid: bool) -> int:
        """Calculate confidence score for extraction"""
        base_confidence = 50
        
        # Strategy-based confidence
        strategy_confidence = {
            'VoucherNumber label': 90,
            'Nuaber/Nunber variants': 75,
            'Standalone number early': 60,
            'Number after voucher': 70,
            'VoucherDate label': 90,
            'Date pattern general': 70,
            'DD/MM/YYYY pattern': 65,
            'Supp Name label': 85,
            'Name line after label': 75,
            'Line after Supp': 65,
            'Capitalized text': 50,
            'Total line pattern': 90,
            'Largest amount': 60,
            'Sum of items': 80,
        }
        
        confidence = strategy_confidence.get(strategy, 50)
        
        # Validation bonus/penalty
        if is_valid:
            confidence += 10
        else:
            confidence -= 30
        
        # Context-based adjustments
        if field_name == 'voucher_number':
            # Higher confidence for shorter numbers (less chance of being date)
            if isinstance(value, str) and len(value) <= 3:
                confidence += 5
        
        return max(0, min(100, confidence))
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string to standard format"""
        for sep in ['/', '-', '.']:
            if sep in date_str:
                parts = date_str.split(sep)
                if len(parts) == 3:
                    try:
                        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                        if len(str(year)) == 2:
                            year = 2000 + year
                        if 2020 <= year <= 2030:
                            dt = datetime(year, month, day)
                            return dt.strftime('%Y-%m-%d')
                    except:
                        continue
        return None
    
    def _cross_validate(self, results: Dict[str, FieldResult]):
        """Cross-validate field relationships"""
        self._log("\n" + "=" * 60)
        self._log("CROSS-FIELD VALIDATION")
        self._log("=" * 60)
        
        gross = results.get('gross_total')
        net = results.get('net_total')
        
        if gross and gross.value and net and net.value:
            # Check if net makes sense relative to gross
            if net.value > gross.value:
                self._log("  [WARN]  Net total > Gross total - check deductions")
                net.status = ExtractionStatus.VALIDATION_FAILED
                net.recommendation = "Net > Gross - verify deductions"
    
    def _generate_recommendations(self, results: Dict[str, FieldResult]) -> Dict:
        """Generate field-level recommendations"""
        recommendations = {}
        
        for field_name, result in results.items():
            if result.status == ExtractionStatus.HIGH_CONFIDENCE:
                recommendations[field_name] = "[OK] Auto-accept"
            elif result.status == ExtractionStatus.MEDIUM_CONFIDENCE:
                recommendations[field_name] = "[WARN] Verify this field"
            elif result.status == ExtractionStatus.VALIDATION_FAILED:
                recommendations[field_name] = f"[X] Validation failed: {result.recommendation}"
            elif result.status == ExtractionStatus.LOW_CONFIDENCE:
                recommendations[field_name] = "[X] Low confidence - manual entry"
            else:
                recommendations[field_name] = "[X] Not found - manual entry required"
        
        return recommendations
    
    def _calculate_overall_confidence(self, results: Dict[str, FieldResult]) -> int:
        """Calculate overall extraction confidence"""
        confidences = [r.confidence for r in results.values() if r.confidence > 0]
        if not confidences:
            return 0
        return int(sum(confidences) / len(confidences))


def extract_with_quality(ocr_text: str) -> Dict:
    """Main entry point for quality-focused extraction"""
    extractor = QualityFocusedExtractor(ocr_text)
    return extractor.extract_all()


# Convenience function for API compatibility
def parse_receipt_text(ocr_text: str) -> Dict:
    """API-compatible wrapper"""
    result = extract_with_quality(ocr_text)
    
    # Convert to expected format
    return {
        'master': {
            'voucher_number': result['fields']['voucher_number'].value,
            'voucher_date': result['fields']['voucher_date'].value,
            'supplier_name': result['fields']['supplier_name'].value,
            'gross_total': result['fields']['gross_total'].value,
            'net_total': result['fields']['net_total'].value,
        },
        'quality_report': result,
        'requires_review': result['requires_review'],
        'confidence': result['overall_confidence']
    }


if __name__ == "__main__":
    # Test with problematic sample
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
    
    print("Testing Quality-Focused Extraction Engine")
    print("=" * 80)
    result = extract_with_quality(test_text)
    
    print("\n[STATS] EXTRACTION RESULTS:")
    print("=" * 80)
    
    for field_name, field_result in result['fields'].items():
        print(f"\n{field_name.upper()}:")
        print(f"  Value: {field_result.value}")
        print(f"  Confidence: {field_result.confidence}%")
        print(f"  Status: {field_result.status.value}")
        print(f"  Recommendation: {field_result.recommendation}")
        
        if field_result.attempts:
            print(f"  Attempts ({len(field_result.attempts)}):")
            for i, attempt in enumerate(field_result.attempts[:3], 1):
                valid = "[OK]" if attempt.validation_passed else "[X]"
                print(f"    {i}. {valid} {attempt.strategy}: {attempt.value} [{attempt.confidence}%]")
    
    print(f"\n" + "=" * 80)
    print(f"OVERALL CONFIDENCE: {result['overall_confidence']}%")
    print(f"REQUIRES REVIEW: {result['requires_review']}")
    print(f"\nRECOMMENDATIONS:")
    for field, rec in result['recommendations'].items():
        print(f"  {field}: {rec}")
