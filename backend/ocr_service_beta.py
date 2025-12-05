"""
Beta OCR Service - Enhanced OCR with Tesseract Optimization
Based on production ocr_service.py with improvements for better accuracy
"""
print(f"[DEBUG] Loaded ocr_service_beta.py from: {__file__}, module: {__name__}")

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
    
    # 1. Gentle noise reduction (reduced from 9, 75, 75)
    denoised = cv2.bilateralFilter(img_array, 5, 50, 50)
    
    # 2. Moderate CLAHE (reduced from 2.0)
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8,8))
    enhanced = clahe.apply(denoised)
    
    # 3. Otsu's binarization
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Convert back to PIL
    result = Image.fromarray(binary)
    
    return result

def preprocess_image_beta(path, method='enhanced'):
    """
    Beta preprocessing - starting conservative, matching production
    
    Args:
        path: Image file path
        method: 'enhanced' (production + Tesseract config), 'simple' (exact production), 'experimental' (advanced)
    
    Returns:
        Preprocessed PIL Image
    """
    img = Image.open(path)
    
    # IMPROVEMENT: Upscale small images (Tesseract works better with larger images)
    # Only upscale if width < 1000px to avoid processing already large images
    if img.width < 1000:
        scale_factor = 2
        new_size = (img.width * scale_factor, img.height * scale_factor)
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        print(f"[INFO] Upscaled image from {img.width // scale_factor}x{img.height // scale_factor} to {img.width}x{img.height}")
    
    if method == 'simple':
        # EXACT PRODUCTION METHOD - proven to work
        img = ImageOps.grayscale(img)
        img = img.filter(ImageFilter.MedianFilter(size=3))
        return img
    
    elif method == 'experimental':
        # Advanced preprocessing (currently disabled - was too aggressive)
        # TODO: Fine-tune these parameters with real data
        img = ImageOps.grayscale(img)
        img_array = np.array(img)
        
        # Very gentle CLAHE
        clahe = cv2.createCLAHE(clipLimit=1.2, tileGridSize=(8,8))
        enhanced = clahe.apply(img_array)
        
        # Otsu's binarization
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        img = Image.fromarray(binary)
        return img
    
    else:  # 'enhanced' (default)
        # PRODUCTION METHOD (proven) + Tesseract optimization
        # This is the safest starting point
        img = ImageOps.grayscale(img)
        img = img.filter(ImageFilter.MedianFilter(size=3))
        return img

def extract_text_beta(image_path: str, method='enhanced') -> dict:
    """
    Extract text from image using optimized Tesseract configuration
    
    The 'enhanced' method uses PRODUCTION preprocessing (proven to work)
    with OPTIMIZED Tesseract configuration (PSM 6, OEM 1)
    
    Args:
        image_path: Path to image file
        method: 'enhanced' (default), 'simple', 'experimental'
    
    Returns:
        dict with text, confidence, preprocessing_method, processing_time_ms
    """
    start_time = time.time()
    
    try:
        # Preprocess image
        img = preprocess_image_beta(image_path, method=method)
        
        # KEY IMPROVEMENT: Optimized Tesseract configuration
        # PSM 6: Assume a single uniform block of text (better for receipts than default PSM 3)
        # OEM 1: LSTM neural net mode (more accurate than legacy engine)
        # Character whitelist: Restrict to common receipt characters (reduces false positives)
        #   - Numbers: 0-9
        #   - Letters: A-Z, a-z
        #   - Common symbols: . , / - : ( ) & $ ₹ (space)
        #   - This prevents misreading | as I, 0 as O, etc.
        custom_config = r'--oem 1 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,/-:()&$₹ '
        
        # Extract text with confidence data
        data = pytesseract.image_to_data(img, lang="eng", config=custom_config, output_type=pytesseract.Output.DICT)
        
        # Calculate average confidence
        confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Get plain text
        text = pytesseract.image_to_string(img, lang="eng", config=custom_config)
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return {
            'text': text or "",
            'confidence': round(avg_confidence, 2),
            'preprocessing_method': method,
            'processing_time_ms': processing_time
        }
        
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

# Backward compatibility function
def extract_text(image_path: str) -> str:
    """
    Simple extraction for backward compatibility
    Returns just the text string
    """
    result = extract_text_beta(image_path, method='enhanced')
    return result['text']
