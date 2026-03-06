"""
Enhanced ML Training Service with Continuous Learning
Integrates continuous learning capabilities with the existing ML infrastructure
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

from backend.db import get_connection
from backend.ml_models.ml_correction_model import OCRCorrectionModel, ParsingCorrectionModel
from backend.ml_models.continuous_learning_model import ContinuousLearningModel, get_enhanced_model
from backend.services.ml_feedback_service import MLFeedbackService
from backend.services.smart_crop_training_service import SmartCropTrainingService
from backend.services.learning_history_tracker import LearningHistoryTracker

# Initialize ML logger
ml_logger = logging.getLogger('ml')


class EnhancedMLTrainingService:
    """
    Enhanced ML Training Service with continuous learning capabilities
    """
    
    @staticmethod
    def train_with_continuous_learning(feedback_limit: int = 5000, 
                                       save_models: bool = True,
                                       include_smart_crop: bool = True) -> Dict[str, Any]:
        """
        Train all models with continuous learning capabilities
        
        Returns:
            {
                'status': 'success'|'error',
                'models_trained': {
                    'ocr': {...},
                    'parsing': {...},
                    'continuous': {...},
                    'smart_crop': {...}
                },
                'performance_metrics': {...},
                'new_patterns_learned': int,
                'training_time': float
            }
        """
        import time
        start_time = time.time()
        
        result = {
            'status': 'success',
            'models_trained': {},
            'performance_metrics': {},
            'new_patterns_learned': 0,
            'training_time': 0
        }
        
        try:
            # 1. Train traditional models
            traditional_result = EnhancedMLTrainingService._train_traditional_models(
                feedback_limit, save_models
            )
            result['models_trained']['ocr'] = traditional_result.get('ocr', {})
            result['models_trained']['parsing'] = traditional_result.get('parsing', {})
            
            # 2. Train continuous learning model
            continuous_result = EnhancedMLTrainingService._train_continuous_model(
                feedback_limit, save_models
            )
            result['models_trained']['continuous'] = continuous_result
            result['new_patterns_learned'] = continuous_result.get('patterns_learned', 0)
            
            # 3. Train smart crop if requested
            if include_smart_crop:
                try:
                    crop_result = SmartCropTrainingService.train_smart_crop_model(
                        data_limit=feedback_limit
                    )
                    result['models_trained']['smart_crop'] = crop_result
                except Exception as e:
                    ml_logger.error(f"[EnhancedML] Smart crop training failed: {e}")
                    result['models_trained']['smart_crop'] = {'error': str(e)}
            
            # 4. Get performance metrics from continuous learning model
            enhanced_model = get_enhanced_model()
            result['performance_metrics'] = enhanced_model.get_performance_metrics()
            
            # 5. Record training session
            LearningHistoryTracker.record_training_session(
                corrections_used=continuous_result.get('corrections', []),
                training_results=result
            )
            
            result['training_time'] = time.time() - start_time
            
        except Exception as e:
            ml_logger.error(f"[EnhancedML] Training failed: {e}")
            result['status'] = 'error'
            result['error'] = str(e)
            result['training_time'] = time.time() - start_time
        
        return result
    
    @staticmethod
    def _train_traditional_models(feedback_limit: int, save_models: bool) -> Dict[str, Any]:
        """Train traditional OCR and Parsing models"""
        try:
            # Import and use existing MLTrainingService
            from backend.services.ml_training_service import MLTrainingService
            
            result = MLTrainingService._train_correction_models(feedback_limit, save_models)
            
            return {
                'ocr': result.get('ocr_model_stats', {}),
                'parsing': result.get('parsing_model_stats', {}),
                'status': result.get('status', 'unknown')
            }
        except Exception as e:
            ml_logger.error(f"[EnhancedML] Traditional model training failed: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def _train_continuous_model(feedback_limit: int, save_models: bool) -> Dict[str, Any]:
        """Train the continuous learning model"""
        try:
            # Collect training data
            training_data = EnhancedMLTrainingService._collect_comprehensive_training_data(
                feedback_limit
            )
            
            # Get enhanced model
            model = get_enhanced_model()
            
            patterns_learned = 0
            corrections_processed = []
            
            # Train on parsing corrections
            for correction in training_data.get('parsing_corrections', []):
                success = model.learn_from_correction(
                    field_name=correction.get('field'),
                    raw_ocr=correction.get('raw_ocr', ''),
                    auto_extracted=correction.get('auto'),
                    user_corrected=correction.get('corrected'),
                    supplier_name=correction.get('supplier_name'),
                    confidence=1.0  # User-validated
                )
                
                if success:
                    patterns_learned += 1
                    corrections_processed.append(correction)
            
            # Save model if requested
            if save_models:
                model.save_model()
            
            # Cleanup old patterns
            cleaned = model.cleanup_old_patterns(days=90)
            
            return {
                'status': 'success',
                'patterns_learned': patterns_learned,
                'patterns_cleaned': cleaned,
                'total_patterns': len(model.patterns),
                'corrections': corrections_processed,
                'stats': model.stats
            }
            
        except Exception as e:
            ml_logger.error(f"[EnhancedML] Continuous model training failed: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def _collect_comprehensive_training_data(limit: int = 5000) -> Dict[str, Any]:
        """Collect training data from all sources"""
        training_data = {
            'parsing_corrections': [],
            'source_breakdown': {
                'database': 0,
                'batch_feedback': 0,
                'regular_feedback': 0
            }
        }
        
        # Source 1: Database validated vouchers
        try:
            conn = get_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT 
                    id,
                    raw_ocr_text,
                    parsed_json_original,
                    parsed_json,
                    supplier_name as user_supplier
                FROM vouchers_master
                WHERE validation_status = 'VALIDATED' AND parsed_json_original IS NOT NULL
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            
            vouchers = cur.fetchall()
            
            for voucher in vouchers:
                raw_ocr = voucher['raw_ocr_text'] or ''
                
                try:
                    original = json.loads(voucher['parsed_json_original']) if isinstance(
                        voucher['parsed_json_original'], str) else voucher['parsed_json_original']
                    corrected = json.loads(voucher['parsed_json']) if isinstance(
                        voucher['parsed_json'], str) else voucher['parsed_json']
                except:
                    continue
                
                original_master = original.get('master', {})
                corrected_master = corrected.get('master', {})
                
                # Compare and collect corrections
                for field in ['supplier_name', 'voucher_date', 'voucher_number', 
                             'gross_total', 'net_total']:
                    if original_master.get(field) != corrected_master.get(field):
                        training_data['parsing_corrections'].append({
                            'field': field,
                            'raw_ocr': raw_ocr,
                            'auto': original_master.get(field),
                            'corrected': corrected_master.get(field),
                            'supplier_name': corrected_master.get('supplier_name'),
                            'source': 'database'
                        })
                        training_data['source_breakdown']['database'] += 1
                
                # Handle deductions
                original_deds = original.get('deductions', [])
                corrected_deds = corrected.get('deductions', [])
                
                if len(original_deds) != len(corrected_deds):
                    for ded in corrected_deds:
                        training_data['parsing_corrections'].append({
                            'field': f"deduction_{ded.get('deduction_type')}",
                            'raw_ocr': raw_ocr,
                            'auto': '',
                            'corrected': str(ded.get('amount')),
                            'supplier_name': corrected_master.get('supplier_name'),
                            'source': 'database'
                        })
                        training_data['source_breakdown']['database'] += 1
                
                # Handle line items
                original_items = original.get('items', [])
                corrected_items = corrected.get('items', [])
                
                for i, item in enumerate(corrected_items):
                    if i < len(original_items):
                        orig_item = original_items[i]
                        for field in ['item_name', 'quantity', 'unit_price', 'line_amount']:
                            if orig_item.get(field) != item.get(field):
                                training_data['parsing_corrections'].append({
                                    'field': f"item_{field}",
                                    'raw_ocr': raw_ocr,
                                    'auto': orig_item.get(field),
                                    'corrected': item.get(field),
                                    'supplier_name': corrected_master.get('supplier_name'),
                                    'source': 'database'
                                })
                                training_data['source_breakdown']['database'] += 1
            
            conn.close()
            
        except Exception as e:
            ml_logger.error(f"[EnhancedML] Error collecting database data: {e}")
        
        # Source 2 & 3: Feedback data
        try:
            feedback_data = MLFeedbackService.get_all_corrections(limit=limit)
            
            for correction in feedback_data.get('batch_corrections', []):
                corrections_dict = correction.get('corrections', {})
                raw_ocr = correction.get('raw_ocr_text', '')
                
                for field, change in corrections_dict.items():
                    if isinstance(change, dict) and 'original' in change and 'corrected' in change:
                        training_data['parsing_corrections'].append({
                            'field': field,
                            'raw_ocr': raw_ocr,
                            'auto': change['original'],
                            'corrected': change['corrected'],
                            'source': 'batch_feedback'
                        })
                        training_data['source_breakdown']['batch_feedback'] += 1
            
            for correction in feedback_data.get('regular_corrections', []):
                corrections_dict = correction.get('corrections', {})
                raw_ocr = correction.get('raw_ocr_text', '')
                
                for field, change in corrections_dict.items():
                    if isinstance(change, dict) and 'original' in change and 'corrected' in change:
                        training_data['parsing_corrections'].append({
                            'field': field,
                            'raw_ocr': raw_ocr,
                            'auto': change['original'],
                            'corrected': change['corrected'],
                            'source': 'regular_feedback'
                        })
                        training_data['source_breakdown']['regular_feedback'] += 1
        
        except Exception as e:
            ml_logger.error(f"[EnhancedML] Error collecting feedback data: {e}")
        
        return training_data
    
    @staticmethod
    def apply_enhanced_corrections(auto_extracted_data: dict, raw_ocr: str) -> Dict[str, Any]:
        """
        Apply corrections using both traditional and continuous learning models
        
        Returns:
            {
                'corrected_data': dict,
                'suggestions': {
                    'field_name': {
                        'suggestion': str,
                        'confidence': float,
                        'source': str
                    }
                },
                'model_confidence': float
            }
        """
        result = {
            'corrected_data': auto_extracted_data.copy(),
            'suggestions': {},
            'model_confidence': 0.0
        }
        
        try:
            # Get continuous learning model
            model = get_enhanced_model()
            
            # Get supplier name if available
            supplier_name = None
            if 'master' in auto_extracted_data:
                supplier_name = auto_extracted_data['master'].get('supplier_name')
            
            # Apply corrections to master fields
            if 'master' in result['corrected_data']:
                master = result['corrected_data']['master']
                
                for field in ['supplier_name', 'voucher_date', 'voucher_number', 
                             'gross_total', 'net_total']:
                    if field in master:
                        suggestion = model.get_correction_suggestion(
                            field_name=field,
                            raw_ocr=raw_ocr,
                            current_value=master[field],
                            supplier_name=supplier_name
                        )
                        
                        if suggestion['suggestion'] and suggestion['confidence'] >= 0.7:
                            result['suggestions'][field] = suggestion
                            # Don't auto-apply, just suggest
                            master[f'{field}_suggestion'] = suggestion['suggestion']
                            master[f'{field}_confidence'] = suggestion['confidence']
            
            # Apply corrections to line items
            if 'items' in result['corrected_data']:
                for i, item in enumerate(result['corrected_data']['items']):
                    for field in ['item_name', 'quantity', 'unit_price', 'line_amount']:
                        field_key = f"item_{field}"
                        if field in item:
                            suggestion = model.get_correction_suggestion(
                                field_name=field_key,
                                raw_ocr=raw_ocr,
                                current_value=str(item[field]),
                                supplier_name=supplier_name
                            )
                            
                            if suggestion['suggestion'] and suggestion['confidence'] >= 0.7:
                                result['suggestions'][f"items[{i}].{field}"] = suggestion
            
            # Calculate overall confidence
            if result['suggestions']:
                confidences = [s['confidence'] for s in result['suggestions'].values()]
                result['model_confidence'] = sum(confidences) / len(confidences)
            
        except Exception as e:
            ml_logger.error(f"[EnhancedML] Error applying corrections: {e}")
        
        return result
    
    @staticmethod
    def record_correction_feedback(predicted_field: str,
                                 predicted_value: str,
                                 actual_value: str,
                                 confidence: float,
                                 raw_ocr: str,
                                 supplier_name: str = None):
        """
        Record feedback on a prediction for continuous learning
        """
        try:
            model = get_enhanced_model()
            
            was_correct = (str(predicted_value) == str(actual_value))
            
            model.record_prediction_result(
                field_name=predicted_field,
                predicted_value=predicted_value,
                actual_value=actual_value,
                confidence=confidence,
                was_correct=was_correct
            )
            
            # If prediction was wrong, learn from it immediately
            if not was_correct:
                model.learn_from_correction(
                    field_name=predicted_field,
                    raw_ocr=raw_ocr,
                    auto_extracted=predicted_value,
                    user_corrected=actual_value,
                    supplier_name=supplier_name,
                    confidence=1.0
                )
                
                # Save model periodically (every 10 new learnings)
                if model.stats['total_corrections'] % 10 == 0:
                    model.save_model()
        
        except Exception as e:
            ml_logger.error(f"[EnhancedML] Error recording feedback: {e}")
    
    @staticmethod
    def get_model_status() -> Dict[str, Any]:
        """
        Get comprehensive status of all ML models
        """
        try:
            model = get_enhanced_model()
            
            return {
                'continuous_model': {
                    'available': True,
                    'total_patterns': len(model.patterns),
                    'total_corrections': model.stats['total_corrections'],
                    'accuracy': model.stats['model_accuracy'],
                    'performance_metrics': model.get_performance_metrics()
                },
                'traditional_models': {
                    'ocr': EnhancedMLTrainingService._get_traditional_model_status('ocr'),
                    'parsing': EnhancedMLTrainingService._get_traditional_model_status('parsing')
                }
            }
        except Exception as e:
            return {
                'error': str(e),
                'continuous_model': {'available': False},
                'traditional_models': {}
            }
    
    @staticmethod
    def _get_traditional_model_status(model_type: str) -> Dict[str, Any]:
        """Get status of traditional models"""
        try:
            from backend.services.ml_training_service import MLTrainingService
            status = MLTrainingService.get_training_status()
            
            if model_type == 'ocr':
                return {
                    'available': status.get('ocr_model_available', False),
                    'stats': status.get('ocr_stats', {})
                }
            else:
                return {
                    'available': status.get('parsing_model_available', False),
                    'fields': status.get('parsing_fields', [])
                }
        except:
            return {'available': False}
