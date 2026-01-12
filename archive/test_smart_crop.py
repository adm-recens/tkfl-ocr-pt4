"""
Test Script: Smart Receipt Detection
Tests auto-crop functionality on sample receipts

Usage:
    python test_smart_crop.py <receipt_image_path>
    python test_smart_crop.py <folder_with_receipts>
"""

import os
import sys
import cv2
from backend.smart_crop import SmartReceiptDetector, test_detection

def test_single_image(image_path):
    """Test detection on a single image"""
    if not os.path.exists(image_path):
        print(f"❌ Error: File not found: {image_path}")
        return False
    
    result = test_detection(image_path)
    
    # Show result visually
    if result['success']:
        print(f"\n✅ AUTO-CROP {'APPROVED' if result['confidence'] >= 0.85 else 'REVIEW NEEDED'}")
        
        # Save cropped result for inspection
        if result['cropped_image'] is not None:
            base = os.path.basename(image_path)
            output_path = image_path.replace(base, f"cropped_{base}")
            cv2.imwrite(output_path, result['cropped_image'])
            print(f"💾 Cropped image saved: {output_path}")
    else:
        print(f"\n❌ AUTO-CROP FAILED - Manual cropping required")
        print(f"Reason: {result.get('error', 'Unknown')}")
    
    return result['success']

def test_folder(folder_path):
    """Test detection on all images in a folder"""
    if not os.path.isdir(folder_path):
        print(f"❌ Error: Not a directory: {folder_path}")
        return
    
    # Find all image files
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    images = [
        os.path.join(folder_path, f) 
        for f in os.listdir(folder_path) 
        if os.path.splitext(f.lower())[1] in image_extensions
    ]
    
    if not images:
        print(f"❌ No images found in: {folder_path}")
        return
    
    print(f"\n{'='*70}")
    print(f"BATCH TEST: {len(images)} images found")
    print(f"{'='*70}\n")
    
    results = {
        'total': len(images),
        'success': 0,
        'high_confidence': 0,
        'medium_confidence': 0,
        'failed': 0
    }
    
    for i, img_path in enumerate(images, 1):
        print(f"\n[{i}/{len(images)}] Processing: {os.path.basename(img_path)}")
        
        detector = SmartReceiptDetector()
        result = detector.detect_receipt(img_path)
        
        if result['success']:
            results['success'] += 1
            conf = result['confidence']
            
            if conf >= 0.85:
                results['high_confidence'] += 1
                print(f"   ✅ HIGH CONFIDENCE: {conf:.1%} - Auto-approved")
            elif conf >= 0.65:
                results['medium_confidence'] += 1
                print(f"   ⚠️  MEDIUM CONFIDENCE: {conf:.1%} - Needs review")
            else:
                print(f"   ❌ LOW CONFIDENCE: {conf:.1%} - Manual crop needed")
            
            # Save cropped
            if result['cropped_image'] is not None:
                base = os.path.basename(img_path)
                output_path = img_path.replace(base, f"cropped_{base}")
                cv2.imwrite(output_path, result['cropped_image'])
        else:
            results['failed'] += 1
            print(f"   ❌ FAILED: {result.get('error', 'Unknown error')}")
    
    # Summary
    print(f"\n{'='*70}")
    print(f"BATCH RESULTS SUMMARY")
    print(f"{'='*70}")
    print(f"Total Processed: {results['total']}")
    print(f"Successful: {results['success']} ({results['success']/results['total']*100:.1f}%)")
    print(f"  ✅ High Confidence (≥85%): {results['high_confidence']}")
    print(f"  ⚠️  Medium Confidence (65-85%): {results['medium_confidence']}")
    print(f"  ❌ Failed: {results['failed']}")
    print(f"\n🎯 Auto-Approval Rate: {results['high_confidence']/results['total']*100:.1f}%")
    print(f"{'='*70}\n")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Test single image: python test_smart_crop.py <image_path>")
        print("  Test folder: python test_smart_crop.py <folder_path>")
        print("\nExample:")
        print("  python test_smart_crop.py uploads/receipt_001.jpg")
        print("  python test_smart_crop.py uploads/")
        return
    
    path = sys.argv[1]
    
    if os.path.isfile(path):
        test_single_image(path)
    elif os.path.isdir(path):
        test_folder(path)
    else:
        print(f"❌ Error: Path not found: {path}")

if __name__ == "__main__":
    main()
