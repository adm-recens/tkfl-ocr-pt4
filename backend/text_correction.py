"""
Enhanced Text Correction for OCR Output
Fixes common OCR errors in receipts including terms, digits, and spacing
"""

import re

class ReceiptTextCorrector:
    """Advanced text correction for receipt OCR output"""
    
    # Common substitutions
    subs = {
        'O': '0', 'D': '0', 'Q': '0',
        'I': '1', 'L': '1', '|': '1', '!': '1',
        'Z': '2',
        'S': '5', '$': '5',
        'B': '8', '&': '8',
        'G': '6'
    }
    
# Receipt-specific term corrections (conservative)
    RECEIPT_TERMS = {
        # Voucher related (critical for voucher extraction)
        'Voucner': 'Voucher', 'Vouchcr': 'Voucher', 'V0ucher': 'Voucher',
        'Vouch3r': 'Voucher', 'Vouch3rNumb3r': 'VoucherNumber',
        
        # Date related
        'VoucberDate': 'Voucher Date', 'VYoucherDate': 'Voucher Date',
        'Date': 'Date', 'Dat3': 'Date',
        
        # Supplier related (critical for supplier extraction)
        'SuppName': 'Supp Name', 'SuppNanm3': 'Supp Name', 'SuppNam3': 'Supp Name', 'SuppNane': 'Supp Name', 'SuppNanme': 'Supp Name',
        
        # Deduction terms
        'Comm': 'Comm', 'CommW': 'Comm', 'Commision': 'Commission',
        'LessForDamnages': 'Less For Damages', 'LessForDamages': 'Less For Damages',
        'UnLoadin': 'UnLoading', 'Unloading': 'UnLoading',
        'LFAndCash': 'L/F and Cash', 'LFAndCash': 'L/F and Cash',
        
        # Total terms
        'brandTotal': 'Grand Total', 'GrandTotal': 'Grand Total',
        'Tota': 'Total', 'NetTotal': 'Net Total',
        
        # Amount/Price terms
        'Amount': 'Amount', 'Anount': 'Amount', 'Price': 'Price', 'Qty': 'Qty'
    }
    
    @staticmethod
    def clean_whitespace(text: str) -> str:
        """Clean up spacing issues in OCR text"""
        # Fix multiple spaces
        corrected = re.sub(r' +', ' ', text)
        
        # Fix spacing around punctuation
        corrected = re.sub(r'\s*([:,])\s*', r'\1 ', corrected)
        
        # Fix line endings with extra spaces
        corrected = re.sub(r' *\n', '\n', corrected)
        
        return corrected.strip()
    
    @staticmethod
    def correct_digit_substitutions(text: str) -> str:
        """Fix common digit/character substitution errors"""
        corrected = ""
        
        for char in text:
            # Only substitute if it helps form a valid number pattern
            if char in ReceiptTextCorrector.subs:
                # Look ahead to see if we're in a numeric context
                next_chars = text[text.find(char) + 1:text.find(char) + 3]
                prev_chars = text[max(0, text.find(char) - 2):text.find(char)]
                
                # If surrounded by digits or decimal points, make substitution
                numeric_context = (
                    (next_chars and any(c.isdigit() or c == '.' for c in next_chars)) or
                    (prev_chars and any(c.isdigit() or c == '.' for c in prev_chars))
                )
                
                # Additional check: don't substitute within voucher words
                word_context = text[max(0, text.find(char) - 10):text.find(char) + 10].lower()
                in_voucher_word = any(term in word_context for term in ['vouch', 'voucher', 'date', 'supp'])
                
                if numeric_context and not in_voucher_word:
                    corrected += ReceiptTextCorrector.subs[char]
                else:
                    corrected += char
            else:
                corrected += char
        
        return corrected
    
    @staticmethod
    def correct_receipt_terms(text: str) -> str:
        """Fix receipt-specific term OCR errors"""
        corrected = text
        
        # Apply term corrections (conservative)
        for wrong, correct in ReceiptTextCorrector.RECEIPT_TERMS.items():
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(wrong) + r'\b'
            # Only correct if it doesn't break nearby numbers
            corrected_with_sub = re.sub(pattern, correct, corrected, flags=re.IGNORECASE)
            
            # Check if correction broke nearby numbers and revert if so
            if re.search(correct + r'\s*\d{3,}', corrected_with_sub):
                # Correction might have broken number extraction, be more conservative
                continue
            corrected = corrected_with_sub
        
        # Special case: Handle standalone 3-digit numbers that might be voucher numbers
        # This is a more aggressive approach for the specific issue
        lines = corrected.split('\n')
        corrected_lines = []
        for i, line in enumerate(lines):
            # If line contains a 3-digit number and is early in the receipt
            if re.search(r'\b(\d{3,})\b', line) and i < 3:
                # Check if this line is likely a voucher number (not a date)
                if not re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', line):  # Not a date pattern
                    num_match = re.search(r'\b(\d{3,})\b', line)
                    if num_match:
                        line = re.sub(rf'\b{num_match.group(1)}\b', f'VoucherNumber{num_match.group(1)}', line)
            corrected_lines.append(line)
        corrected = '\n'.join(corrected_lines)
        
        # Special voucher corrections without word boundaries
        voucher_corrections = {
            r'Vouch3rNumb3r': 'VoucherNumber',
            r'Vouch3r': 'Voucher',
            r'Youch3r': 'Voucher',
            r'Youch3rDat3': 'VoucherDate'
        }
        
        for wrong, correct in voucher_corrections.items():
            corrected = re.sub(wrong, correct, corrected, flags=re.IGNORECASE)
        
        # Additional voucher number corrections for attached patterns
        # Handle cases like '340' that should be 'VoucherNumber340'
        if re.search(r'Voucher.*?(\d{3,})', corrected):
            # Extract the voucher number from the corrected text
            voucher_match = re.search(r'Voucher.*?(\d{3,})', corrected)
            if voucher_match:
                voucher_num = voucher_match.group(1)
                # Replace the standalone number with proper voucher format
                corrected = re.sub(rf'\b{voucher_num}\b', f'VoucherNumber{voucher_num}', corrected)
        
        # Handle standalone 3-digit numbers that might be voucher numbers
        # Only if they appear near voucher-related text
        lines = corrected.split('\n')
        corrected_lines = []
        for line in lines:
            if re.search(r'Voucher|Vouch|Number', line, re.IGNORECASE):
                # Look for standalone 3-digit numbers in voucher context
                numbers = re.findall(r'\b(\d{3,})\b', line)
                for num in numbers:
                    # Replace with voucher format
                    line = re.sub(rf'\b{num}\b', f'VoucherNumber{num}', line)
            corrected_lines.append(line)
        corrected = '\n'.join(corrected_lines)
        
        return corrected
    
    @staticmethod
    def fix_amount_patterns(text: str) -> str:
        """Fix specific amount extraction patterns"""
        corrected = text
        
        # Fix patterns where decimal points are missed
        # Example: "2200" → "220.00" when in amount context
        amount_context_pattern = r'(Amount|Price|Total|Comm|Damages|Loading|Cash)\s+(\d{3,})(?!\.\d)'
        corrected = re.sub(amount_context_pattern, r'\1 \2.00', corrected, flags=re.IGNORECASE)
        
        # Fix patterns with extra digits
        # Example: "22000" → "220.00" when clearly an amount
        large_amount_pattern = r'\b(\d{5,})(?!\.\d)\b'
        def fix_large_amount(match):
            num = match.group(1)
            # If it's a large number ending in 00, likely missing decimal
            if num.endswith('00') and len(num) >= 5:
                return f"{num[:-2]}.00"
            return num
        
        corrected = re.sub(large_amount_pattern, fix_large_amount, corrected)
        
        return corrected
    
    @classmethod
    def correct_text(cls, text: str) -> str:
        """Apply all text corrections in sequence"""
        if not text:
            return text
        
        # Step 1: Clean whitespace
        corrected = cls.clean_whitespace(text)
        
        # Step 2: Apply receipt term corrections
        corrected = cls.correct_receipt_terms(corrected)
        
        # Step 3: Apply digit substitution corrections
        corrected = cls.correct_digit_substitutions(corrected)
        
        # Step 4: Fix amount patterns
        corrected = cls.fix_amount_patterns(corrected)
        
        # Step 5: Final cleanup
        corrected = cls.clean_whitespace(corrected)
        
        return corrected

def apply_text_corrections(ocr_text: str) -> str:
    """Convenience function to apply text corrections"""
    return ReceiptTextCorrector.correct_text(ocr_text)

if __name__ == "__main__":
    # Test the corrections
    test_text = """
    Tota         1              22e0On
    -:       CommW?4-OO      ory
    -       LessForDamnages     110
    -                                                  UnLoadin q                            Sd
    -                                                                           So
    -.         LFAndCash      FO
    brandTotal         Pano
    """
    
    print("Original:")
    print(test_text)
    print("\nCorrected:")
    corrector = ReceiptTextCorrector()
    print(corrector.correct_text(test_text))