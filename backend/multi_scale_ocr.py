"""
Multi-Scale OCR Processing
Process images at multiple scales and combine results using voting
"""
import pytesseract
from PIL import Image
import numpy as np
from collections import Counter
from typing import List, Dict, Tuple


def process_at_scale(image_path: str, scale: float, custom_config: str) -> Dict:
    """
    Process image at a specific scale
    
    Args:
        image_path: Path to image
        scale: Scale factor (1.0 = original, 1.5 = 150%, 2.0 = 200%)
        custom_config: Tesseract configuration
        
    Returns:
        Dictionary with text, confidence, and scale info
    """
    # Load and scale image
    img = Image.open(image_path)
    
    if scale != 1.0:
        new_size = (int(img.width * scale), int(img.height * scale))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    
    # Extract text with confidence
    data = pytesseract.image_to_data(img, lang="eng", config=custom_config, output_type=pytesseract.Output.DICT)
    
    # Calculate average confidence
    confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    
    # Get plain text
    text = pytesseract.image_to_string(img, lang="eng", config=custom_config)
    
    return {
        'text': text.strip(),
        'confidence': avg_confidence,
        'scale': scale,
        'word_count': len([w for w in data['text'] if w.strip()])
    }


def multi_scale_ocr(image_path: str, scales: List[float] = [1.0, 1.5, 2.0], 
                    custom_config: str = None) -> Dict:
    """
    Process image at multiple scales and combine results
    
    Args:
        image_path: Path to image
        scales: List of scale factors to try
        custom_config: Tesseract configuration
        
    Returns:
        Dictionary with best result and all scale results
    """
    if custom_config is None:
        custom_config = r'--oem 1 --psm 6'
    
    results = []
    
    # Process at each scale
    for scale in scales:
        try:
            result = process_at_scale(image_path, scale, custom_config)
            results.append(result)
            print(f"[MULTI-SCALE] Scale {scale}x: {result['confidence']:.1f}% confidence, {result['word_count']} words")
        except Exception as e:
            print(f"[MULTI-SCALE] Error at scale {scale}x: {e}")
            continue
    
    if not results:
        raise Exception("All scales failed")
    
    # Find best result by confidence
    best_result = max(results, key=lambda x: x['confidence'])
    
    print(f"[MULTI-SCALE] Best scale: {best_result['scale']}x ({best_result['confidence']:.1f}%)")
    
    return {
        'text': best_result['text'],
        'confidence': best_result['confidence'],
        'best_scale': best_result['scale'],
        'all_results': results
    }


def voting_multi_scale_ocr(image_path: str, scales: List[float] = [1.0, 1.5, 2.0],
                           custom_config: str = None) -> Dict:
    """
    Process at multiple scales and use voting to combine results
    
    Args:
        image_path: Path to image
        scales: List of scale factors
        custom_config: Tesseract configuration
        
    Returns:
        Dictionary with voted result
    """
    if custom_config is None:
        custom_config = r'--oem 1 --psm 6'
    
    results = []
    
    # Process at each scale
    for scale in scales:
        try:
            result = process_at_scale(image_path, scale, custom_config)
            results.append(result)
        except Exception as e:
            print(f"[VOTING] Error at scale {scale}x: {e}")
            continue
    
    if not results:
        raise Exception("All scales failed")
    
    # Simple voting: pick most common text
    texts = [r['text'] for r in results]
    
    # If all different, pick highest confidence
    if len(set(texts)) == len(texts):
        best_result = max(results, key=lambda x: x['confidence'])
        print(f"[VOTING] All different - using highest confidence: {best_result['scale']}x")
    else:
        # Find most common
        text_counter = Counter(texts)
        most_common_text = text_counter.most_common(1)[0][0]
        
        # Get result with most common text and highest confidence
        matching_results = [r for r in results if r['text'] == most_common_text]
        best_result = max(matching_results, key=lambda x: x['confidence'])
        print(f"[VOTING] Consensus text found at scale: {best_result['scale']}x")
    
    return {
        'text': best_result['text'],
        'confidence': best_result['confidence'],
        'selected_scale': best_result['scale'],
        'all_results': results
    }


def weighted_multi_scale_ocr(image_path: str, scales: List[float] = [1.0, 1.5, 2.0],
                             custom_config: str = None) -> Dict:
    """
    Process at multiple scales with confidence-weighted selection
    
    Args:
        image_path: Path to image
        scales: List of scale factors
        custom_config: Tesseract configuration
        
    Returns:
        Dictionary with weighted best result
    """
    if custom_config is None:
        custom_config = r'--oem 1 --psm 6'
    
    results = []
    
    # Process at each scale
    for scale in scales:
        try:
            result = process_at_scale(image_path, scale, custom_config)
            results.append(result)
        except Exception as e:
            print(f"[WEIGHTED] Error at scale {scale}x: {e}")
            continue
    
    if not results:
        raise Exception("All scales failed")
    
    # Weight by confidence and word count
    for result in results:
        # Higher confidence and more words = better
        result['score'] = result['confidence'] * (1 + result['word_count'] / 100)
    
    # Pick best score
    best_result = max(results, key=lambda x: x['score'])
    
    print(f"[WEIGHTED] Best weighted score: {best_result['scale']}x (conf: {best_result['confidence']:.1f}%, words: {best_result['word_count']})")
    
    return {
        'text': best_result['text'],
        'confidence': best_result['confidence'],
        'selected_scale': best_result['scale'],
        'word_count': best_result['word_count'],
        'all_results': results
    }
