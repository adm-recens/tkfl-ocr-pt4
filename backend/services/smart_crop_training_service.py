"""
Smart Crop Model Training Service
Trains crop detection models from user-corrected crop boundaries
"""

import os
import json
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from backend.services.ml_feedback_service import MLFeedbackService


class SmartCropTrainingService:
    """
    Service to train smart crop detection models from user feedback.
    
    Core idea: Learn the DIFFERENCE between auto-detected and user-corrected crops
    Then apply those learned corrections to future auto-detections.
    
    Example:
    - Auto-detect finds crop at (50, 100, 300, 700)
    - User corrects it to (35, 110, 320, 710) 
    - System learns: delta = (-15, +10, +20, +10)
    - Next similar receipt: auto-detect (48, 98, 305, 695) 
    - Apply learned delta: (48-15, 98+10, 305+20, 695+10) = (33, 108, 325, 705)
    """
    
    # Model storage
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    MODELS_DIR = os.path.join(BASE_DIR, "ml_models")
    SMART_CROP_MODEL = os.path.join(MODELS_DIR, "smart_crop_model.json")
    
    @classmethod
    def collect_crop_training_data(cls, limit: int = None) -> Dict:
        """
        Collect user-corrected crop data with AUTO-DETECTED crops for learning deltas.
        
        CRITICAL: We need BOTH auto-detected and user-corrected crops to learn corrections!
        
        Returns:
            {
                'training_examples': [
                    {
                        'image_id': str,
                        'auto_crop': [x, y, w, h],      # What auto-detect suggested
                        'user_crop': [x, y, w, h],      # What user corrected to
                        'delta': {
                            'x_delta': int,
                            'y_delta': int,
                            'w_delta': int,
                            'h_delta': int,
                        },
                        'delta_magnitude': float        # Total pixels adjusted
                    },
                    ...
                ],
                'total_examples': int,
                'avg_x_delta': float,
                'avg_y_delta': float,
                'avg_w_delta': float,
                'avg_h_delta': float
            }
        """
        try:
            # Get crop annotations from ML feedback
            stats = MLFeedbackService.get_dataset_stats()
            annotations_count = stats.get('total_annotations', 0)
            
            if annotations_count == 0:
                return {
                    'training_examples': [],
                    'total_examples': 0,
                    'message': 'No crop data collected yet - need both auto AND user crops'
                }
            
            # Read crop feedback from annotations file
            annotations_file = MLFeedbackService.ANNOTATIONS_FILE
            training_examples = []
            
            if os.path.exists(annotations_file):
                with open(annotations_file, 'r') as f:
                    for line in f:
                        try:
                            record = json.loads(line)
                            
                            # CRITICAL: Need BOTH auto-detected and user crops!
                            auto_crop = record.get('auto_crop', {})
                            user_crop = record.get('user_crop', {})
                            
                            # Skip if missing auto-detected crop (can't learn delta!)
                            if not auto_crop or not user_crop:
                                continue
                            
                            # Extract crop coordinates
                            auto_x = auto_crop.get('x', 0)
                            auto_y = auto_crop.get('y', 0)
                            auto_w = auto_crop.get('width', 0)
                            auto_h = auto_crop.get('height', 0)
                            
                            user_x = user_crop.get('x', 0)
                            user_y = user_crop.get('y', 0)
                            user_w = user_crop.get('width', 0)
                            user_h = user_crop.get('height', 0)
                            
                            # Calculate delta (correction)
                            delta_x = user_x - auto_x
                            delta_y = user_y - auto_y
                            delta_w = user_w - auto_w
                            delta_h = user_h - auto_h
                            
                            delta_magnitude = abs(delta_x) + abs(delta_y) + abs(delta_w) + abs(delta_h)
                            
                            example = {
                                'image_id': record.get('id'),
                                'auto_crop': {
                                    'x': auto_x,
                                    'y': auto_y,
                                    'width': auto_w,
                                    'height': auto_h
                                },
                                'user_crop': {
                                    'x': user_x,
                                    'y': user_y,
                                    'width': user_w,
                                    'height': user_h
                                },
                                'delta': {
                                    'x_delta': delta_x,
                                    'y_delta': delta_y,
                                    'w_delta': delta_w,
                                    'h_delta': delta_h
                                },
                                'delta_magnitude': delta_magnitude,
                                'timestamp': record.get('timestamp')
                            }
                            
                            training_examples.append(example)
                            
                            if limit and len(training_examples) >= limit:
                                break
                        
                        except Exception as e:
                            print(f"[SMART-CROP-TRAINING] Error parsing annotation: {e}")
                            continue
            
            # Calculate average deltas
            if training_examples:
                avg_x_delta = np.mean([ex['delta']['x_delta'] for ex in training_examples])
                avg_y_delta = np.mean([ex['delta']['y_delta'] for ex in training_examples])
                avg_w_delta = np.mean([ex['delta']['w_delta'] for ex in training_examples])
                avg_h_delta = np.mean([ex['delta']['h_delta'] for ex in training_examples])
            else:
                avg_x_delta = avg_y_delta = avg_w_delta = avg_h_delta = 0
            
            return {
                'training_examples': training_examples,
                'total_examples': len(training_examples),
                'avg_x_delta': float(avg_x_delta),
                'avg_y_delta': float(avg_y_delta),
                'avg_w_delta': float(avg_w_delta),
                'avg_h_delta': float(avg_h_delta),
                'message': f'Collected {len(training_examples)} crop training examples with deltas'
            }
            
        except Exception as e:
            print(f"[SMART-CROP-TRAINING] Error collecting training data: {e}")
            return {
                'training_examples': [],
                'total_examples': 0,
                'error': str(e)
            }
    
    @staticmethod
    def _calculate_avg_correction(examples: List[Dict]) -> float:
        """
        Calculate average magnitude of user corrections
        (how much the user typically adjusts auto-detected crops)
        """
        if not examples:
            return 0.0
        
        total_magnitude = 0
        for example in examples:
            crop = example.get('user_crop', {})
            # Simple magnitude: sum of absolute coordinate values
            magnitude = (
                abs(crop.get('x', 0)) +
                abs(crop.get('y', 0)) +
                abs(crop.get('width', 0)) +
                abs(crop.get('height', 0))
            )
            total_magnitude += magnitude
        
        return total_magnitude / len(examples) if examples else 0.0
    
    @classmethod
    def train_smart_crop_model(cls, data_limit: int = 1000) -> Dict:
        """
        Train smart crop model from collected crop feedback.
        
        Returns:
            {
                'status': 'success' | 'failed',
                'message': str,
                'model_stats': {
                    'training_samples': int,
                    'model_name': str,
                    'location': str,
                    'patterns_learned': int,
                    'avg_crop_size': Dict,
                    'crop_variations': Dict
                },
                'training_time': float,
                'timestamp': str
            }
        """
        try:
            import time
            start_time = time.time()
            
            # Collect training data
            training_data = cls.collect_crop_training_data(limit=data_limit)
            examples = training_data.get('training_examples', [])
            
            if not examples:
                return {
                    'status': 'failed',
                    'message': 'No training data available',
                    'training_time': time.time() - start_time
                }
            
            # Extract patterns from crop data
            model_data = cls._extract_crop_patterns(examples)
            
            # Save model
            os.makedirs(cls.MODELS_DIR, exist_ok=True)
            with open(cls.SMART_CROP_MODEL, 'w') as f:
                json.dump(model_data, f, indent=2, default=str)
            
            training_time = time.time() - start_time
            
            return {
                'status': 'success',
                'message': 'Smart crop model trained successfully',
                'model_stats': {
                    'training_samples': len(examples),
                    'model_name': 'SmartCropModel',
                    'location': cls.SMART_CROP_MODEL,
                    'patterns_learned': len(model_data.get('patterns', [])),
                    'avg_crop_size': model_data.get('avg_crop_size', {}),
                    'crop_variations': model_data.get('crop_variations', {})
                },
                'training_time': training_time,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"[SMART-CROP-TRAINING] Training failed: {e}")
            return {
                'status': 'failed',
                'message': str(e),
                'training_time': 0
            }
    
    @staticmethod
    def _extract_crop_patterns(examples: List[Dict]) -> Dict:
        """
        Extract learned correction patterns from crop deltas.
        
        Instead of learning just statistics, learn the CORRECTIONS:
        - How much X typically needs adjustment
        - How much Y typically needs adjustment
        - How much Width needs adjustment
        - How much Height needs adjustment
        
        This is the KEY to smart crop learning!
        """
        if not examples:
            return {}
        
        # Extract deltas (the corrections users make)
        deltas_x = [ex['delta']['x_delta'] for ex in examples]
        deltas_y = [ex['delta']['y_delta'] for ex in examples]
        deltas_w = [ex['delta']['w_delta'] for ex in examples]
        deltas_h = [ex['delta']['h_delta'] for ex in examples]
        
        # Calculate statistics on the deltas
        mean_x = float(np.mean(deltas_x))
        mean_y = float(np.mean(deltas_y))
        mean_w = float(np.mean(deltas_w))
        mean_h = float(np.mean(deltas_h))
        
        std_x = float(np.std(deltas_x))
        std_y = float(np.std(deltas_y))
        std_w = float(np.std(deltas_w))
        std_h = float(np.std(deltas_h))
        
        # Also extract the actual crop sizes for reference
        crops_user = [ex['user_crop'] for ex in examples]
        widths = [c.get('width', 0) for c in crops_user]
        heights = [c.get('height', 0) for c in crops_user]
        xs = [c.get('x', 0) for c in crops_user]
        ys = [c.get('y', 0) for c in crops_user]
        
        avg_width = np.mean(widths) if widths else 0
        avg_height = np.mean(heights) if heights else 0
        avg_x = np.mean(xs) if xs else 0
        avg_y = np.mean(ys) if ys else 0
        
        return {
            'version': '2.0',  # Version 2: Learns deltas not just statistics
            'trained_at': datetime.now().isoformat(),
            'total_examples': len(examples),
            'patterns': [
                {
                    'pattern_type': 'correction_deltas',
                    'description': 'Learned corrections to apply to auto-detected crops',
                    'mean_x_delta': mean_x,
                    'mean_y_delta': mean_y,
                    'mean_w_delta': mean_w,
                    'mean_h_delta': mean_h,
                    'std_x_delta': std_x,
                    'std_y_delta': std_y,
                    'std_w_delta': std_w,
                    'std_h_delta': std_h,
                    'note': f'Apply these deltas to auto-detected crops: x+{mean_x:.0f}, y+{mean_y:.0f}, w+{mean_w:.0f}, h+{mean_h:.0f}'
                },
                {
                    'pattern_type': 'expected_crop_size',
                    'avg_width': float(avg_width),
                    'avg_height': float(avg_height),
                    'avg_x': float(avg_x),
                    'avg_y': float(avg_y),
                    'width_std': float(np.std(widths)) if widths else 0,
                    'height_std': float(np.std(heights)) if heights else 0,
                    'aspect_ratio': float(avg_width / avg_height) if avg_height > 0 else 0
                }
            ],
            'learned_corrections': {
                'x_adjustment': round(mean_x),
                'y_adjustment': round(mean_y),
                'width_adjustment': round(mean_w),
                'height_adjustment': round(mean_h)
            },
            'avg_crop_size': {
                'width': float(avg_width),
                'height': float(avg_height),
                'aspect_ratio': float(avg_width / avg_height) if avg_height > 0 else 0
            },
            'crop_variations': {
                'width_std': float(np.std(widths)) if widths else 0,
                'height_std': float(np.std(heights)) if heights else 0,
                'x_delta_std': std_x,
                'y_delta_std': std_y,
                'w_delta_std': std_w,
                'h_delta_std': std_h
            }
        }
    
    @classmethod
    def get_training_status(cls) -> Dict:
        """
        Get status of smart crop model training
        
        Returns:
            {
                'model_available': bool,
                'model_path': str,
                'trained_at': str,
                'training_samples': int,
                'patterns': List,
                'last_training_info': Dict
            }
        """
        try:
            if not os.path.exists(cls.SMART_CROP_MODEL):
                return {
                    'model_available': False,
                    'model_path': cls.SMART_CROP_MODEL,
                    'message': 'No trained model yet'
                }
            
            with open(cls.SMART_CROP_MODEL, 'r') as f:
                model_data = json.load(f)
            
            return {
                'model_available': True,
                'model_path': cls.SMART_CROP_MODEL,
                'trained_at': model_data.get('trained_at'),
                'training_samples': model_data.get('total_examples', 0),
                'patterns_count': len(model_data.get('patterns', [])),
                'avg_crop_size': model_data.get('avg_crop_size', {}),
                'crop_variations': model_data.get('crop_variations', {})
            }
        
        except Exception as e:
            print(f"[SMART-CROP-TRAINING] Error getting status: {e}")
            return {
                'model_available': False,
                'error': str(e)
            }
    
    @classmethod
    def load_model(cls) -> Optional[Dict]:
        """
        Load trained smart crop model
        
        Returns:
            Model data dict or None if not available
        """
        try:
            if os.path.exists(cls.SMART_CROP_MODEL):
                with open(cls.SMART_CROP_MODEL, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"[SMART-CROP-TRAINING] Error loading model: {e}")
        
        return None
    
    @classmethod
    def apply_learned_corrections_to_auto_detect(cls, auto_crop: Dict) -> Dict:
        """
        **CRITICAL METHOD**: Apply learned correction deltas to auto-detected crops.
        
        This is what makes smart crop actually LEARN and improve!
        
        Args:
            auto_crop: {x, y, width, height} from auto-detection
        
        Returns:
            {
                'corrected_crop': {x, y, width, height},
                'applied_corrections': {x, y, width, height},
                'confidence': float,
                'improved': bool
            }
        """
        model = cls.load_model()
        
        if not model or model.get('version', '1.0') == '1.0':
            # Old model version or no model - return unchanged
            return {
                'corrected_crop': auto_crop,
                'applied_corrections': {'x': 0, 'y': 0, 'width': 0, 'height': 0},
                'confidence': 0.0,
                'improved': False,
                'reason': 'No trained correction model available'
            }
        
        try:
            corrections = model.get('learned_corrections', {})
            
            # Extract learned deltas
            x_adj = corrections.get('x_adjustment', 0)
            y_adj = corrections.get('y_adjustment', 0)
            w_adj = corrections.get('width_adjustment', 0)
            h_adj = corrections.get('height_adjustment', 0)
            
            # Skip if no meaningful corrections learned
            if x_adj == 0 and y_adj == 0 and w_adj == 0 and h_adj == 0:
                return {
                    'corrected_crop': auto_crop,
                    'applied_corrections': {'x': 0, 'y': 0, 'width': 0, 'height': 0},
                    'confidence': 0.0,
                    'improved': False,
                    'reason': 'No corrections learned yet'
                }
            
            # Apply corrections to auto-detected crop
            corrected = {
                'x': max(0, auto_crop.get('x', 0) + x_adj),  # Don't go negative
                'y': max(0, auto_crop.get('y', 0) + y_adj),
                'width': max(10, auto_crop.get('width', 0) + w_adj),  # Minimum size
                'height': max(10, auto_crop.get('height', 0) + h_adj)
            }
            
            # Calculate confidence based on:
            # 1. Number of training samples
            # 2. Consistency of corrections (low std dev = more consistent)
            samples = model.get('total_examples', 0)
            variations = model.get('crop_variations', {})
            
            # More samples = higher confidence
            confidence_from_samples = min(0.95, samples / 50.0) if samples > 0 else 0.0
            
            # Low variation = more confidence
            total_std = (abs(variations.get('x_delta_std', 0)) + 
                        abs(variations.get('y_delta_std', 0)) +
                        abs(variations.get('w_delta_std', 0)) +
                        abs(variations.get('h_delta_std', 0)))
            
            # If std dev is low, corrections are consistent (good!)
            confidence_from_consistency = 1.0 - min(0.5, total_std / 100.0)
            
            final_confidence = (confidence_from_samples * 0.6) + (confidence_from_consistency * 0.4)
            
            return {
                'corrected_crop': corrected,
                'applied_corrections': {
                    'x': x_adj,
                    'y': y_adj,
                    'width': w_adj,
                    'height': h_adj
                },
                'confidence': min(0.95, final_confidence),
                'improved': True,
                'training_samples': samples,
                'applied_corrections_summary': f'Applied delta: x{x_adj:+d}, y{y_adj:+d}, w{w_adj:+d}, h{h_adj:+d}'
            }
        
        except Exception as e:
            print(f"[SMART-CROP-TRAINING] Error applying corrections: {e}")
            return {
                'corrected_crop': auto_crop,
                'applied_corrections': {'x': 0, 'y': 0, 'width': 0, 'height': 0},
                'confidence': 0.0,
                'improved': False,
                'error': str(e)
            }
    
    @classmethod
    def apply_learned_crop_suggestions(cls, image_shape: Tuple[int, int], 
                                      auto_detected_crop: Dict) -> Dict:
        """
        Apply learned patterns to suggest crop improvements.
        
        Args:
            image_shape: (height, width) of the image
            auto_detected_crop: Auto-detected crop from SmartReceiptDetector
        
        Returns:
            {
                'original_crop': Dict,
                'suggested_crop': Dict,
                'confidence': float,
                'adjustments': List
            }
        """
        model = cls.load_model()
        
        if not model:
            return {
                'original_crop': auto_detected_crop,
                'suggested_crop': auto_detected_crop,
                'confidence': 0.0,
                'message': 'No trained model available'
            }
        
        try:
            suggested = auto_detected_crop.copy()
            adjustments = []
            
            avg_size = model.get('avg_crop_size', {})
            avg_width = avg_size.get('width', 0)
            avg_height = avg_size.get('height', 0)
            
            # If learned crop is significantly different, suggest adjustment
            if avg_width > 0 and abs(auto_detected_crop.get('w', 0) - avg_width) > avg_width * 0.1:
                suggested['w'] = int(avg_width)
                adjustments.append(f"Width adjusted from {auto_detected_crop.get('w')} to {int(avg_width)}")
            
            if avg_height > 0 and abs(auto_detected_crop.get('h', 0) - avg_height) > avg_height * 0.1:
                suggested['h'] = int(avg_height)
                adjustments.append(f"Height adjusted from {auto_detected_crop.get('h')} to {int(avg_height)}")
            
            confidence = min(0.9, model.get('total_examples', 0) / 100.0)  # More examples = higher confidence
            
            return {
                'original_crop': auto_detected_crop,
                'suggested_crop': suggested,
                'confidence': confidence,
                'adjustments': adjustments,
                'training_samples_used': model.get('total_examples', 0)
            }
        
        except Exception as e:
            print(f"[SMART-CROP-TRAINING] Error applying suggestions: {e}")
            return {
                'original_crop': auto_detected_crop,
                'suggested_crop': auto_detected_crop,
                'confidence': 0.0,
                'error': str(e)
            }
