"""
Adaptive OCR Service - Multi-Pass OCR with Intelligent Ensemble
Handles poor quality vouchers through multiple strategies and smart result merging
"""

import cv2
import numpy as np
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
import pytesseract
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import Counter
import re
from difflib import SequenceMatcher
import time

# Import existing modules
from backend.image_quality import analyze_image_quality, ImageQualityMetrics
from backend.text_correction import apply_text_corrections
from backend.ocr_service import extract_text as base_extract_text

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


@dataclass
class OCRAttempt:
    """Represents a single OCR attempt with metadata"""
    mode: str
    text: str
    confidence: float
    processing_time_ms: int
    quality_score: float


@dataclass
class EnsembleResult:
    """Final merged OCR result"""
    text: str
    confidence: float
    attempts: List[OCRAttempt]
    merge_strategy: str
    field_confidence: Dict[str, float]


class AdaptiveOCRService:
    """
    Intelligent OCR service that adapts to image quality and uses
    multiple strategies to extract the best possible text
    """
    
    # Quality thresholds
    HIGH_QUALITY_THRESHOLD = 70
    MEDIUM_QUALITY_THRESHOLD = 40
    LOW_QUALITY_THRESHOLD = 20
    
    # Confidence thresholds for automatic retry
    MIN_ACCEPTABLE_CONFIDENCE = 60
    TARGET_CONFIDENCE = 85
    
    # OCR modes to try in order of aggressiveness
    OCR_MODES_SEQUENCE = [
        'optimal',      # Try best mode first
        'aggressive',   # Then more aggressive
        'experimental', # Then experimental
        'enhanced',     # Then enhanced
        'simple'        # Finally simple as fallback
    ]
    
    @staticmethod
    def extract_text_adaptive(image_path: str, max_attempts: int = 3) -> EnsembleResult:
        """
        Main entry point: Extract text using adaptive multi-pass OCR
        
        Args:
            image_path: Path to the image file
            max_attempts: Maximum number of OCR attempts (default 3)
            
        Returns:
            EnsembleResult with merged text and confidence scores
        """
        start_time = time.time()
        
        # Analyze image quality first
        quality_metrics = analyze_image_quality(image_path)
        quality_score = quality_metrics.quality_score()
        
        print(f"[ADAPTIVE-OCR] Image quality score: {quality_score:.1f}/100")
        print(f"[ADAPTIVE-OCR] Starting multi-pass OCR (max {max_attempts} attempts)")
        
        # Determine which modes to try based on quality
        modes_to_try = AdaptiveOCRService._select_modes_for_quality(quality_score)
        
        attempts = []
        best_confidence = 0
        
        # Try each mode until we hit target confidence or max attempts
        for i, mode in enumerate(modes_to_try[:max_attempts]):
            print(f"[ADAPTIVE-OCR] Attempt {i+1}/{max_attempts}: Using '{mode}' mode")
            
            try:
                result = base_extract_text(image_path, method=mode)
                
                attempt = OCRAttempt(
                    mode=mode,
                    text=result.get('text', ''),
                    confidence=result.get('confidence', 0),
                    processing_time_ms=result.get('processing_time_ms', 0),
                    quality_score=quality_score
                )
                
                attempts.append(attempt)
                best_confidence = max(best_confidence, attempt.confidence)
                
                print(f"[ADAPTIVE-OCR] Attempt {i+1} confidence: {attempt.confidence:.1f}%")
                
                # If we hit target confidence, stop early
                if attempt.confidence >= AdaptiveOCRService.TARGET_CONFIDENCE:
                    print(f"[ADAPTIVE-OCR] Target confidence reached! Stopping early.")
                    break
                    
            except Exception as e:
                print(f"[ADAPTIVE-OCR] Attempt {i+1} failed: {e}")
                continue
        
        # If no attempts succeeded, return error
        if not attempts:
            return EnsembleResult(
                text="[OCR FAILED] All attempts failed",
                confidence=0,
                attempts=[],
                merge_strategy="failed",
                field_confidence={}
            )
        
        # Merge results from all attempts
        merged_result = AdaptiveOCRService._ensemble_merge(attempts)
        
        total_time = int((time.time() - start_time) * 1000)
        print(f"[ADAPTIVE-OCR] Completed in {total_time}ms with final confidence: {merged_result.confidence:.1f}%")
        
        return merged_result
    
    @staticmethod
    def _select_modes_for_quality(quality_score: float) -> List[str]:
        """Select appropriate OCR modes based on image quality"""
        if quality_score >= AdaptiveOCRService.HIGH_QUALITY_THRESHOLD:
            # Good quality: Try optimal, then enhanced
            return ['optimal', 'enhanced', 'simple']
        elif quality_score >= AdaptiveOCRService.MEDIUM_QUALITY_THRESHOLD:
            # Medium quality: Aggressive preprocessing needed
            return ['optimal', 'aggressive', 'enhanced', 'experimental']
        else:
            # Poor quality: Use all aggressive modes
            return ['aggressive', 'experimental', 'optimal', 'enhanced']
    
    @staticmethod
    def _ensemble_merge(attempts: List[OCRAttempt]) -> EnsembleResult:
        """
        Intelligently merge OCR results from multiple attempts
        Uses voting for common lines and confidence weighting
        """
        if len(attempts) == 1:
            # Only one attempt, use it directly
            return EnsembleResult(
                text=attempts[0].text,
                confidence=attempts[0].confidence,
                attempts=attempts,
                merge_strategy="single",
                field_confidence=AdaptiveOCRService._calculate_field_confidence(attempts[0].text, attempts)
            )
        
        # Split all attempts into lines
        all_lines = {}
        for attempt in attempts:
            lines = attempt.text.split('\n')
            for i, line in enumerate(lines):
                if i not in all_lines:
                    all_lines[i] = []
                all_lines[i].append((line.strip(), attempt.confidence, attempt.mode))
        
        # For each line position, select the best version
        merged_lines = []
        for line_idx in sorted(all_lines.keys()):
            line_options = all_lines[line_idx]
            best_line = AdaptiveOCRService._select_best_line(line_options)
            if best_line:  # Only add non-empty lines
                merged_lines.append(best_line)
        
        merged_text = '\n'.join(merged_lines)
        
        # Calculate overall confidence
        avg_confidence = sum(a.confidence for a in attempts) / len(attempts)
        max_confidence = max(a.confidence for a in attempts)
        
        # Weight toward max confidence but consider consistency
        merged_confidence = (max_confidence * 0.6) + (avg_confidence * 0.4)
        
        return EnsembleResult(
            text=merged_text,
            confidence=merged_confidence,
            attempts=attempts,
            merge_strategy="ensemble_voting",
            field_confidence=AdaptiveOCRService._calculate_field_confidence(merged_text, attempts)
        )
    
    @staticmethod
    def _select_best_line(line_options: List[Tuple[str, float, str]]) -> str:
        """
        Select the best version of a line from multiple OCR attempts
        Uses a combination of:
        1. Length heuristic (prefer complete lines)
        2. Character validity
        3. Confidence weighting
        4. Similarity voting
        """
        if not line_options:
            return ""
        
        # Filter out empty lines
        valid_options = [(line, conf, mode) for line, conf, mode in line_options if line.strip()]
        if not valid_options:
            return ""
        
        # If only one option, return it
        if len(valid_options) == 1:
            return valid_options[0][0]
        
        # Score each option
        scored_options = []
        for i, (line1, conf1, mode1) in enumerate(valid_options):
            score = conf1  # Base score from OCR confidence
            
            # Bonus for length (more complete extraction)
            score += min(len(line1) * 0.5, 10)
            
            # Bonus for valid characters (fewer replacement characters)
            valid_char_ratio = sum(1 for c in line1 if c.isprintable()) / max(len(line1), 1)
            score += valid_char_ratio * 10
            
            # Similarity bonus - lines that match other attempts get bonus
            similarity_bonus = 0
            for j, (line2, conf2, mode2) in enumerate(valid_options):
                if i != j:
                    sim = SequenceMatcher(None, line1.lower(), line2.lower()).ratio()
                    similarity_bonus += sim * 5
            score += similarity_bonus
            
            scored_options.append((line1, score))
        
        # Return the highest scoring line
        scored_options.sort(key=lambda x: x[1], reverse=True)
        return scored_options[0][0]
    
    @staticmethod
    def _calculate_field_confidence(text: str, attempts: List[OCRAttempt]) -> Dict[str, float]:
        """
        Calculate per-field confidence scores based on OCR consistency
        This helps identify which fields need human review
        """
        field_confidence = {
            'overall': max(a.confidence for a in attempts),
            'voucher_number': 50,  # Default medium confidence
            'date': 50,
            'supplier': 50,
            'amounts': 50,
            'items': 50
        }
        
        # Check for voucher number patterns
        if re.search(r'voucher\s*(?:no|number|#)?[:\s]*\d+', text, re.IGNORECASE):
            field_confidence['voucher_number'] = 75
        if re.search(r'\b\d{3,}\b', text):
            field_confidence['voucher_number'] = max(field_confidence['voucher_number'], 60)
        
        # Check for date patterns
        if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', text):
            field_confidence['date'] = 75
        if re.search(r'date', text, re.IGNORECASE):
            field_confidence['date'] = max(field_confidence['date'], 65)
        
        # Check for supplier patterns
        if re.search(r'supp(?:lier|lier|lier)?\s*(?:name)?', text, re.IGNORECASE):
            field_confidence['supplier'] = 70
        
        # Check for amount patterns
        amount_patterns = len(re.findall(r'\d+\.\d{2}', text))
        if amount_patterns >= 3:
            field_confidence['amounts'] = 80
        elif amount_patterns >= 1:
            field_confidence['amounts'] = 65
        
        # Adjust based on OCR consistency across attempts
        if len(attempts) > 1:
            consistency_bonus = min(20, len(attempts) * 5)
            for field in field_confidence:
                if field != 'overall':
                    field_confidence[field] = min(95, field_confidence[field] + consistency_bonus)
        
        return field_confidence


class FieldSpecificOCR:
    """
    Performs OCR on specific regions of the image for critical fields
    This is useful when general OCR misses important data
    """
    
    # Common receipt regions (as percentages of image dimensions)
    REGION_TOP = (0, 0, 1.0, 0.3)      # Top 30% - usually has header info
    REGION_MIDDLE = (0, 0.2, 1.0, 0.6)  # Middle 40% - usually has items
    REGION_BOTTOM = (0, 0.7, 1.0, 0.3)  # Bottom 30% - usually has totals
    REGION_LEFT = (0, 0, 0.5, 1.0)      # Left half
    REGION_RIGHT = (0.5, 0, 0.5, 1.0)   # Right half
    
    @staticmethod
    def extract_from_region(image_path: str, region: Tuple[float, float, float, float], 
                           preprocessing: str = 'aggressive') -> Dict:
        """
        Extract text from a specific region of the image
        
        Args:
            image_path: Path to image
            region: (x, y, width, height) as ratios (0-1)
            preprocessing: Preprocessing mode to use
            
        Returns:
            Dict with text and confidence
        """
        try:
            # Load image
            img = Image.open(image_path)
            width, height = img.size
            
            # Calculate crop coordinates
            x = int(region[0] * width)
            y = int(region[1] * height)
            w = int(region[2] * width)
            h = int(region[3] * height)
            
            # Crop region
            cropped = img.crop((x, y, x + w, y + h))
            
            # Save temporarily for OCR
            temp_path = image_path + f"_region_{x}_{y}.jpg"
            cropped.save(temp_path)
            
            # Run OCR on cropped region
            result = base_extract_text(temp_path, method=preprocessing)
            
            # Cleanup temp file
            import os
            try:
                os.remove(temp_path)
            except:
                pass
            
            return result
            
        except Exception as e:
            print(f"[FIELD-OCR] Region extraction failed: {e}")
            return {'text': '', 'confidence': 0}
    
    @staticmethod
    def extract_critical_fields(image_path: str, full_text: str) -> Dict[str, Dict]:
        """
        Attempt to extract critical fields using region-specific OCR
        when they're missing from the full text
        """
        results = {
            'header': {},
            'totals': {},
            'items': {}
        }
        
        # Check if we need header extraction
        if not re.search(r'voucher|supplier|date', full_text, re.IGNORECASE):
            print("[FIELD-OCR] Header info missing, extracting from top region...")
            results['header'] = FieldSpecificOCR.extract_from_region(
                image_path, FieldSpecificOCR.REGION_TOP, 'aggressive'
            )
        
        # Check if we need totals extraction
        if not re.search(r'total|amount|grand', full_text, re.IGNORECASE):
            print("[FIELD-OCR] Totals missing, extracting from bottom region...")
            results['totals'] = FieldSpecificOCR.extract_from_region(
                image_path, FieldSpecificOCR.REGION_BOTTOM, 'aggressive'
            )
        
        return results


class QualityAwarePreprocessor:
    """
    Preprocesses images based on detected quality issues
    Applies targeted enhancements for specific problems
    """
    
    @staticmethod
    def preprocess_for_quality(image_path: str) -> str:
        """
        Preprocess image based on quality analysis
        Returns path to preprocessed image
        """
        quality = analyze_image_quality(image_path)
        
        # Load image
        img = cv2.imread(image_path)
        
        # Apply targeted corrections
        if quality.needs_brightness_correction():
            img = QualityAwarePreprocessor._fix_brightness(img, quality.brightness)
        
        if quality.needs_contrast_enhancement():
            img = QualityAwarePreprocessor._fix_contrast(img, quality.contrast)
        
        if quality.needs_denoising():
            img = QualityAwarePreprocessor._fix_noise(img, quality.noise_level)
        
        if quality.needs_sharpening():
            img = QualityAwarePreprocessor._fix_sharpness(img, quality.sharpness)
        
        if quality.needs_deskewing():
            img = QualityAwarePreprocessor._fix_skew(img, quality.skew_angle)
        
        # Always upscale if needed
        if quality.needs_upscaling():
            img = QualityAwarePreprocessor._upscale(img)
        
        # Save preprocessed image
        preprocessed_path = image_path.replace('.jpg', '_preprocessed.jpg').replace('.png', '_preprocessed.png')
        cv2.imwrite(preprocessed_path, img)
        
        return preprocessed_path
    
    @staticmethod
    def _fix_brightness(img: np.ndarray, brightness: float) -> np.ndarray:
        """Adjust image brightness"""
        if brightness < 80:
            # Too dark - brighten
            gamma = 0.7
        else:
            # Too bright - darken
            gamma = 1.3
        
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255
                         for i in range(256)]).astype("uint8")
        return cv2.LUT(img, table)
    
    @staticmethod
    def _fix_contrast(img: np.ndarray, contrast: float) -> np.ndarray:
        """Enhance contrast using CLAHE"""
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        clip_limit = 3.0 if contrast < 20 else 2.0
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
        l = clahe.apply(l)
        
        lab = cv2.merge((l, a, b))
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    
    @staticmethod
    def _fix_noise(img: np.ndarray, noise_level: float) -> np.ndarray:
        """Apply denoising"""
        if noise_level > 40:
            return cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)
        else:
            return cv2.bilateralFilter(img, 9, 75, 75)
    
    @staticmethod
    def _fix_sharpness(img: np.ndarray, sharpness: float) -> np.ndarray:
        """Apply sharpening"""
        if sharpness < 10:
            kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        else:
            kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        
        return cv2.filter2D(img, -1, kernel)
    
    @staticmethod
    def _fix_skew(img: np.ndarray, angle: float) -> np.ndarray:
        """Correct skew"""
        if abs(angle) < 1:
            return img
        
        (h, w) = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, 
                             borderMode=cv2.BORDER_REPLICATE)
    
    @staticmethod
    def _upscale(img: np.ndarray, target_width: int = 2000) -> np.ndarray:
        """Upscale image for better OCR"""
        current_width = img.shape[1]
        if current_width >= target_width:
            return img
        
        scale_factor = target_width / current_width
        new_size = (int(img.shape[1] * scale_factor), int(img.shape[0] * scale_factor))
        return cv2.resize(img, new_size, interpolation=cv2.INTER_CUBIC)


# Convenience function for easy integration
def extract_text_robust(image_path: str) -> Dict:
    """
    Main function to extract text with robust handling of poor quality images
    Returns a dictionary compatible with existing code
    """
    # Run adaptive OCR
    result = AdaptiveOCRService.extract_text_adaptive(image_path)
    
    # Apply text corrections
    corrected_text = apply_text_corrections(result.text)
    
    # Check for missing critical fields and try region-specific extraction
    if result.confidence < 70:
        print("[ROBUST-OCR] Low confidence detected, trying field-specific extraction...")
        field_results = FieldSpecificOCR.extract_critical_fields(image_path, corrected_text)
        
        # Merge field-specific results if they improve confidence
        for region, region_result in field_results.items():
            if region_result.get('confidence', 0) > 50:
                print(f"[ROBUST-OCR] Adding text from {region} region")
                corrected_text += "\n" + region_result.get('text', '')
    
    return {
        'text': corrected_text,
        'raw_text': result.text,
        'confidence': result.confidence,
        'field_confidence': result.field_confidence,
        'attempts': [
            {
                'mode': a.mode,
                'confidence': a.confidence,
                'processing_time_ms': a.processing_time_ms
            }
            for a in result.attempts
        ],
        'merge_strategy': result.merge_strategy
    }


if __name__ == "__main__":
    # Test the adaptive OCR service
    import sys
    
    if len(sys.argv) > 1:
        test_image = sys.argv[1]
        print(f"\nTesting Adaptive OCR on: {test_image}\n")
        result = extract_text_robust(test_image)
        
        print(f"\n{'='*60}")
        print(f"FINAL RESULT")
        print(f"{'='*60}")
        print(f"Confidence: {result['confidence']:.1f}%")
        print(f"Strategy: {result['merge_strategy']}")
        print(f"\nField Confidence:")
        for field, conf in result['field_confidence'].items():
            print(f"  {field}: {conf}%")
        print(f"\nText Preview (first 500 chars):")
        print(result['text'][:500])
        print(f"\n{'='*60}")
    else:
        print("Usage: python adaptive_ocr_service.py <image_path>")
