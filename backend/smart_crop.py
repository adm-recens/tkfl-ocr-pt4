"""
Smart Receipt Crop - Intelligent Boundary Detection
Phase 6A: Auto-detect receipt boundaries using computer vision

Features:
1. Edge detection (Canny + Hough Transform)
2. Perspective correction for skewed receipts
3. Confidence scoring for auto-approval
4. Multi-strategy fallback (edge → contour → manual)
"""

import cv2
import numpy as np
from typing import Tuple, Dict, Optional
import os

class SmartReceiptDetector:
    """
    Intelligent receipt boundary detection with confidence scoring
    """
    
    def __init__(self):
        # Detection thresholds
        self.MIN_AREA_RATIO = 0.1  # Receipt should be at least 10% of image
        self.MAX_AREA_RATIO = 0.95  # But not the entire image
        self.MIN_ASPECT_RATIO = 0.3  # Receipts are usually tall/narrow
        self.MAX_ASPECT_RATIO = 3.0
        
        # Confidence thresholds
        self.HIGH_CONFIDENCE = 0.85  # Auto-approve
        self.MEDIUM_CONFIDENCE = 0.65  # Show preview
        self.LOW_CONFIDENCE = 0.0  # Force manual
    
    def detect_receipt(self, image_path: str) -> Dict:
        """
        Main detection pipeline - tries multiple strategies
        
        Returns:
            {
                'success': bool,
                'cropped_image': np.array or None,
                'bbox': [x, y, w, h],
                'confidence': float (0-1),
                'method': str ('edge_detection', 'contour', 'failed'),
                'needs_manual_review': bool,
                'preview_path': str (saved preview image)
            }
        """
        try:
            # Load image
            image = cv2.imread(image_path)
            if image is None:
                return self._failed_result("Could not load image")
            
            original_h, original_w = image.shape[:2]
            
            # Strategy 1: Edge Detection (Best for clean backgrounds)
            result = self._edge_detection_method(image)
            if result['confidence'] >= self.MEDIUM_CONFIDENCE:
                result['preview_path'] = self._save_preview(image, result, image_path)
                return result
            
            # Strategy 2: Contour Detection (Fallback for noisy backgrounds)
            result = self._contour_method(image)
            if result['confidence'] >= self.MEDIUM_CONFIDENCE:
                result['preview_path'] = self._save_preview(image, result, image_path)
                return result
            
            # Both failed - force manual
            return self._failed_result("Auto-detection failed - manual cropping required")
            
        except Exception as e:
            return self._failed_result(f"Detection error: {e}")
    
    def _edge_detection_method(self, image: np.ndarray) -> Dict:
        """
        Strategy 1: Use Canny edge detection + contour approximation
        Works best for receipts with clear edges
        """
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Reduce noise
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Edge detection
            edges = cv2.Canny(blurred, 50, 150, apertureSize=3)
            
            # Dilate to connect nearby edges
            kernel = np.ones((5, 5), np.uint8)
            dilated = cv2.dilate(edges, kernel, iterations=2)
            
            # Find contours
            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return self._failed_result("No contours found")
            
            # Find largest rectangular contour
            for contour in sorted(contours, key=cv2.contourArea, reverse=True):
                area = cv2.contourArea(contour)
                image_area = image.shape[0] * image.shape[1]
                
                # Check area ratio
                area_ratio = area / image_area
                if area_ratio < self.MIN_AREA_RATIO or area_ratio > self.MAX_AREA_RATIO:
                    continue
                
                # Approximate contour to polygon
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # If 4 corners (rectangle), apply perspective transform
                if len(approx) == 4:
                    rect = self._order_points(approx.reshape(4, 2))
                    warped = self._four_point_transform(image, rect)
                    
                    # Calculate confidence based on shape quality
                    confidence = self._calculate_confidence(warped, area_ratio, 'rectangle')
                    
                    h, w = warped.shape[:2]
                    return {
                        'success': True,
                        'cropped_image': warped,
                        'bbox': [0, 0, w, h],  # Already transformed
                        'confidence': confidence,
                        'method': 'edge_detection_perspective',
                        'needs_manual_review': confidence < self.HIGH_CONFIDENCE,
                        'corners': approx.reshape(4, 2).tolist()
                    }
                
                # Otherwise use bounding box
                else:
                    x, y, w, h = cv2.boundingRect(contour)
                    
                    # Add small padding
                    padding = int(min(w, h) * 0.02)
                    x = max(0, x - padding)
                    y = max(0, y - padding)
                    w = min(image.shape[1] - x, w + 2 * padding)
                    h = min(image.shape[0] - y, h + 2 * padding)
                    
                    cropped = image[y:y+h, x:x+w]
                    confidence = self._calculate_confidence(cropped, area_ratio, 'bounding_box')
                    
                    return {
                        'success': True,
                        'cropped_image': cropped,
                        'bbox': [x, y, w, h],
                        'confidence': confidence,
                        'method': 'edge_detection_bbox',
                        'needs_manual_review': confidence < self.HIGH_CONFIDENCE
                    }
            
            return self._failed_result("No valid receipt contour found")
            
        except Exception as e:
            return self._failed_result(f"Edge detection failed: {e}")
    
    def _contour_method(self, image: np.ndarray) -> Dict:
        """
        Strategy 2: Simple contour detection (fallback)
        More robust for noisy backgrounds
        """
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Binary threshold
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return self._failed_result("No contours in threshold")
            
            # Get largest contour
            largest = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest)
            image_area = image.shape[0] * image.shape[1]
            area_ratio = area / image_area
            
            if area_ratio < self.MIN_AREA_RATIO:
                return self._failed_result("Receipt area too small")
            
            x, y, w, h = cv2.boundingRect(largest)
            
            # Add padding
            padding = int(min(w, h) * 0.03)
            x = max(0, x - padding)
            y = max(0, y - padding)
            w = min(image.shape[1] - x, w + 2 * padding)
            h = min(image.shape[0] - y, h + 2 * padding)
            
            cropped = image[y:y+h, x:x+w]
            confidence = self._calculate_confidence(cropped, area_ratio, 'contour')
            
            return {
                'success': True,
                'cropped_image': cropped,
                'bbox': [x, y, w, h],
                'confidence': confidence,
                'method': 'contour_detection',
                'needs_manual_review': confidence < self.HIGH_CONFIDENCE
            }
            
        except Exception as e:
            return self._failed_result(f"Contour method failed: {e}")
    
    def _calculate_confidence(self, cropped: np.ndarray, area_ratio: float, method: str) -> float:
        """
        Calculate confidence score based on multiple factors
        """
        confidence = 0.5  # Base confidence
        
        # Factor 1: Area ratio (optimal: 0.3 - 0.8)
        if 0.3 <= area_ratio <= 0.8:
            confidence += 0.2
        elif 0.15 <= area_ratio <= 0.9:
            confidence += 0.1
        
        # Factor 2: Aspect ratio (receipts are usually tall)
        h, w = cropped.shape[:2]
        aspect = h / w if w > 0 else 0
        
        if self.MIN_ASPECT_RATIO <= aspect <= self.MAX_ASPECT_RATIO:
            confidence += 0.15
        
        # Factor 3: Method bonus
        if method == 'rectangle':
            confidence += 0.15  # Rectangle detection is most accurate
        elif method == 'bounding_box':
            confidence += 0.05
        
        # Factor 4: Image clarity (check if not too blurry)
        gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        if laplacian_var > 100:  # Sharp image
            confidence += 0.1
        elif laplacian_var > 50:
            confidence += 0.05
        
        return min(1.0, confidence)
    
    def _order_points(self, pts: np.ndarray) -> np.ndarray:
        """
        Order points in consistent manner: top-left, top-right, bottom-right, bottom-left
        """
        rect = np.zeros((4, 2), dtype="float32")
        
        # Top-left has smallest sum, bottom-right has largest sum
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        
        # Top-right has smallest diff, bottom-left has largest diff
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        
        return rect
    
    def _four_point_transform(self, image: np.ndarray, rect: np.ndarray) -> np.ndarray:
        """
        Apply perspective transform to get bird's eye view
        """
        (tl, tr, br, bl) = rect
        
        # Calculate width
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))
        
        # Calculate height
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))
        
        # Destination points
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]
        ], dtype="float32")
        
        # Perspective transform
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
        
        return warped
    
    def _save_preview(self, original: np.ndarray, result: Dict, original_path: str) -> str:
        """
        Save preview image showing detection boundaries
        """
        try:
            preview = original.copy()
            
            # Draw bounding box
            if 'bbox' in result:
                x, y, w, h = result['bbox']
                cv2.rectangle(preview, (x, y), (x+w, y+h), (0, 255, 0), 3)
            
            # Draw corners if available (perspective detection)
            if 'corners' in result:
                corners = np.array(result['corners'], dtype=np.int32)
                cv2.polylines(preview, [corners], True, (0, 0, 255), 3)
            
            # Add text overlay
            confidence_pct = int(result['confidence'] * 100)
            text = f"Confidence: {confidence_pct}% ({result['method']})"
            cv2.putText(preview, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                       1, (255, 255, 255), 2, cv2.LINE_AA)
            
            # Save preview
            base_name = os.path.basename(original_path)
            preview_path = original_path.replace(base_name, f"preview_{base_name}")
            cv2.imwrite(preview_path, preview)
            
            return preview_path
            
        except Exception as e:
            print(f"[WARNING] Preview save failed: {e}")
            return ""
    
    def _failed_result(self, reason: str) -> Dict:
        """
        Return failed detection result
        """
        return {
            'success': False,
            'cropped_image': None,
            'bbox': None,
            'confidence': 0.0,
            'method': 'failed',
            'needs_manual_review': True,
            'error': reason
        }


# Convenience function for quick testing
def test_detection(image_path: str) -> None:
    """
    Test smart detection on a single image
    """
    print(f"\n{'='*60}")
    print(f"Testing: {os.path.basename(image_path)}")
    print(f"{'='*60}")
    
    detector = SmartReceiptDetector()
    result = detector.detect_receipt(image_path)
    
    print(f"\nResult:")
    print(f"  Success: {result['success']}")
    print(f"  Method: {result['method']}")
    print(f"  Confidence: {result['confidence']:.2%}")
    print(f"  Needs Manual Review: {result['needs_manual_review']}")
    
    if result['success']:
        print(f"  Cropped Size: {result['cropped_image'].shape[:2]}")
        if 'preview_path' in result:
            print(f"  Preview Saved: {result['preview_path']}")
    else:
        print(f"  Error: {result.get('error', 'Unknown error')}")
    
    print(f"{'='*60}\n")
    
    return result


if __name__ == "__main__":
    # Test with sample image
    import sys
    if len(sys.argv) > 1:
        test_detection(sys.argv[1])
    else:
        print("Usage: python smart_crop.py <image_path>")
