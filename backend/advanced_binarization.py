"""
Advanced Binarization Techniques
Implements multiple binarization methods for different image characteristics
"""
import cv2
import numpy as np
from typing import Tuple


def adaptive_gaussian_threshold(gray_image: np.ndarray, block_size: int = 11, C: int = 2) -> np.ndarray:
    """
    Adaptive Gaussian thresholding - good for uneven lighting
    
    Args:
        gray_image: Grayscale image
        block_size: Size of pixel neighborhood (must be odd)
        C: Constant subtracted from weighted mean
        
    Returns:
        Binary image
    """
    return cv2.adaptiveThreshold(
        gray_image, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size, C
    )


def adaptive_mean_threshold(gray_image: np.ndarray, block_size: int = 11, C: int = 2) -> np.ndarray:
    """
    Adaptive mean thresholding
    
    Args:
        gray_image: Grayscale image
        block_size: Size of pixel neighborhood (must be odd)
        C: Constant subtracted from mean
        
    Returns:
        Binary image
    """
    return cv2.adaptiveThreshold(
        gray_image, 255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY,
        block_size, C
    )


def sauvola_threshold(gray_image: np.ndarray, window_size: int = 15, k: float = 0.2, R: float = 128) -> np.ndarray:
    """
    Sauvola binarization - excellent for documents with uneven lighting
    
    Formula: T(x,y) = mean(x,y) * [1 + k * (std(x,y)/R - 1)]
    
    Args:
        gray_image: Grayscale image
        window_size: Local window size
        k: Parameter (typically 0.2-0.5)
        R: Dynamic range of standard deviation (typically 128)
        
    Returns:
        Binary image
    """
    # Ensure window size is odd
    if window_size % 2 == 0:
        window_size += 1
    
    # Convert to float
    img_float = gray_image.astype(np.float64)
    
    # Calculate local mean
    mean = cv2.boxFilter(img_float, -1, (window_size, window_size), normalize=True)
    
    # Calculate local standard deviation
    mean_sq = cv2.boxFilter(img_float ** 2, -1, (window_size, window_size), normalize=True)
    std = np.sqrt(mean_sq - mean ** 2)
    
    # Sauvola threshold
    threshold = mean * (1 + k * ((std / R) - 1))
    
    # Apply threshold
    binary = np.where(img_float > threshold, 255, 0).astype(np.uint8)
    
    return binary


def auto_select_binarization(gray_image: np.ndarray, quality_metrics=None) -> Tuple[np.ndarray, str]:
    """
    Automatically select best binarization method based on image characteristics
    
    Args:
        gray_image: Grayscale image
        quality_metrics: Optional ImageQualityMetrics object
        
    Returns:
        Tuple of (binary image, method name)
    """
    # Calculate image statistics
    mean_brightness = np.mean(gray_image)
    std_brightness = np.std(gray_image)
    
    # Decision logic
    if quality_metrics:
        # Use quality metrics if available
        if quality_metrics.contrast < 25:
            # Very low contrast - use Sauvola
            method = 'sauvola'
            binary = sauvola_threshold(gray_image, window_size=15, k=0.3)
        elif quality_metrics.brightness < 100 or quality_metrics.brightness > 200:
            # Uneven lighting - use adaptive Gaussian
            method = 'adaptive_gaussian'
            binary = adaptive_gaussian_threshold(gray_image, block_size=11, C=2)
        else:
            # Good quality - use Otsu
            method = 'otsu'
            _, binary = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        # Fallback to statistics-based selection
        if std_brightness < 30:
            # Low variance - use Sauvola
            method = 'sauvola'
            binary = sauvola_threshold(gray_image)
        elif mean_brightness < 100 or mean_brightness > 180:
            # Extreme brightness - use adaptive
            method = 'adaptive_gaussian'
            binary = adaptive_gaussian_threshold(gray_image)
        else:
            # Normal - use Otsu
            method = 'otsu'
            _, binary = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return binary, method


def compare_binarization_methods(gray_image: np.ndarray) -> dict:
    """
    Compare multiple binarization methods and return all results
    
    Args:
        gray_image: Grayscale image
        
    Returns:
        Dictionary with method names as keys and binary images as values
    """
    results = {}
    
    # Otsu
    _, results['otsu'] = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Adaptive Gaussian
    results['adaptive_gaussian'] = adaptive_gaussian_threshold(gray_image)
    
    # Adaptive Mean
    results['adaptive_mean'] = adaptive_mean_threshold(gray_image)
    
    # Sauvola
    results['sauvola'] = sauvola_threshold(gray_image)
    
    return results
