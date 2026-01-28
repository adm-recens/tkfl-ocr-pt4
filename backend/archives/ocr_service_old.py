"""
Production OCR Service - Enhanced OCR with Tesseract Optimization
Includes text corrections, decimal fixing, and dynamic whitelisting.
"""
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
import pytesseract
import cv2
import numpy as np
import os
import time

# Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def deskew_image(image):
    """
    Auto-deskew image using text orientation detection
    """
    try:
        # Convert PIL to OpenCV format
        img_array = np.array(image)
        
        # Convert to grayscale if needed
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # Detect text orientation
        coords = np.column_stack(np.where(gray > 0))
        if len(coords) < 10:
            return image  # Not enough data to deskew
            
        angle = cv2.minAreaRect(coords)[-1]
        
        # Adjust angle
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        # Only deskew if angle is significant (> 0.5 degrees)
        if abs(angle) > 0.5:
            (h, w) = gray.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(img_array, M, (w, h), 
                                     flags=cv2.INTER_CUBIC, 
                                     borderMode=cv2.BORDER_REPLICATE)
            return Image.fromarray(rotated)
        
        return image
    except Exception as e:
        print(f"[WARN] Deskew failed: {e}, using original image")
        return image

def enhance_image_quality(image):
    """
    Apply advanced preprocessing for better OCR
    """
    # Convert to grayscale
    if image.mode != 'L':
        image = ImageOps.grayscale(image)
    
    # Convert to OpenCV format for advanced processing
    img_array = np.array(image)
    
    # 1. Gentle noise reduction
    denoised = cv2.bilateralFilter(img_array, 5, 50, 50)
    
    # 2. Moderate CLAHE
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8,8))
    enhanced = clahe.apply(denoised)
    
    # 3. Otsu's binarization
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Convert back to PIL
    result = Image.fromarray(binary)
    
    return result

def preprocess_image(path, method='enhanced'):
    """
    Preprocessing - starting conservative, matching production
    
    Args:
        path: Image file path
        method: 'enhanced' (production + Tesseract config), 'simple' (exact production), 
                'experimental' (advanced), 'adaptive' (quality-aware), 'aggressive' (strong),
                'optimal' (unified best)
    
    Returns:
        Preprocessed PIL Image or (Image, QualityMetrics) tuple
    """
    img = Image.open(path)
    
    # IMPROVEMENT: Upscale small images (Tesseract works better with larger images)
    if img.width < 1000:
        scale_factor = 2
        new_size = (img.width * scale_factor, img.height * scale_factor)
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        print(f"[INFO] Upscaled image from {img.width // scale_factor}x{img.height // scale_factor} to {img.width}x{img.height}")
    
    # Import quality analysis for all modes
    from backend.image_quality import analyze_image_quality
    
    # Analyze image quality for adaptive preprocessing decisions
    quality_metrics = analyze_image_quality(path)
    
    if method == 'simple':
        # EXACT PRODUCTION METHOD - proven to work
        img = ImageOps.grayscale(img)
        img = img.filter(ImageFilter.MedianFilter(size=3))
        return img
    
    elif method == 'experimental':
        # Advanced preprocessing - Now with quality-aware enhancements
        # Step 1: Grayscale
        img = ImageOps.grayscale(img)
        img_array = np.array(img)
        
        # Step 2: Quality-aware denoising
        if quality_metrics.noise_level > 30:
            print(f"[EXPERIMENTAL] High noise detected ({quality_metrics.noise_level:.1f}), applying bilateral filter")
            img_array = cv2.bilateralFilter(img_array, 5, 50, 50)
        else:
            # Standard median filter
            img = Image.fromarray(img_array)
            img = img.filter(ImageFilter.MedianFilter(size=3))
            img_array = np.array(img)
        
        # Step 3: Quality-aware CLAHE
        if quality_metrics.contrast < 20:
            clip_limit = 2.5  
            print(f"[EXPERIMENTAL] Low contrast ({quality_metrics.contrast:.1f}), using CLAHE 2.5")
        elif quality_metrics.contrast < 30:
            clip_limit = 1.5  
        else:
            clip_limit = 1.2  
        
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8,8))
        enhanced = clahe.apply(img_array)
        
        # Step 4: Otsu's binarization
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Convert back to PIL
        img = Image.fromarray(binary)
        
        # Step 5: Quality-aware sharpening
        if quality_metrics.sharpness < 15:
            print(f"[EXPERIMENTAL] Low sharpness ({quality_metrics.sharpness:.1f}), applying strong sharpening")
            img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=150, threshold=3))
        else:
            # Standard sharpening
            img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=100, threshold=3))
        
        return img
    
    elif method == 'adaptive':
        # PHASE 1: Adaptive preprocessing based on image quality analysis
        from backend.image_quality import (
            apply_gamma_correction,
            adaptive_clahe,
            adaptive_sharpen,
            adaptive_denoise,
            deskew_image as deskew_quality
        )
        
        print(f"[ADAPTIVE] Quality Analysis:")
        print(f"  Brightness: {quality_metrics.brightness:.1f}")
        print(f"  Contrast: {quality_metrics.contrast:.1f}")
        print(f"  Sharpness: {quality_metrics.sharpness:.1f}")
        print(f"  Noise: {quality_metrics.noise_level:.1f}")
        print(f"  Skew: {quality_metrics.skew_angle:.2f}°")
        print(f"  Quality Score: {quality_metrics.quality_score():.1f}/100")
        
        # Convert to grayscale and numpy array
        img = ImageOps.grayscale(img)
        img_array = np.array(img)
        
        # Step 1: Brightness correction
        if quality_metrics.needs_brightness_correction():
            print(f"[ADAPTIVE] Applying brightness correction")
            if quality_metrics.brightness < 80:
                gamma = 0.7  
            else:
                gamma = 1.3  
            img_array = apply_gamma_correction(img_array, gamma)
        
        # Step 2: Denoising
        if quality_metrics.needs_denoising():
            print(f"[ADAPTIVE] Applying denoising")
            img_array = adaptive_denoise(img_array, quality_metrics.noise_level)
        
        # Step 3: Contrast enhancement
        if quality_metrics.needs_contrast_enhancement():
            print(f"[ADAPTIVE] Applying contrast enhancement")
            img_array = adaptive_clahe(img_array, quality_metrics.contrast)
        
        # Step 4: Binarization
        _, binary = cv2.threshold(img_array, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Step 5: Sharpening
        if quality_metrics.needs_sharpening():
            print(f"[ADAPTIVE] Applying sharpening")
            binary = adaptive_sharpen(binary, quality_metrics.sharpness)
        
        # Step 6: Deskewing
        if quality_metrics.needs_deskewing():
            print(f"[ADAPTIVE] Applying deskew ({quality_metrics.skew_angle:.2f}°)")
            binary = deskew_quality(binary, quality_metrics.skew_angle)
        
        # Convert back to PIL
        img = Image.fromarray(binary)
        
        return img, quality_metrics
    
    elif method == 'optimal':
        # UNIFIED OPTIMAL MODE - Combines all Phase 1-3 optimizations
        from backend.image_quality import (
            apply_gamma_correction,
            adaptive_denoise,
            deskew_image as deskew_quality
        )
        from backend.advanced_binarization import auto_select_binarization
        
        quality_score = quality_metrics.quality_score()
        
        print(f"[OPTIMAL] Quality Score: {quality_score:.1f}/100")
        print(f"[OPTIMAL] Brightness: {quality_metrics.brightness:.1f}, Contrast: {quality_metrics.contrast:.1f}")
        print(f"[OPTIMAL] Sharpness: {quality_metrics.sharpness:.1f}, Noise: {quality_metrics.noise_level:.1f}")
        
        # Convert to grayscale
        img = ImageOps.grayscale(img)
        img_array = np.array(img)
        
        # Step 2: Brightness correction
        if quality_metrics.brightness < 80 or quality_metrics.brightness > 200:
            gamma = 0.7 if quality_metrics.brightness < 80 else 1.3
            print(f"[OPTIMAL] Applying brightness correction (gamma={gamma})")
            img_array = apply_gamma_correction(img_array, gamma)
        
        # Step 3: Adaptive denoising
        if quality_metrics.noise_level > 25:
            print(f"[OPTIMAL] High noise detected, applying strong denoising")
            img_array = cv2.fastNlMeansDenoising(img_array, None, h=10, templateWindowSize=7, searchWindowSize=21)
        elif quality_metrics.noise_level > 15:
            print(f"[OPTIMAL] Moderate noise detected, applying median blur")
            img_array = cv2.medianBlur(img_array, 3)
        
        # Step 4: Adaptive contrast enhancement
        if quality_metrics.contrast < 30:
            clip_limit = 2.5 if quality_score < 50 else 1.5
            print(f"[OPTIMAL] Low contrast, applying CLAHE (clip={clip_limit})")
            clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8,8))
            img_array = clahe.apply(img_array)
        elif quality_metrics.contrast < 40:
            print(f"[OPTIMAL] Moderate contrast, applying gentle CLAHE")
            clahe = cv2.createCLAHE(clipLimit=1.2, tileGridSize=(8,8))
            img_array = clahe.apply(img_array)
        
        # Step 5: Adaptive binarization
        binary, binarization_method = auto_select_binarization(img_array, quality_metrics)
        print(f"[OPTIMAL] Using {binarization_method} binarization")
        
        # Step 6: Adaptive sharpening
        if quality_metrics.sharpness < 20:
            print(f"[OPTIMAL] Low sharpness, applying strong sharpening")
            kernel = np.array([[-1, -1, -1], [-1,  9, -1], [-1, -1, -1]])
            binary = cv2.filter2D(binary, -1, kernel)
        elif quality_metrics.sharpness < 30:
            print(f"[OPTIMAL] Moderate sharpness, applying light sharpening")
            kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
            binary = cv2.filter2D(binary, -1, kernel)
        
        # Step 7: Deskewing
        if abs(quality_metrics.skew_angle) > 1.0:
            print(f"[OPTIMAL] Deskewing image ({quality_metrics.skew_angle:.2f}°)")
            binary = deskew_quality(binary, quality_metrics.skew_angle)
        
        # Step 8: Morphological cleanup
        kernel = np.ones((2,2), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        
        # Convert back to PIL
        img = Image.fromarray(binary)
        
        print(f"[OPTIMAL] Preprocessing complete")
        return img, quality_metrics
    
    elif method == 'aggressive':
        # PHASE 2: Advanced preprocessing with adaptive binarization
        from backend.advanced_binarization import auto_select_binarization
        
        print(f"[AGGRESSIVE] Quality Analysis:")
        print(f"  Brightness: {quality_metrics.brightness:.1f}")
        print(f"  Contrast: {quality_metrics.contrast:.1f}")
        
        # Convert to grayscale
        img = ImageOps.grayscale(img)
        img_array = np.array(img)
        
        # Step 1: Aggressive denoising
        if quality_metrics.noise_level > 20:
            print(f"[AGGRESSIVE] Applying strong denoising")
            img_array = cv2.fastNlMeansDenoising(img_array, None, h=10, templateWindowSize=7, searchWindowSize=21)
        
        # Step 2: Aggressive contrast enhancement
        if quality_metrics.contrast < 40:
            print(f"[AGGRESSIVE] Applying strong CLAHE")
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8,8))
            img_array = clahe.apply(img_array)
        
        # Step 3: Adaptive binarization
        binary, binarization_method = auto_select_binarization(img_array, quality_metrics)
        print(f"[AGGRESSIVE] Using {binarization_method} binarization")
        
        # Step 4: Aggressive sharpening
        if quality_metrics.sharpness < 25:
            print(f"[AGGRESSIVE] Applying strong sharpening")
            kernel = np.array([[-1, -1, -1], [-1,  9, -1], [-1, -1, -1]])
            binary = cv2.filter2D(binary, -1, kernel)
        
        # Step 5: Morphological operations
        kernel = np.ones((2,2), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        
        # Convert back to PIL
        img = Image.fromarray(binary)
        
        return img, quality_metrics
    
    else:  # 'enhanced' (default)
        # PRODUCTION METHOD + Quality-aware enhancements
        img = ImageOps.grayscale(img)
        img_array = np.array(img)
        
        # Quality-aware median filter
        if quality_metrics.noise_level > 25:
            print(f"[ENHANCED] Noise detected ({quality_metrics.noise_level:.1f}), using median filter size 5")
            img_array = cv2.medianBlur(img_array, 5)
        else:
            img_array = cv2.medianBlur(img_array, 3)
        
        # Quality-aware contrast adjustment
        if quality_metrics.contrast < 35:
            print(f"[ENHANCED] Low contrast ({quality_metrics.contrast:.1f}), applying gentle CLAHE")
            clahe = cv2.createCLAHE(clipLimit=1.2, tileGridSize=(8,8))
            img_array = clahe.apply(img_array)
        
        img = Image.fromarray(img_array)
        return img

def extract_text(image_path: str, method='optimal') -> dict:
    """
    Extract text from image using optimized Tesseract configuration
    
    Args:
        image_path: Path to image file
        method: 'enhanced' (default), 'simple', 'experimental', 'adaptive', 'aggressive', 'optimal'
    
    Returns:
        dict with text, confidence, preprocessing_method, processing_time_ms
    """
    start_time = time.time()
    
    try:
        # Preprocess image
        preprocessing_result = preprocess_image(image_path, method=method)
        
        # Handle adaptive mode returning tuple (img, quality_metrics)
        quality_metrics = None
        if isinstance(preprocessing_result, tuple):
            img, quality_metrics = preprocessing_result
        else:
            img = preprocessing_result
        
        # KEY IMPROVEMENT: Dynamic whitelist based on content
        from backend.dynamic_whitelist import DynamicWhitelist
        
        # Prepare Tesseract configuration
        custom_config = ''
        
        if method == 'optimal':
            # PSM AUTO-SELECTION (Phase 3 Complete)
            # Try PSM 4 (Columnar) first - often best for receipts
            # Then try PSM 6 (Block) if confidence is low or just to compare
            
            # Pass 1: PSM 4 (Single column of variable sizes)
            print(f"[OPTIMAL] Running Pass 1 (PSM 4 - Columnar)...")
            config_psm4 = DynamicWhitelist.build_tesseract_config(whitelist_type='general', psm=4, oem=1)
            config_psm4 += ' -c preserve_interword_spaces=1'
            
            data_psm4 = pytesseract.image_to_data(img, lang="eng", config=config_psm4, output_type=pytesseract.Output.DICT)
            confidences_psm4 = [int(conf) for conf in data_psm4['conf'] if int(conf) > 0]
            avg_conf_psm4 = sum(confidences_psm4) / len(confidences_psm4) if confidences_psm4 else 0
            
            # Pass 2: PSM 6 (Uniform block of text)
            print(f"[OPTIMAL] Running Pass 2 (PSM 6 - Block)...")
            config_psm6 = DynamicWhitelist.build_tesseract_config(whitelist_type='general', psm=6, oem=1)
            config_psm6 += ' -c preserve_interword_spaces=1'
            
            data_psm6 = pytesseract.image_to_data(img, lang="eng", config=config_psm6, output_type=pytesseract.Output.DICT)
            confidences_psm6 = [int(conf) for conf in data_psm6['conf'] if int(conf) > 0]
            avg_conf_psm6 = sum(confidences_psm6) / len(confidences_psm6) if confidences_psm6 else 0
            
            # Compare and select winner
            if avg_conf_psm4 >= avg_conf_psm6:
                print(f"[OPTIMAL] Selected PSM 4 (Columnar) - Confidence: {avg_conf_psm4:.1f}% vs {avg_conf_psm6:.1f}%")
                data = data_psm4
                custom_config = config_psm4
                text = pytesseract.image_to_string(img, lang="eng", config=config_psm4)
            else:
                print(f"[OPTIMAL] Selected PSM 6 (Block) - Confidence: {avg_conf_psm6:.1f}% vs {avg_conf_psm4:.1f}%")
                data = data_psm6
                custom_config = config_psm6
                text = pytesseract.image_to_string(img, lang="eng", config=config_psm6)
            
        else:
            # Standard single-pass for other modes
            custom_config = DynamicWhitelist.build_tesseract_config(
                whitelist_type='general', 
                psm=6, 
                oem=1  
            )
            custom_config += ' -c preserve_interword_spaces=1'
            
            print(f"[OCR] Using dynamic whitelist config for {method}")
            
            # Extract text with confidence data
            data = pytesseract.image_to_data(img, lang="eng", config=custom_config, output_type=pytesseract.Output.DICT)
            text = pytesseract.image_to_string(img, lang="eng", config=custom_config)
        
        # Calculate average confidence from selected data
        confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        processing_time = int((time.time() - start_time) * 1000)
        
        # Apply text corrections to improve OCR output with progress indicators
        from backend.text_correction import apply_text_corrections
        from backend.decimal_correction import apply_decimal_corrections
        
        print(f"[OCR] Initial extraction confidence: {avg_confidence:.2f}")
        
        # Apply text corrections with feedback
        raw_text = text or ""
        corrected_intermediate = apply_text_corrections(raw_text)
        print(f"[OCR] Raw OCR length: {len(raw_text)} chars")
        print(f"[OCR] After text corrections: {len(corrected_intermediate)} chars")
        
        final_corrected_text = apply_decimal_corrections(corrected_intermediate)
        print(f"[OCR] After decimal corrections: {len(final_corrected_text)} chars")
        
        if len(raw_text) > 0:
            print(f"[OCR] Text correction rate: {(len(final_corrected_text) - len(raw_text)) / len(raw_text) * 100:.1f}%")
        
        result = {
            'text': final_corrected_text,
            'raw_text': raw_text,
            'confidence': round(avg_confidence, 2),
            'preprocessing_method': method,
            'processing_time_ms': processing_time
        }
        
        # Add quality metrics if available
        if quality_metrics:
            result['quality_metrics'] = {
                'quality_score': quality_metrics.quality_score(),
                'brightness': quality_metrics.brightness,
                'contrast': quality_metrics.contrast,
                'sharpness': quality_metrics.sharpness,
                'noise_level': quality_metrics.noise_level
            }
            
        return result
        
    except Exception as e:
        processing_time = int((time.time() - start_time) * 1000)
        print(f"[ERROR] OCR failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            'text': f"[OCR ERROR] {e}",
            'confidence': 0,
            'preprocessing_method': method,
            'processing_time_ms': processing_time
        }

def extract_numbers_focused(image_path: str) -> dict:
    """
    Specialized extraction focused on numeric fields with enhanced preprocessing
    Uses numeric-optimized Tesseract configuration for better number recognition
    """
    start_time = time.time()
    
    try:
        # Preprocess with enhanced settings for numbers
        img = Image.open(image_path)
        
        # Upscale for better number recognition
        if img.width < 1500:
            scale_factor = 2.5
            new_size = (int(img.width * scale_factor), int(img.height * scale_factor))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            print(f"[NUMERIC] Upscaled image for number extraction")
        
        # Convert to grayscale and enhance contrast for numbers
        img = ImageOps.grayscale(img)
        img_array = np.array(img)
        
        # Strong contrast enhancement for numbers
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced = clahe.apply(img_array)
        
        # Otsu thresholding optimized for numbers
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Morphological operations to clean up numbers
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2,2))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        img = Image.fromarray(binary)
        
        # Use numeric-focused whitelist
        from backend.dynamic_whitelist import DynamicWhitelist
        numeric_config = DynamicWhitelist.build_tesseract_config(
            whitelist_type='number', 
            psm=6, 
            oem=1
        )
        numeric_config += ' -c preserve_interword_spaces=1'
        
        print(f"[NUMERIC] Using optimized numeric configuration")
        
        # Extract text with numeric focus
        data = pytesseract.image_to_data(img, lang="eng", config=numeric_config, output_type=pytesseract.Output.DICT)
        text = pytesseract.image_to_string(img, lang="eng", config=numeric_config)
        
        # Apply text corrections
        from backend.text_correction import apply_text_corrections
        corrected_text = apply_text_corrections(text or "")
        
        # Calculate confidence
        confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return {
            'text': corrected_text,
            'raw_text': text or "",
            'confidence': round(avg_confidence, 2),
            'preprocessing_method': 'numeric_focused',
            'processing_time_ms': processing_time
        }
        
    except Exception as e:
        processing_time = int((time.time() - start_time) * 1000)
        print(f"[ERROR] Numeric extraction failed: {e}")
        return {
            'text': f"[NUMERIC ERROR] {e}",
            'raw_text': f"[NUMERIC ERROR] {e}",
            'confidence': 0,
            'preprocessing_method': 'numeric_focused',
            'processing_time_ms': processing_time
        }
