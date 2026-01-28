import os
import sys
import json
import shutil
from backend.smart_crop import SmartReceiptDetector
from backend.services.ml_feedback_service import MLFeedbackService

def test_ml_pipeline():
    print("=== Testing ML Pipeline ===")
    
    # Setup paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    uploads_dir = os.path.join(base_dir, 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)
    
    # 1. Create a dummy image
    import cv2
    import numpy as np
    
    # Create black image with a white rectangle (simulating a receipt)
    img = np.zeros((800, 600, 3), dtype=np.uint8)
    # Receipt area: x=100, y=100, w=400, h=600
    cv2.rectangle(img, (100, 100), (500, 700), (255, 255, 255), -1) 
    
    test_image_path = os.path.join(uploads_dir, 'test_receipt.jpg')
    cv2.imwrite(test_image_path, img)
    print(f"[TEST] Created dummy image: {test_image_path}")

    # 2. Test SmartReceiptDetector
    print("\n[TEST] Running SmartReceiptDetector...")
    detector = SmartReceiptDetector()
    result = detector.detect_receipt(test_image_path)
    
    if result['success']:
        print(f"  [SUCCESS] Detection worked! Confidence: {result['confidence']}")
        print(f"  BBox: {result['bbox']}")
    else:
        print(f"  [FAILED] Detection failed: {result.get('error')}")

    # 3. Test MLFeedbackService
    print("\n[TEST] Running MLFeedbackService...")
    # Simulate user correction (slightly different from detection)
    user_crop = {
        'x': 90, 'y': 90, 'width': 420, 'height': 620, 'rotate': 0
    }
    
    success = MLFeedbackService.save_crop_feedback(test_image_path, user_crop)
    
    if success:
        print("  [SUCCESS] Feedback saved.")
        
        # Verify file existence
        jsonl_path = MLFeedbackService.ANNOTATIONS_FILE
        if os.path.exists(jsonl_path):
            with open(jsonl_path, 'r') as f:
                lines = f.readlines()
                last_line = json.loads(lines[-1])
                print(f"  [VERIFY] JSONL Record: {last_line['original_filename']}")
                print(f"  [VERIFY] Saved Crop Data: {last_line['user_crop']}")
        else:
            print("  [FAILED] JSONL file not found!")
    else:
        print("  [FAILED] Feedback save returned False")

    # Cleanup
    if os.path.exists(test_image_path):
        os.remove(test_image_path)
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_ml_pipeline()
