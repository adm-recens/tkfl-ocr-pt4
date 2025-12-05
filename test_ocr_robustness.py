import cv2
import numpy as np
import os
from backend.ocr_roi_service import extract_with_roi, auto_crop, deskew, detect_regions, preprocess_region

def test_robustness():
    print("Testing robustness against invalid inputs...")
    
    # Test 1: Non-existent file
    print("\nTest 1: Non-existent file")
    result = extract_with_roi("non_existent_file.jpg")
    print(f"Result: {result}")
    
    # Test 2: Empty image passed to functions
    print("\nTest 2: Empty image passed to internal functions")
    empty_img = np.array([], dtype=np.uint8)
    
    res_crop = auto_crop(empty_img)
    print(f"auto_crop result size: {res_crop.size}")
    
    res_deskew = deskew(empty_img)
    print(f"deskew result size: {res_deskew.size}")
    
    res_regions = detect_regions(empty_img)
    print(f"detect_regions result: {res_regions}")
    
    res_preprocess = preprocess_region(empty_img, 'header')
    print(f"preprocess_region result size: {res_preprocess.size}")
    
    # Test 3: None passed to functions
    print("\nTest 3: None passed to internal functions")
    res_crop_none = auto_crop(None)
    print(f"auto_crop(None) result: {res_crop_none}")

    print("\nRobustness test complete.")

if __name__ == "__main__":
    test_robustness()
