"""
OCR Preprocessing & Enhancement Pipeline
Fixes image quality issues BEFORE parsing
"""

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
from typing import Dict, Tuple
import re

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


class OCRPreprocessor:
    """
    Preprocesses images for better OCR results
    Addresses: blur, skew, low contrast, noise
    """
    
    @staticmethod
    def preprocess_for_tesseract(image_path: str) -> str:
        """
        Full preprocessing pipeline for poor quality voucher images
        Returns path to preprocessed image
        """
        # Load image
        img = cv2.imread(image_path)
        
        if img is None:
            return image_path  # Return original if can't load
        
        # Step 1: Fix orientation/skew
        img = OCRPreprocessor._deskew(img)
        
        # Step 2: Enhance contrast
        img = OCRPreprocessor._enhance_contrast(img)
        
        # Step 3: Denoise
        img = OCRPreprocessor._denoise(img)
        
        # Step 4: Sharpen
        img = OCRPreprocessor._sharpen(img)
        
        # Step 5: Resize for better OCR (Tesseract likes 300 DPI equivalent)
        img = OCRPreprocessor._resize_for_ocr(img)
        
        # Step 6: Apply adaptive thresholding
        img = OCRPreprocessor._adaptive_threshold(img)
        
        # Save preprocessed image
        preprocessed_path = image_path.replace('.jpg', '_preprocessed.jpg').replace('.png', '_preprocessed.png')
        cv2.imwrite(preprocessed_path, img)
        
        return preprocessed_path
    
    @staticmethod
    def _deskew(img: np.ndarray) -> np.ndarray:
        """Correct image skew"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.bitwise_not(gray)
        
        # Find all non-zero points
        coords = np.column_stack(np.where(gray > 0))
        
        if len(coords) == 0:
            return img
        
        # Get angle
        angle = cv2.minAreaRect(coords)[-1]
        
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        # Rotate if significant angle
        if abs(angle) > 0.5:
            (h, w) = img.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(img, M, (w, h),
                                    flags=cv2.INTER_CUBIC,
                                    borderMode=cv2.BORDER_REPLICATE)
            return rotated
        
        return img
    
    @staticmethod
    def _enhance_contrast(img: np.ndarray) -> np.ndarray:
        """Enhance contrast using CLAHE"""
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        
        lab = cv2.merge((l, a, b))
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    
    @staticmethod
    def _denoise(img: np.ndarray) -> np.ndarray:
        """Remove noise while preserving edges"""
        return cv2.bilateralFilter(img, 9, 75, 75)
    
    @staticmethod
    def _sharpen(img: np.ndarray) -> np.ndarray:
        """Sharpen image"""
        kernel = np.array([[-1, -1, -1],
                          [-1, 9, -1],
                          [-1, -1, -1]])
        return cv2.filter2D(img, -1, kernel)
    
    @staticmethod
    def _resize_for_ocr(img: np.ndarray, target_width: int = 2000) -> np.ndarray:
        """Resize to optimal size for OCR"""
        height, width = img.shape[:2]
        
        if width < target_width:
            scale = target_width / width
            new_size = (target_width, int(height * scale))
            return cv2.resize(img, new_size, interpolation=cv2.INTER_CUBIC)
        
        return img
    
    @staticmethod
    def _adaptive_threshold(img: np.ndarray) -> np.ndarray:
        """Apply adaptive thresholding for better text extraction"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Adaptive Gaussian thresholding
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, 11, 2)
        
        # Convert back to BGR
        return cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)


class OCRPostprocessor:
    """
    Fixes common OCR errors AFTER extraction
    Addresses: merged fields, garbled text, wrong characters
    """
    
    # Common OCR error corrections
    OCR_CORRECTIONS = {
        'vouchernumber': 'voucher_number',
        'voucherdate': 'voucher_date',
        'suppname': 'supp_name',
        'grandtotal': 'grand_total',
    }
    
    @staticmethod
    def fix_merged_fields(text: str) -> str:
        """
        Fix fields that got merged together by OCR
        Example: "VoucherDate VoucherNumber1070172026" 
                -> "VoucherDate 10/01/2026\nVoucherNumber 113"
        """
        lines = text.split('\n')
        fixed_lines = []
        
        for line in lines:
            # Fix merged VoucherDate + VoucherNumber
            # Pattern: VoucherDate VoucherNumber[DDMMYYYY or similar]
            match = re.search(r'(voucherdate|voucher\s*date)\s*(vouchernumber|voucher\s*number|voucher\s*no)(\d{6,10})', 
                             line, re.IGNORECASE)
            if match:
                date_part = match.group(3)
                # Try to extract date from merged number
                if len(date_part) >= 8:
                    # Could be DDMMYYYY or similar
                    potential_date = OCRPostprocessor._extract_date_from_garbled(date_part)
                    if potential_date:
                        # Split into two lines
                        fixed_lines.append(f"VoucherDate {potential_date}")
                        # Try to find actual voucher number elsewhere or use generic
                        fixed_lines.append(line[match.end():].strip() or "VoucherNumber ")
                        continue
            
            # Fix other merged patterns
            line = OCRPostprocessor._split_merged_patterns(line)
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    @staticmethod
    def _extract_date_from_garbled(text: str) -> str:
        """Try to extract date from garbled OCR like '1070172026'"""
        # Remove obvious voucher number prefix
        text = re.sub(r'^0+', '', text)
        
        # Try to find DDMMYYYY pattern
        if len(text) >= 8:
            # Could be DDMMYYYY
            day = text[:2]
            month = text[2:4]
            year = text[4:8]
            
            try:
                d, m, y = int(day), int(month), int(year)
                if 1 <= d <= 31 and 1 <= m <= 12 and 2020 <= y <= 2030:
                    return f"{day}/{month}/{year}"
            except:
                pass
        
        return None
    
    @staticmethod
    def _split_merged_patterns(line: str) -> str:
        """Split merged text patterns"""
        # Add space between lowercase and uppercase transitions
        line = re.sub(r'([a-z])([A-Z])', r'\1 \2', line)
        
        # Fix common OCR artifacts
        line = line.replace('  ', ' ')
        
        return line
    
    @staticmethod
    def fix_amount_errors(text: str) -> str:
        """Fix common amount OCR errors"""
        # Fix letter O/ o instead of 0 in amounts
        # Pattern: number followed by O or o should be 0
        text = re.sub(r'(\d)O(\d)', r'\10\2', text)
        text = re.sub(r'(\d)o(\d)', r'\10\2', text)
        
        # Fix S instead of 5
        text = re.sub(r'(\d)S(\d)', r'\15\2', text)
        text = re.sub(r'(\d)s(\d)', r'\15\2', text)
        
        # Fix l or I instead of 1
        text = re.sub(r'(\d)l(\d)', r'\11\2', text)
        text = re.sub(r'(\d)I(\d)', r'\11\2', text)
        
        return text
    
    @staticmethod
    def enhance_structure(text: str) -> str:
        """Enhance text structure for better parsing"""
        # Ensure labels are on their own lines when possible
        text = re.sub(r'(VoucherNumber|Voucher Number)(\d)', r'\1\n\2', text, flags=re.IGNORECASE)
        text = re.sub(r'(VoucherDate|Voucher Date)(\d)', r'\1\n\2', text, flags=re.IGNORECASE)
        text = re.sub(r'(SuppName|Supp Name)([A-Z])', r'\1\n\2', text, flags=re.IGNORECASE)
        
        return text
    
    @staticmethod
    def postprocess(text: str) -> str:
        """Full postprocessing pipeline"""
        text = OCRPostprocessor.fix_merged_fields(text)
        text = OCRPostprocessor.fix_amount_errors(text)
        text = OCRPostprocessor.enhance_structure(text)
        return text


class EnhancedOCRPipeline:
    """
    Complete pipeline: Preprocess -> OCR -> Postprocess
    """
    
    @staticmethod
    def extract_text_enhanced(image_path: str) -> Dict:
        """
        Enhanced OCR with preprocessing and postprocessing
        """
        import os
        
        print(f"[OCR-PIPELINE] Processing: {os.path.basename(image_path)}")
        
        # Step 1: Preprocess image
        print("  [1/4] Preprocessing image...")
        preprocessed_path = OCRPreprocessor.preprocess_for_tesseract(image_path)
        
        # Step 2: Run OCR with optimal settings
        print("  [2/4] Running OCR...")
        
        # Try multiple PSM modes
        best_text = ""
        best_confidence = 0
        
        for psm in [4, 6, 3]:  # Try different page segmentation modes
            custom_config = f'--oem 3 --psm {psm}'
            text = pytesseract.image_to_string(preprocessed_path, config=custom_config)
            
            # Simple confidence estimation based on text quality
            confidence = EnhancedOCRPipeline._estimate_text_quality(text)
            
            if confidence > best_confidence:
                best_confidence = confidence
                best_text = text
        
        # Step 3: Postprocess OCR text
        print("  [3/4] Postprocessing text...")
        enhanced_text = OCRPostprocessor.postprocess(best_text)
        
        # Step 4: Cleanup temp file
        if preprocessed_path != image_path and os.path.exists(preprocessed_path):
            try:
                os.remove(preprocessed_path)
            except:
                pass
        
        print(f"  [4/4] Done! Confidence estimate: {best_confidence}%")
        
        return {
            'text': enhanced_text,
            'raw_text': best_text,
            'confidence': best_confidence,
            'preprocessed': preprocessed_path != image_path
        }
    
    @staticmethod
    def _estimate_text_quality(text: str) -> int:
        """Estimate OCR quality based on text characteristics"""
        if not text:
            return 0
        
        score = 50  # Base score
        
        # Bonus for common voucher keywords
        keywords = ['voucher', 'date', 'supp', 'total', 'amount', 'qty']
        for keyword in keywords:
            if keyword in text.lower():
                score += 5
        
        # Bonus for date patterns
        if re.search(r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}', text):
            score += 10
        
        # Bonus for amount patterns
        if re.search(r'\d+\.\d{2}', text):
            score += 10
        
        # Penalty for excessive garbage characters
        garbage_ratio = len(re.findall(r'[^\w\s\.\/\-]', text)) / max(len(text), 1)
        score -= int(garbage_ratio * 30)
        
        return max(0, min(100, score))


# Convenience function
def extract_text_enhanced(image_path: str) -> Dict:
    """Main entry point for enhanced OCR"""
    return EnhancedOCRPipeline.extract_text_enhanced(image_path)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        result = extract_text_enhanced(sys.argv[1])
        
        print("\n" + "="*60)
        print("ENHANCED OCR RESULT")
        print("="*60)
        print(f"\nConfidence: {result['confidence']}%")
        print(f"\nEnhanced Text:\n{result['text'][:500]}...")
    else:
        print("Usage: python enhanced_ocr_pipeline.py <image_path>")
