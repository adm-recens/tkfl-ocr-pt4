import os
import json
import shutil
import uuid
from datetime import datetime

class MLFeedbackService:
    """
    Service to collect and store user feedback for Machine Learning training.
    Captures feedback from two sources:
    1. Crop feedback: User-corrected crop coordinates for smart crop model
    2. Batch validation feedback: OCR corrections from batch processing
    3. Regular validation feedback: OCR corrections from /validate page
    """
    # Store dataset in the backend root/ml_dataset
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATASET_DIR = os.path.join(BASE_DIR, "ml_dataset")
    IMAGES_DIR = os.path.join(DATASET_DIR, "images")
    ANNOTATIONS_FILE = os.path.join(DATASET_DIR, "annotations.jsonl")
    
    # Feedback storage for ML model training
    FEEDBACK_DIR = os.path.join(DATASET_DIR, "feedback")
    BATCH_CORRECTIONS_FILE = os.path.join(FEEDBACK_DIR, "batch_corrections.jsonl")
    REGULAR_CORRECTIONS_FILE = os.path.join(FEEDBACK_DIR, "regular_corrections.jsonl")

    @classmethod
    def _ensure_dirs(cls):
        os.makedirs(cls.IMAGES_DIR, exist_ok=True)
        os.makedirs(cls.FEEDBACK_DIR, exist_ok=True)

    @classmethod
    def save_crop_feedback(cls, original_image_path: str, crop_data: dict, auto_crop_data: dict = None) -> bool:
        """
        Save the original image and the user's confirmed crop coordinates.
        CRITICAL: Also save auto-detected crop so we can learn the correction delta!
        
        Args:
            original_image_path: Path to the full raw image on disk
            crop_data: Dictionary containing x, y, width, height, rotate, scaleX, scaleY (USER'S CROP - the truth)
            auto_crop_data: Auto-detected crop from SmartReceiptDetector (OPTIONAL but IMPORTANT for learning!)
        """
        try:
            cls._ensure_dirs()
            
            if not os.path.exists(original_image_path):
                print(f"[ML-FEEDBACK] Error: Source image not found at {original_image_path}")
                return False

            # Generate unique ID for this training example
            example_id = str(uuid.uuid4())
            ext = os.path.splitext(original_image_path)[1]
            if not ext:
                ext = ".jpg"
                
            target_image_name = f"{example_id}{ext}"
            target_image_path = os.path.join(cls.IMAGES_DIR, target_image_name)

            # Copy original image (we want the FULL image to train the detector)
            shutil.copy2(original_image_path, target_image_path)
            
            # Create annotation record
            record = {
                "id": example_id,
                "timestamp": datetime.now().isoformat(),
                "original_filename": os.path.basename(original_image_path),
                "stored_image_name": target_image_name,
                "user_crop": crop_data,  # The 'truth' (label) - what user corrected to
                "auto_crop": auto_crop_data if auto_crop_data else {},  # What auto-detect found (for learning delta!)
                "metadata": {
                    "source": "user_correction",
                    "original_width": 0, # Could retrieve if needed
                    "original_height": 0,
                    "has_auto_crop": auto_crop_data is not None  # Track if we have delta data
                }
            }

            # Append to JSONL file
            with open(cls.ANNOTATIONS_FILE, "a") as f:
                f.write(json.dumps(record) + "\n")
                
            print(f"[ML-FEEDBACK] Saved training example {example_id} (auto_crop: {auto_crop_data is not None})")
            return True
            
        except Exception as e:
            print(f"[ML-FEEDBACK] Error saving feedback: {e}")
            return False

    @classmethod
    def save_batch_validation_feedback(cls, voucher_id: int, original_data: dict, corrected_data: dict, 
                                      raw_ocr_text: str, source_file: str) -> bool:
        """
        Save corrections from batch validation workflow for ML training.
        
        Args:
            voucher_id: ID of the saved voucher
            original_data: Original OCR parsed data (what system extracted)
            corrected_data: User-corrected data (what user validated)
            raw_ocr_text: Raw OCR text from the image
            source_file: Path to the source image file
        """
        try:
            cls._ensure_dirs()
            
            # Extract field-level corrections
            master_original = original_data.get('master', {})
            master_corrected = corrected_data.get('master', {})
            
            # Find differences
            corrections = {}
            for field in ['supplier_name', 'voucher_number', 'voucher_date', 'gross_total', 'net_total']:
                if field in master_original and field in master_corrected:
                    original_val = master_original.get(field)
                    corrected_val = master_corrected.get(field)
                    
                    # Only record if there's a difference
                    if original_val != corrected_val:
                        corrections[field] = {
                            'original': original_val,
                            'corrected': corrected_val
                        }
            
            # Check items corrections
            items_original = original_data.get('items', [])
            items_corrected = corrected_data.get('items', [])
            
            if len(items_original) != len(items_corrected):
                corrections['items_count'] = {
                    'original': len(items_original),
                    'corrected': len(items_corrected)
                }
            else:
                item_corrections = []
                for i, (orig_item, corr_item) in enumerate(zip(items_original, items_corrected)):
                    item_diff = {}
                    for field in ['item_name', 'quantity', 'unit_price', 'line_amount']:
                        if orig_item.get(field) != corr_item.get(field):
                            item_diff[field] = {
                                'original': orig_item.get(field),
                                'corrected': corr_item.get(field)
                            }
                    if item_diff:
                        item_corrections.append({'item_index': i, 'corrections': item_diff})
                
                if item_corrections:
                    corrections['items'] = item_corrections
            
            # Only save if there were actual corrections
            if not corrections:
                return True  # No corrections needed, not an error
            
            # Create feedback record
            record = {
                'id': str(uuid.uuid4()),
                'voucher_id': voucher_id,
                'timestamp': datetime.now().isoformat(),
                'source': 'batch_validation',
                'source_file': source_file,
                'raw_ocr_text': raw_ocr_text,
                'corrections': corrections,
                'original_data': original_data,
                'corrected_data': corrected_data
            }
            
            # Save to batch corrections file
            with open(cls.BATCH_CORRECTIONS_FILE, 'a') as f:
                f.write(json.dumps(record) + '\n')
            
            print(f"[ML-FEEDBACK] Batch validation feedback saved: voucher_id={voucher_id}, corrections={len(corrections)} fields")
            return True
            
        except Exception as e:
            print(f"[ML-FEEDBACK] Error saving batch validation feedback: {e}")
            return False

    @classmethod
    def save_regular_validation_feedback(cls, voucher_id: int, original_data: dict, corrected_data: dict,
                                         raw_ocr_text: str) -> bool:
        """
        Save corrections from regular /validate page workflow for ML training.
        
        Args:
            voucher_id: ID of the voucher being validated
            original_data: Original OCR parsed data
            corrected_data: User-corrected data
            raw_ocr_text: Raw OCR text
        """
        try:
            cls._ensure_dirs()
            
            # Extract field-level corrections (same logic as batch)
            master_original = original_data.get('master', {})
            master_corrected = corrected_data.get('master', {})
            
            corrections = {}
            for field in ['supplier_name', 'voucher_number', 'voucher_date', 'gross_total', 'net_total']:
                if field in master_original and field in master_corrected:
                    original_val = master_original.get(field)
                    corrected_val = master_corrected.get(field)
                    
                    if original_val != corrected_val:
                        corrections[field] = {
                            'original': original_val,
                            'corrected': corrected_val
                        }
            
            # Only save if there were corrections
            if not corrections:
                return True
            
            record = {
                'id': str(uuid.uuid4()),
                'voucher_id': voucher_id,
                'timestamp': datetime.now().isoformat(),
                'source': 'regular_validation',
                'raw_ocr_text': raw_ocr_text,
                'corrections': corrections,
                'original_data': original_data,
                'corrected_data': corrected_data
            }
            
            # Save to regular corrections file
            with open(cls.REGULAR_CORRECTIONS_FILE, 'a') as f:
                f.write(json.dumps(record) + '\n')
            
            print(f"[ML-FEEDBACK] Regular validation feedback saved: voucher_id={voucher_id}, corrections={len(corrections)} fields")
            return True
            
        except Exception as e:
            print(f"[ML-FEEDBACK] Error saving regular validation feedback: {e}")
            return False

    @classmethod
    def get_all_corrections(cls, limit: int = None) -> dict:
        """
        Get all corrections from both batch and regular validation sources.
        
        Returns:
            Dictionary with batch_corrections and regular_corrections lists
        """
        try:
            corrections = {
                'batch_corrections': [],
                'regular_corrections': [],
                'total': 0
            }
            
            # Read batch corrections
            if os.path.exists(cls.BATCH_CORRECTIONS_FILE):
                with open(cls.BATCH_CORRECTIONS_FILE, 'r') as f:
                    for line in f:
                        try:
                            record = json.loads(line)
                            corrections['batch_corrections'].append(record)
                        except:
                            pass
            
            # Read regular corrections
            if os.path.exists(cls.REGULAR_CORRECTIONS_FILE):
                with open(cls.REGULAR_CORRECTIONS_FILE, 'r') as f:
                    for line in f:
                        try:
                            record = json.loads(line)
                            corrections['regular_corrections'].append(record)
                        except:
                            pass
            
            # Apply limit if specified
            if limit:
                total_corrections = corrections['batch_corrections'] + corrections['regular_corrections']
                total_corrections = total_corrections[-limit:]  # Get last N
                corrections['batch_corrections'] = [c for c in total_corrections if c['source'] == 'batch_validation']
                corrections['regular_corrections'] = [c for c in total_corrections if c['source'] == 'regular_validation']
            
            corrections['total'] = len(corrections['batch_corrections']) + len(corrections['regular_corrections'])
            return corrections
            
        except Exception as e:
            print(f"[ML-FEEDBACK] Error getting corrections: {e}")
            return {'error': str(e)}

    @classmethod
    def get_dataset_stats(cls) -> dict:
        """
        Get statistics about the collected dataset
        """
        try:
            stats = {
                'total_images': 0,
                'total_annotations': 0,
                'batch_corrections': 0,
                'regular_corrections': 0,
                'total_corrections': 0,
                'last_updated': None
            }
            
            # Count images
            if os.path.exists(cls.IMAGES_DIR):
                stats['total_images'] = len([name for name in os.listdir(cls.IMAGES_DIR) 
                                           if os.path.isfile(os.path.join(cls.IMAGES_DIR, name))])
            
            # Count annotations
            if os.path.exists(cls.ANNOTATIONS_FILE):
                with open(cls.ANNOTATIONS_FILE, 'r') as f:
                    lines = f.readlines()
                    stats['total_annotations'] = len(lines)
                    if lines:
                        try:
                            last_record = json.loads(lines[-1])
                            stats['last_updated'] = last_record.get('timestamp')
                        except:
                            pass
            
            # Count batch corrections
            if os.path.exists(cls.BATCH_CORRECTIONS_FILE):
                with open(cls.BATCH_CORRECTIONS_FILE, 'r') as f:
                    stats['batch_corrections'] = len(f.readlines())
            
            # Count regular corrections
            if os.path.exists(cls.REGULAR_CORRECTIONS_FILE):
                with open(cls.REGULAR_CORRECTIONS_FILE, 'r') as f:
                    lines = f.readlines()
                    stats['regular_corrections'] = len(lines)
                    if lines:
                        try:
                            last_record = json.loads(lines[-1])
                            stats['last_updated'] = last_record.get('timestamp')
                        except:
                            pass
            
            stats['total_corrections'] = stats['batch_corrections'] + stats['regular_corrections']
            
            return stats
        except Exception as e:
            print(f"[ML-FEEDBACK] Error getting stats: {e}")
            return {'error': str(e)}
