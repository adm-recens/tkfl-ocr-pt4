"""
Robust OCR Integration Module
Provides easy integration of adaptive OCR and robust parser into existing workflow
"""

from typing import Dict, Optional
from backend.adaptive_ocr_service import extract_text_robust, QualityAwarePreprocessor
from backend.robust_parser import parse_receipt_text_robust
from backend.services.ml_training_service import MLTrainingService
import os


class RobustOCRPipeline:
    """
    Complete pipeline that integrates adaptive OCR with robust parsing
    Provides confidence-based processing and human-in-the-loop triggers
    """
    
    # Confidence thresholds for different actions
    AUTO_PROCESS_THRESHOLD = 80  # Automatically save if above this
    REVIEW_THRESHOLD = 50        # Flag for review if below this
    MIN_USABLE_THRESHOLD = 30    # Reject if below this
    
    def __init__(self):
        self.processing_stats = {
            'total_processed': 0,
            'auto_accepted': 0,
            'flagged_for_review': 0,
            'rejected': 0
        }
    
    def process_image(self, image_path: str, apply_ml_corrections: bool = True) -> Dict:
        """
        Process an image through the complete robust pipeline
        
        Returns:
            {
                'success': bool,
                'action': 'auto_accept' | 'review' | 'reject',
                'ocr_result': dict,
                'parsed_data': dict,
                'confidence': dict,
                'recommendations': list,
                'field_warnings': dict
            }
        """
        print(f"[ROBUST-PIPELINE] Processing: {os.path.basename(image_path)}")
        
        # Step 1: Adaptive OCR
        ocr_result = extract_text_robust(image_path)
        
        # Step 2: Apply ML corrections if enabled
        if apply_ml_corrections:
            try:
                ocr_result = self._apply_ml_to_ocr(ocr_result)
            except Exception as e:
                print(f"[ROBUST-PIPELINE] ML correction failed: {e}")
        
        # Step 3: Robust parsing
        parsed_data = parse_receipt_text_robust(
            ocr_result['text'], 
            field_confidence=ocr_result.get('field_confidence', {})
        )
        
        # Step 4: Apply ML corrections to parsed data
        if apply_ml_corrections:
            try:
                parsed_data = MLTrainingService.apply_learned_corrections(
                    parsed_data, 
                    ocr_result['text']
                )
            except Exception as e:
                print(f"[ROBUST-PIPELINE] ML parsing correction failed: {e}")
        
        # Step 5: Determine action based on confidence
        action, recommendations, warnings = self._determine_action(
            ocr_result, parsed_data
        )
        
        self.processing_stats['total_processed'] += 1
        if action == 'auto_accept':
            self.processing_stats['auto_accepted'] += 1
        elif action == 'review':
            self.processing_stats['flagged_for_review'] += 1
        else:
            self.processing_stats['rejected'] += 1
        
        return {
            'success': action != 'reject',
            'action': action,
            'ocr_result': ocr_result,
            'parsed_data': parsed_data,
            'confidence': {
                'ocr': ocr_result['confidence'],
                'parsing': parsed_data.get('confidence', {}).get('overall', 50),
                'fields': self._merge_field_confidence(
                    ocr_result.get('field_confidence', {}),
                    parsed_data.get('confidence', {})
                )
            },
            'recommendations': recommendations,
            'field_warnings': warnings
        }
    
    def _apply_ml_to_ocr(self, ocr_result: Dict) -> Dict:
        """Apply ML text corrections to OCR result"""
        # Load OCR correction model
        from backend.ml_models.ml_correction_model import OCRCorrectionModel
        
        model = OCRCorrectionModel()
        if model.load_model():
            corrected_text = ocr_result['text']
            
            # Try to apply corrections line by line
            lines = corrected_text.split('\n')
            corrected_lines = []
            
            for line in lines:
                suggestion = model.get_correction_suggestion(line)
                if suggestion.get('suggestion') and suggestion.get('confidence', 0) > 0.7:
                    corrected_lines.append(suggestion['suggestion'])
                else:
                    corrected_lines.append(line)
            
            ocr_result['text'] = '\n'.join(corrected_lines)
            ocr_result['ml_corrected'] = True
        
        return ocr_result
    
    def _determine_action(self, ocr_result: Dict, parsed_data: Dict) -> tuple:
        """
        Determine processing action based on confidence scores
        Returns: (action, recommendations, warnings)
        """
        ocr_conf = ocr_result['confidence']
        parse_conf = parsed_data.get('confidence', {}).get('overall', 50)
        field_conf = parsed_data.get('confidence', {})
        
        recommendations = []
        warnings = {}
        
        # Check critical fields
        critical_fields = ['voucher_number', 'voucher_date', 'net_total']
        for field in critical_fields:
            conf = field_conf.get(field, 0)
            if conf < self.REVIEW_THRESHOLD:
                warnings[field] = f'Low confidence ({conf:.0f}%) - please verify'
                recommendations.append(f'Review and correct {field.replace("_", " ")}')
        
        # Overall decision
        if ocr_conf < self.MIN_USABLE_THRESHOLD or parse_conf < self.MIN_USABLE_THRESHOLD:
            action = 'reject'
            recommendations.insert(0, 'Image quality too poor - consider retaking photo')
        elif ocr_conf >= self.AUTO_PROCESS_THRESHOLD and parse_conf >= self.AUTO_PROCESS_THRESHOLD and not warnings:
            action = 'auto_accept'
        else:
            action = 'review'
            if not recommendations:
                recommendations.append('Please review extracted data for accuracy')
        
        # Add quality-based recommendations
        if ocr_conf < 60:
            recommendations.append('Consider using better lighting for future scans')
        
        return action, recommendations, warnings
    
    def _merge_field_confidence(self, ocr_conf: Dict, parse_conf: Dict) -> Dict:
        """Merge OCR and parsing confidence scores"""
        merged = {}
        all_fields = set(ocr_conf.keys()) | set(parse_conf.keys())
        
        for field in all_fields:
            ocr_score = ocr_conf.get(field, 50)
            parse_score = parse_conf.get(field, 50)
            # Weight parsing confidence higher
            merged[field] = (ocr_score * 0.3) + (parse_score * 0.7)
        
        return merged
    
    def get_stats(self) -> Dict:
        """Get processing statistics"""
        total = self.processing_stats['total_processed']
        if total == 0:
            return self.processing_stats
        
        return {
            **self.processing_stats,
            'auto_accept_rate': (self.processing_stats['auto_accepted'] / total) * 100,
            'review_rate': (self.processing_stats['flagged_for_review'] / total) * 100,
            'rejection_rate': (self.processing_stats['rejected'] / total) * 100
        }


def process_voucher_robust(image_path: str, skip_ml: bool = False) -> Dict:
    """
    Convenience function for processing a voucher with robust pipeline
    Use this instead of the standard process for poor quality images
    
    Args:
        image_path: Path to the voucher image
        skip_ml: Set to True to skip ML corrections (faster but less accurate)
        
    Returns:
        Processing result with action recommendation
    """
    pipeline = RobustOCRPipeline()
    return pipeline.process_image(image_path, apply_ml_corrections=not skip_ml)


# Integration helper for API routes
def integrate_with_api(original_api_func):
    """
    Decorator to integrate robust OCR into existing API endpoints
    
    Usage:
        @integrate_with_api
        def upload_file():
            # original upload code
    """
    def wrapper(*args, **kwargs):
        # Check if robust processing is requested
        from flask import request
        use_robust = request.args.get('robust', 'false').lower() == 'true'
        
        if use_robust:
            # Use robust pipeline
            pass  # Implementation depends on specific API
        
        # Call original function
        return original_api_func(*args, **kwargs)
    
    return wrapper


# Preprocessing helper for batch operations
def preprocess_batch_images(image_paths: List[str]) -> List[str]:
    """
    Preprocess a batch of images for better OCR results
    Returns list of preprocessed image paths
    """
    preprocessed_paths = []
    
    for path in image_paths:
        try:
            preprocessed_path = QualityAwarePreprocessor.preprocess_for_quality(path)
            preprocessed_paths.append(preprocessed_path)
        except Exception as e:
            print(f"[BATCH-PREPROCESS] Failed to preprocess {path}: {e}")
            preprocessed_paths.append(path)  # Use original on failure
    
    return preprocessed_paths


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        print(f"\nTesting Robust Pipeline on: {image_path}\n")
        
        result = process_voucher_robust(image_path)
        
        print("\n" + "="*60)
        print("PROCESSING RESULT")
        print("="*60)
        print(f"Success: {result['success']}")
        print(f"Action: {result['action']}")
        print(f"\nOCR Confidence: {result['confidence']['ocr']:.1f}%")
        print(f"Parsing Confidence: {result['confidence']['parsing']:.1f}%")
        
        print("\nExtracted Data:")
        for key, value in result['parsed_data']['master'].items():
            print(f"  {key}: {value}")
        
        if result['recommendations']:
            print("\nRecommendations:")
            for rec in result['recommendations']:
                print(f"  - {rec}")
        
        if result['field_warnings']:
            print("\nWarnings:")
            for field, warning in result['field_warnings'].items():
                print(f"  {field}: {warning}")
        
        print("\n" + "="*60)
    else:
        print("Usage: python robust_ocr_integration.py <image_path>")
