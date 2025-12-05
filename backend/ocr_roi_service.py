import cv2
import numpy as np
import pytesseract
from PIL import Image
import os

# Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def read_image_safe(path):
    """
    Read image safely handling Windows paths and non-ASCII characters.
    """
    try:
        # Read file as byte stream and decode
        stream = np.fromfile(path, dtype=np.uint8)
        image = cv2.imdecode(stream, cv2.IMREAD_COLOR)
        return image
    except Exception as e:
        print(f"[ERROR] Failed to read image: {e}")
        return None

def validate_image(image):
    """
    Check if image is valid and not empty.
    """
    return image is not None and image.size > 0

def auto_crop(image):
    """
    Automatically crop borders and remove unnecessary background.
    Detects the receipt's main content area using contour detection.
    """
    if not validate_image(image):
        return image

    try:
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply binary threshold
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return image
        
        # Find the largest contour (assuming it's the receipt)
        largest_contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest_contour)
        
        # Add small padding (5%)
        padding = int(min(w, h) * 0.05)
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(image.shape[1] - x, w + 2 * padding)
        h = min(image.shape[0] - y, h + 2 * padding)
        
        # Validate crop dimensions
        if w <= 0 or h <= 0:
            return image

        # Crop the image
        cropped = image[y:y+h, x:x+w]
        
        if not validate_image(cropped):
            return image
            
        return cropped
    except Exception as e:
        print(f"[WARNING] Auto-crop failed: {e}")
        return image

def deskew(image):
    """
    Straighten skewed/rotated images using Hough line detection.
    """
    if not validate_image(image) or len(image.shape) < 2:
        return image

    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Detect lines using Hough transform
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 100)
        
        if lines is None:
            return image
        
        # Calculate average angle
        angles = []
        for line in lines[:10]:  # Use top 10 lines
            rho, theta = line[0]
            angle = np.degrees(theta) - 90
            if -45 < angle < 45:  # Only consider reasonable angles
                angles.append(angle)
        
        if not angles:
            return image
        
        median_angle = np.median(angles)
        
        # Rotate image to straighten
        if abs(median_angle) > 0.5:  # Only rotate if needed
            (h, w) = image.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
            rotated = cv2.warpAffine(image, M, (w, h), 
                                     flags=cv2.INTER_CUBIC, 
                                     borderMode=cv2.BORDER_REPLICATE)
            return rotated
        
        return image
    except Exception as e:
        print(f"[WARNING] Deskew failed: {e}")
        return image

def detect_regions(image):
    """
    Detect different regions of the receipt (header, items, deductions, totals).
    Uses horizontal line detection to split the receipt into sections.
    """
    if not validate_image(image):
        # Return default regions for empty image to avoid crash
        return {}

    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        
        # Detect horizontal lines (often separate sections on receipts)
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (w // 3, 1))
        detect_horizontal = cv2.morphologyEx(gray, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
        _, thresh = cv2.threshold(detect_horizontal, 127, 255, cv2.THRESH_BINARY_INV)
        
        # Find horizontal line positions
        horizontal_lines = []
        for i in range(h):
            if np.mean(thresh[i, :]) > 200:  # Mostly white (line detected)
                horizontal_lines.append(i)
        
        # Filter close lines (keep only distinct separators)
        filtered_lines = []
        if horizontal_lines:
            filtered_lines.append(horizontal_lines[0])
            for line in horizontal_lines:
                if line - filtered_lines[-1] > h * 0.1:  # At least 10% apart
                    filtered_lines.append(line)
        
        # Define regions based on detected lines and heuristics
        regions = {}
        
        if len(filtered_lines) >= 2:
            # Header: top to first line
            regions['header'] = (0, filtered_lines[0])
            
            # Items: first line to second-to-last line
            regions['items'] = (filtered_lines[0], filtered_lines[-2] if len(filtered_lines) > 2 else filtered_lines[-1])
            
            # Deductions/Totals: last section
            regions['deductions'] = (filtered_lines[-2] if len(filtered_lines) > 2 else filtered_lines[-1], 
                                     filtered_lines[-1])
            regions['totals'] = (filtered_lines[-1], h)
        else:
            # Fallback: split into thirds
            third = h // 3
            regions['header'] = (0, third)
            regions['items'] = (third, 2 * third)
            regions['deductions'] = (2 * third, h)
            regions['totals'] = (2 * third, h)
        
        return regions
    except Exception as e:
        print(f"[WARNING] Region detection failed: {e}")
        # Fallback regions
        h = image.shape[0]
        third = h // 3
        return {
            'header': (0, third),
            'items': (third, 2 * third),
            'deductions': (2 * third, h),
            'totals': (2 * third, h)
        }

def preprocess_region(image, region_type):
    """
    Apply region-specific preprocessing for better OCR.
    Different regions benefit from different preprocessing.
    """
    if not validate_image(image):
        return image

    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        if region_type == 'header':
            # Header: optimize for text clarity
            denoised = cv2.fastNlMeansDenoising(gray)
            _, processed = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        elif region_type == 'items':
            # Items table: enhance grid structure
            denoised = cv2.fastNlMeansDenoising(gray)
            # Adaptive threshold works better for tables
            processed = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                              cv2.THRESH_BINARY, 11, 2)
        
        elif region_type in ['deductions', 'totals']:
            # Numbers: high contrast
            denoised = cv2.fastNlMeansDenoising(gray)
            _, processed = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        else:
            processed = gray
        
        return processed
    except Exception as e:
        print(f"[WARNING] Preprocessing failed for {region_type}: {e}")
        return image

def extract_with_roi(image_path):
    """
    Main function: Extract text from receipt using ROI-based approach.
    Returns dict with text per region.
    """
    try:
        # Read image safely
        image = read_image_safe(image_path)
        if not validate_image(image):
            return {"error": "[OCR ERROR] Could not read image or image is empty"}
        
        # Step 1: Auto-crop - DISABLED for manual cropping workflow
        # Users manually crop with Cropper.js, so auto-crop is redundant and can be too aggressive
        # cropped = auto_crop(image)
        cropped = image  # Use image as-is (already manually cropped)
        
        # Step 2: Deskew
        straightened = deskew(cropped)
        
        # Step 3: Detect regions
        regions = detect_regions(straightened)
        
        # Step 4: Extract text per region
        extracted_text = {
            'full_text': '',
            'regions': {}
        }
        
        for region_name, (y_start, y_end) in regions.items():
            # Validate region bounds
            if y_start >= y_end:
                continue
                
            # Extract region
            region_img = straightened[y_start:y_end, :]
            
            # Skip empty regions
            if not validate_image(region_img):
                continue
            
            # Preprocess region
            processed = preprocess_region(region_img, region_name)
            
            # OCR
            text = pytesseract.image_to_string(processed, lang='eng')
            extracted_text['regions'][region_name] = text.strip()
        
        # Combine all regions for full text
        extracted_text['full_text'] = '\n'.join([
            extracted_text['regions'].get('header', ''),
            extracted_text['regions'].get('items', ''),
            extracted_text['regions'].get('deductions', ''),
            extracted_text['regions'].get('totals', '')
        ])
        
        return extracted_text
        
    except Exception as e:
        return {"error": f"[OCR ERROR] {str(e)}"}
