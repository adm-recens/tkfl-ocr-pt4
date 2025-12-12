"""
Image Quality Analysis Module
Analyzes image quality metrics to determine appropriate preprocessing
"""
import cv2
import numpy as np
from PIL import Image, ImageStat
from dataclasses import dataclass
from typing import Tuple

@dataclass
class ImageQualityMetrics:
    """Container for image quality metrics"""
    brightness: float  # 0-255, optimal: 100-200
    contrast: float    # 0-100, optimal: >30
    sharpness: float   # 0-100, optimal: >20
    noise_level: float # 0-100, optimal: <30
    skew_angle: float  # degrees, optimal: <2
    resolution: Tuple[int, int]  # (width, height)
    
    def needs_brightness_correction(self) -> bool:
        """Check if brightness correction is needed"""
        return self.brightness < 80 or self.brightness > 220
    
    def needs_contrast_enhancement(self) -> bool:
        """Check if contrast enhancement is needed"""
        return self.contrast < 30
    
    def needs_sharpening(self) -> bool:
        """Check if sharpening is needed"""
        return self.sharpness < 20
    
    def needs_denoising(self) -> bool:
        """Check if denoising is needed"""
        return self.noise_level > 30
    
    def needs_deskewing(self) -> bool:
        """Check if deskewing is needed"""
        return abs(self.skew_angle) > 2
    
    def needs_upscaling(self) -> bool:
        """Check if upscaling is needed"""
        return self.resolution[0] < 1000
    
    def quality_score(self) -> float:
        """Overall quality score 0-100"""
        score = 100.0
        
        # Penalize for issues
        if self.needs_brightness_correction():
            score -= 15
        if self.needs_contrast_enhancement():
            score -= 20
        if self.needs_sharpening():
            score -= 15
        if self.needs_denoising():
            score -= 20
        if self.needs_deskewing():
            score -= 10
        if self.needs_upscaling():
            score -= 10
        
        return max(0, score)


def analyze_image_quality(image_path: str) -> ImageQualityMetrics:
    """
    Analyze image quality and return metrics
    
    Args:
        image_path: Path to image file
        
    Returns:
        ImageQualityMetrics object with all quality metrics
    """
    # Load image
    pil_image = Image.open(image_path)
    cv_image = cv2.imread(image_path)
    gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
    
    # 1. Brightness (mean pixel value)
    brightness = np.mean(gray)
    
    # 2. Contrast (standard deviation)
    contrast = np.std(gray)
    
    # 3. Sharpness (Laplacian variance)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    sharpness = laplacian.var()
    
    # 4. Noise level (estimate using median absolute deviation)
    noise_level = estimate_noise(gray)
    
    # 5. Skew angle
    skew_angle = detect_skew(gray)
    
    # 6. Resolution
    resolution = (pil_image.width, pil_image.height)
    
    return ImageQualityMetrics(
        brightness=float(brightness),
        contrast=float(contrast),
        sharpness=float(sharpness),
        noise_level=float(noise_level),
        skew_angle=float(skew_angle),
        resolution=resolution
    )


def estimate_noise(gray_image: np.ndarray) -> float:
    """
    Estimate noise level using median absolute deviation
    
    Args:
        gray_image: Grayscale image array
        
    Returns:
        Noise level (0-100)
    """
    # Use high-pass filter to isolate noise
    kernel = np.array([[-1, -1, -1],
                       [-1,  8, -1],
                       [-1, -1, -1]])
    
    filtered = cv2.filter2D(gray_image, -1, kernel)
    
    # Calculate median absolute deviation
    mad = np.median(np.abs(filtered - np.median(filtered)))
    
    # Normalize to 0-100 scale
    noise_level = min(100, mad * 2)
    
    return noise_level


def detect_skew(gray_image: np.ndarray) -> float:
    """
    Detect skew angle using Hough Line Transform
    
    Args:
        gray_image: Grayscale image array
        
    Returns:
        Skew angle in degrees
    """
    try:
        # Edge detection
        edges = cv2.Canny(gray_image, 50, 150, apertureSize=3)
        
        # Hough Line Transform
        lines = cv2.HoughLines(edges, 1, np.pi/180, 200)
        
        if lines is None:
            return 0.0
        
        # Calculate angles
        angles = []
        for rho, theta in lines[:, 0]:
            angle = np.degrees(theta) - 90
            if -45 < angle < 45:  # Only consider reasonable angles
                angles.append(angle)
        
        if not angles:
            return 0.0
        
        # Return median angle
        return float(np.median(angles))
        
    except Exception:
        return 0.0


def apply_gamma_correction(image: np.ndarray, gamma: float) -> np.ndarray:
    """
    Apply gamma correction to adjust brightness
    
    Args:
        image: Input image array
        gamma: Gamma value (< 1 brightens, > 1 darkens)
        
    Returns:
        Corrected image
    """
    inv_gamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** inv_gamma) * 255
                      for i in range(256)]).astype("uint8")
    
    return cv2.LUT(image, table)


def adaptive_clahe(image: np.ndarray, contrast_level: float) -> np.ndarray:
    """
    Apply adaptive CLAHE based on contrast level
    
    Args:
        image: Input grayscale image
        contrast_level: Current contrast level (0-100)
        
    Returns:
        Enhanced image
    """
    # Determine clip limit based on contrast
    if contrast_level < 20:
        clip_limit = 3.0  # Strong enhancement
    elif contrast_level < 30:
        clip_limit = 2.0  # Medium enhancement
    else:
        clip_limit = 1.5  # Gentle enhancement
    
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    return clahe.apply(image)


def adaptive_sharpen(image: np.ndarray, sharpness_level: float) -> np.ndarray:
    """
    Apply adaptive sharpening based on sharpness level
    
    Args:
        image: Input image
        sharpness_level: Current sharpness level (0-100)
        
    Returns:
        Sharpened image
    """
    if sharpness_level < 10:
        # Strong sharpening
        kernel = np.array([[-1, -1, -1],
                          [-1,  9, -1],
                          [-1, -1, -1]])
    elif sharpness_level < 20:
        # Medium sharpening
        kernel = np.array([[0, -1, 0],
                          [-1, 5, -1],
                          [0, -1, 0]])
    else:
        # Gentle sharpening
        kernel = np.array([[0, -0.5, 0],
                          [-0.5, 3, -0.5],
                          [0, -0.5, 0]])
    
    return cv2.filter2D(image, -1, kernel)


def adaptive_denoise(image: np.ndarray, noise_level: float) -> np.ndarray:
    """
    Apply adaptive denoising based on noise level
    
    Args:
        image: Input image
        noise_level: Current noise level (0-100)
        
    Returns:
        Denoised image
    """
    if noise_level < 20:
        # No denoising needed
        return image
    elif noise_level < 40:
        # Gentle denoising
        return cv2.bilateralFilter(image, 5, 30, 30)
    else:
        # Strong denoising
        return cv2.fastNlMeansDenoising(image, None, h=10, templateWindowSize=7, searchWindowSize=21)


def deskew_image(image: np.ndarray, angle: float) -> np.ndarray:
    """
    Rotate image to correct skew
    
    Args:
        image: Input image
        angle: Rotation angle in degrees
        
    Returns:
        Deskewed image
    """
    if abs(angle) < 0.5:  # Skip if angle is negligible
        return image
    
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    
    # Rotation matrix
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    
    # Rotate
    rotated = cv2.warpAffine(image, M, (w, h),
                             flags=cv2.INTER_CUBIC,
                             borderMode=cv2.BORDER_REPLICATE)
    
    return rotated
