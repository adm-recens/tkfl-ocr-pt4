"""
Dynamic Character Whitelists for Tesseract OCR
Context-aware character filtering to improve accuracy
"""
from typing import Dict, List


class DynamicWhitelist:
    """Manages dynamic character whitelists for different content types"""
    
    # Base character sets
    DIGITS = "0123456789"
    UPPERCASE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    LOWERCASE = "abcdefghijklmnopqrstuvwxyz"
    PUNCTUATION = ".,;:!?-/"
    COMMON_SYMBOLS = "()&"
    CURRENCY = "₹$€£¥"
    SPACE = " "
    
    @classmethod
    def get_numbers_only(cls) -> str:
        """
        Whitelist for numeric fields (amounts, dates, voucher numbers)
        Includes: digits, decimal point, comma, dash, slash
        Excludes: letters that are commonly confused with digits
        """
        return cls.DIGITS + ".,/-" + cls.SPACE
    
    @classmethod
    def get_text_only(cls) -> str:
        """
        Whitelist for text fields (names, addresses)
        Includes: letters, common punctuation, space
        Excludes: digits to avoid confusion in text fields
        """
        return cls.UPPERCASE + cls.LOWERCASE + cls.PUNCTUATION + cls.COMMON_SYMBOLS + cls.SPACE
    
    @classmethod
    def get_alphanumeric(cls) -> str:
        """
        Whitelist for mixed content (general text with numbers)
        Includes: letters, digits, punctuation, common symbols
        Excludes: rarely used characters that cause confusion
        """
        return (cls.UPPERCASE + cls.LOWERCASE + cls.DIGITS + 
                cls.PUNCTUATION + cls.COMMON_SYMBOLS + cls.SPACE)
    
    @classmethod
    def get_currency_amounts(cls) -> str:
        """
        Whitelist for currency amounts
        Includes: digits, decimal, comma, currency symbols
        Excludes: letters commonly confused with digits (O, I, L, S, etc.)
        """
        return cls.DIGITS + ".,/" + cls.CURRENCY + cls.SPACE
    
    @classmethod
    def get_dates(cls) -> str:
        """
        Whitelist for dates
        Includes: digits, dash, slash, space
        """
        return cls.DIGITS + "-/." + cls.SPACE
    
    @classmethod
    def get_receipt_general(cls) -> str:
        """
        Whitelist for general receipt content
        Includes: everything commonly found on receipts
        Excludes: rarely used characters that cause OCR confusion
        """
        # Exclude characters that commonly confuse OCR: ~`|[]{}<>
        excluded = "~`|[]{}<>"
        allowed = (cls.UPPERCASE + cls.LOWERCASE + cls.DIGITS + 
                  cls.PUNCTUATION + cls.COMMON_SYMBOLS + cls.CURRENCY + cls.SPACE)
        
        # Remove excluded characters
        for char in excluded:
            allowed = allowed.replace(char, '')
        
        return allowed
    
    @classmethod
    def get_for_field_type(cls, field_type: str) -> str:
        """
        Get appropriate whitelist for a specific field type
        
        Args:
            field_type: Type of field ('number', 'text', 'amount', 'date', 'general')
            
        Returns:
            Whitelist string
        """
        whitelist_map = {
            'number': cls.get_numbers_only(),
            'text': cls.get_text_only(),
            'amount': cls.get_currency_amounts(),
            'date': cls.get_dates(),
            'alphanumeric': cls.get_alphanumeric(),
            'general': cls.get_receipt_general()
        }
        
        return whitelist_map.get(field_type, cls.get_receipt_general())
    
    @classmethod
    def build_tesseract_config(cls, whitelist_type: str = 'general', 
                               psm: int = 6, oem: int = 1) -> str:
        """
        Build complete Tesseract configuration with whitelist
        
        Args:
            whitelist_type: Type of whitelist to use
            psm: Page segmentation mode (default: 6)
            oem: OCR Engine mode (default: 1 - LSTM)
            
        Returns:
            Tesseract configuration string
        """
        whitelist = cls.get_for_field_type(whitelist_type)
        
        # Build config without quotes (Windows compatibility)
        # Tesseract handles the whitelist string directly
        config = f'--oem {oem} --psm {psm} -c tessedit_char_whitelist={whitelist}'
        
        return config
    
    @classmethod
    def get_blacklist_config(cls, blacklist_chars: str = "|[]{}~`", 
                            psm: int = 6, oem: int = 1) -> str:
        """
        Build Tesseract configuration with character blacklist
        
        Args:
            blacklist_chars: Characters to exclude
            psm: Page segmentation mode
            oem: OCR Engine mode
            
        Returns:
            Tesseract configuration string
        """
        blacklist_escaped = blacklist_chars.replace('\\', '\\\\').replace('"', '\\"')
        
        config = f'--oem {oem} --psm {psm} -c tessedit_char_blacklist="{blacklist_escaped}"'
        
        return config


def get_field_specific_configs() -> Dict[str, str]:
    """
    Get Tesseract configurations optimized for specific field types
    
    Returns:
        Dictionary mapping field types to Tesseract configs
    """
    return {
        'voucher_number': DynamicWhitelist.build_tesseract_config('number', psm=7),  # Single line
        'voucher_date': DynamicWhitelist.build_tesseract_config('date', psm=7),
        'supplier_name': DynamicWhitelist.build_tesseract_config('text', psm=7),
        'amounts': DynamicWhitelist.build_tesseract_config('amount', psm=7),
        'items': DynamicWhitelist.build_tesseract_config('alphanumeric', psm=6),
        'general': DynamicWhitelist.build_tesseract_config('general', psm=6)
    }


def get_optimized_config(content_type: str = 'general') -> str:
    """
    Get optimized Tesseract configuration for content type
    
    Args:
        content_type: Type of content being processed
        
    Returns:
        Optimized Tesseract configuration string
    """
    configs = get_field_specific_configs()
    return configs.get(content_type, configs['general'])