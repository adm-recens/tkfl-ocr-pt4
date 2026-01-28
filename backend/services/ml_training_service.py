"""
ML Training Service - Trains correction models from user feedback
"""

import json
import os
from datetime import datetime
from backend.db import get_connection
from backend.ml_models.ml_correction_model import OCRCorrectionModel, ParsingCorrectionModel
from backend.services.ml_feedback_service import MLFeedbackService
from backend.services.smart_crop_training_service import SmartCropTrainingService
from backend.services.learning_history_tracker import LearningHistoryTracker


class MLTrainingService:
    """Service to manage ML model training from user feedback"""
    
    OCR_MODEL_NAME = 'ocr_corrections_model.json'
    PARSING_MODEL_NAME = 'parsing_corrections_model.json'
    
    @staticmethod
    def collect_training_data(limit: int = 5000):
        """
        Collect training data from:
        1. Database validated vouchers (regular /validate page)
        2. Batch validation feedback (batch processing workflow)
        3. Regular validation feedback (recorded corrections)
        
        Returns list of training examples
        """
        training_data = {
            'ocr_corrections': [],
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
            
            # Get vouchers where user made corrections
            # Compare parsed_json_original (OCR output) with parsed_json (user corrections)
            cur.execute("""
                SELECT 
                    id,
                    raw_ocr_text,
                    parsed_json_original,
                    parsed_json,
                    supplier_name as user_supplier,
                    voucher_date as user_date,
                    voucher_number as user_voucher
                FROM vouchers_master
                WHERE validation_status = 'VALIDATED' AND parsed_json_original IS NOT NULL
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            
            vouchers = cur.fetchall()
            
            for voucher in vouchers:
                raw_ocr = voucher['raw_ocr_text'] or ''
                
                # Get original OCR data
                original_parsed_json = voucher['parsed_json_original']
                if isinstance(original_parsed_json, str):
                    original_parsed_json = json.loads(original_parsed_json)
                
                # Get user-corrected data
                parsed_json = voucher['parsed_json']
                if isinstance(parsed_json, str):
                    parsed_json = json.loads(parsed_json)
                
                original_master = original_parsed_json.get('master', {})
                corrected_master = parsed_json.get('master', {})
                
                # Check supplier name correction
                if original_master.get('supplier_name') != corrected_master.get('supplier_name'):
                    training_data['parsing_corrections'].append({
                        'field': 'supplier_name',
                        'raw_ocr': raw_ocr,
                        'auto': original_master.get('supplier_name'),
                        'corrected': corrected_master.get('supplier_name'),
                        'source': 'database'
                    })
                    training_data['source_breakdown']['database'] += 1
                
                # Check date correction
                if original_master.get('voucher_date') != corrected_master.get('voucher_date'):
                    training_data['parsing_corrections'].append({
                        'field': 'voucher_date',
                        'raw_ocr': raw_ocr,
                        'auto': original_master.get('voucher_date'),
                        'corrected': corrected_master.get('voucher_date'),
                        'source': 'database'
                    })
                    training_data['source_breakdown']['database'] += 1
                
                # Check voucher number correction
                if original_master.get('voucher_number') != corrected_master.get('voucher_number'):
                    training_data['parsing_corrections'].append({
                        'field': 'voucher_number',
                        'raw_ocr': raw_ocr,
                        'auto': original_master.get('voucher_number'),
                        'corrected': corrected_master.get('voucher_number'),
                        'source': 'database'
                    })
                    training_data['source_breakdown']['database'] += 1
            
            cur.close()
        except Exception as e:
            print(f"[ML-TRAINING] Error collecting database training data: {e}")
        
        # Source 2 & 3: Batch and regular validation feedback
        try:
            all_corrections = MLFeedbackService.get_all_corrections(limit=limit)
            
            # Process batch validation feedback
            for correction in all_corrections.get('batch_corrections', []):
                corrections_dict = correction.get('corrections', {})
                raw_ocr = correction.get('raw_ocr_text', '')
                
                for field, change in corrections_dict.items():
                    if isinstance(change, dict) and 'original' in change and 'corrected' in change:
                        training_data['parsing_corrections'].append({
                            'field': field,
                            'raw_ocr': raw_ocr,
                            'auto': change['original'],
                            'corrected': change['corrected'],
                            'source': 'batch_validation'
                        })
                        training_data['source_breakdown']['batch_feedback'] += 1
            
            # Process regular validation feedback
            for correction in all_corrections.get('regular_corrections', []):
                corrections_dict = correction.get('corrections', {})
                raw_ocr = correction.get('raw_ocr_text', '')
                
                for field, change in corrections_dict.items():
                    if isinstance(change, dict) and 'original' in change and 'corrected' in change:
                        training_data['parsing_corrections'].append({
                            'field': field,
                            'raw_ocr': raw_ocr,
                            'auto': change['original'],
                            'corrected': change['corrected'],
                            'source': 'regular_validation'
                        })
                        training_data['source_breakdown']['regular_feedback'] += 1
        
        except Exception as e:
            print(f"[ML-TRAINING] Error collecting feedback training data: {e}")
        
        return training_data
    
    @staticmethod
    def train_models(feedback_limit: int = 5000, save_models: bool = True, include_smart_crop: bool = True):
        """
        Train OCR, Parsing correction models AND Smart Crop model from collected feedback.
        
        Args:
            feedback_limit: Max number of corrections to use
            save_models: Whether to save trained models to disk
            include_smart_crop: Whether to train smart crop model as well
        
        Returns: {
            'status': 'success|error',
            'ocr_model_stats': {...},
            'parsing_model_stats': {...},
            'smart_crop_stats': {...},
            'total_samples': int,
            'training_time': float
        }
        """
        import time
        start_time = time.time()
        
        result = {
            'status': 'success',
            'training_time': 0,
            'ocr_model_stats': {},
            'parsing_model_stats': {},
            'smart_crop_stats': {},
            'models_saved': save_models
        }
        
        try:
            # Train OCR and Parsing models
            correction_result = MLTrainingService._train_correction_models(feedback_limit, save_models)
            result.update(correction_result)
            
            # Train Smart Crop model if requested
            if include_smart_crop:
                try:
                    crop_result = SmartCropTrainingService.train_smart_crop_model(data_limit=feedback_limit)
                    result['smart_crop_stats'] = crop_result.get('model_stats', {})
                    result['smart_crop_status'] = crop_result.get('status', 'unknown')
                except Exception as e:
                    print(f"[ML-TRAINING] Smart crop training failed: {e}")
                    result['smart_crop_stats'] = {'error': str(e)}
                    result['smart_crop_status'] = 'failed'
            
            result['training_time'] = time.time() - start_time
            
            # Record this training session in history
            corrections_used = []
            training_data = MLTrainingService.collect_training_data(feedback_limit)
            for corr in training_data.get('parsing_corrections', []):
                corrections_used.append({
                    'id': f"{corr.get('field')}_{corr.get('auto')}_{corr.get('corrected')}",
                    'field': corr.get('field'),
                    'auto': corr.get('auto'),
                    'corrected': corr.get('corrected'),
                    'source': corr.get('source')
                })
            
            # Track what was learned
            new_patterns = []
            if result.get('parsing_model_stats'):
                for field, patterns in result.get('parsing_model_stats', {}).items():
                    if field != 'version' and field != 'trained_at':
                        new_patterns.append({
                            'field': field,
                            'patterns': len(patterns) if isinstance(patterns, dict) else 1
                        })
            
            result['new_patterns'] = new_patterns
            result['corrections_used_count'] = len(corrections_used)
            
            # Record to learning history
            LearningHistoryTracker.record_training_session(
                corrections_used=corrections_used,
                training_results=result
            )
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            result['training_time'] = time.time() - start_time
        
        return result
    
    @staticmethod
    def _train_correction_models(feedback_limit: int = 5000, save_models: bool = True) -> Dict:
        """
        Train OCR and Parsing correction models.
        Separated from main train_models for modularity.
        """
        try:
            # Collect training data
            training_data = MLTrainingService.collect_training_data(feedback_limit)
            
            # Initialize models
            ocr_model = OCRCorrectionModel()
            parsing_model = ParsingCorrectionModel()
            
            # Train OCR correction model
            for correction in training_data.get('ocr_corrections', []):
                ocr_model.learn_from_correction(
                    raw_ocr=correction.get('raw_ocr'),
                    auto_extracted=correction.get('auto'),
                    user_corrected=correction.get('corrected'),
                    field_name=correction.get('field')
                )
            
            # Train parsing correction model
            for correction in training_data.get('parsing_corrections', []):
                parsing_model.learn_from_correction(
                    field_name=correction.get('field'),
                    raw_ocr=correction.get('raw_ocr'),
                    auto_extracted=correction.get('auto'),
                    user_corrected=correction.get('corrected')
                )
            
            # Save models if requested
            if save_models:
                ocr_model.save_model(MLTrainingService.OCR_MODEL_NAME)
                parsing_model.save_model(MLTrainingService.PARSING_MODEL_NAME)
            
            return {
                'status': 'success',
                'total_samples': len(training_data['ocr_corrections']) + len(training_data['parsing_corrections']),
                'ocr_samples': len(training_data['ocr_corrections']),
                'parsing_samples': len(training_data['parsing_corrections']),
                'source_breakdown': training_data.get('source_breakdown', {}),
                'ocr_model_stats': ocr_model.get_stats(),
                'parsing_model_stats': {
                    'version': parsing_model.model_version,
                    'trained_at': datetime.now().isoformat(),
                    'total_fields': len(parsing_model.parsing_corrections),
                    'fields': list(parsing_model.parsing_corrections.keys())
                }
            }
        
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    @staticmethod
    def get_training_status():
        """Get status of all models: OCR, Parsing, and Smart Crop"""
        ocr_model = OCRCorrectionModel()
        parsing_model = ParsingCorrectionModel()
        
        ocr_loaded = ocr_model.load_model(MLTrainingService.OCR_MODEL_NAME)
        parsing_loaded = parsing_model.load_model(MLTrainingService.PARSING_MODEL_NAME)
        
        # Get smart crop model status
        crop_status = SmartCropTrainingService.get_training_status()
        
        return {
            'ocr_model_available': ocr_loaded,
            'parsing_model_available': parsing_loaded,
            'smart_crop_model_available': crop_status.get('model_available', False),
            'ocr_stats': ocr_model.get_stats() if ocr_loaded else None,
            'parsing_fields': list(parsing_model.parsing_corrections.keys()) if parsing_loaded else [],
            'smart_crop_stats': {
                'trained_at': crop_status.get('trained_at'),
                'training_samples': crop_status.get('training_samples', 0),
                'patterns_count': crop_status.get('patterns_count', 0),
                'avg_crop_size': crop_status.get('avg_crop_size', {}),
                'crop_variations': crop_status.get('crop_variations', {})
            } if crop_status.get('model_available') else None,
            'last_trained': ocr_model.last_trained if isinstance(ocr_model.last_trained, str) else (ocr_model.last_trained.isoformat() if ocr_model.last_trained else None)
        }
    
    @staticmethod
    def apply_learned_corrections(auto_extracted_data: dict, raw_ocr: str) -> dict:
        """
        Apply learned corrections to auto-extracted data
        
        Args:
            auto_extracted_data: The parsed data from the parser
            raw_ocr: The raw OCR text
        
        Returns: Corrected data with applied ML suggestions
        """
        corrected = auto_extracted_data.copy()
        
        try:
            # Load trained models
            ocr_model = OCRCorrectionModel()
            parsing_model = ParsingCorrectionModel()
            
            ocr_loaded = ocr_model.load_model(MLTrainingService.OCR_MODEL_NAME)
            parsing_loaded = parsing_model.load_model(MLTrainingService.PARSING_MODEL_NAME)
            
            if not (ocr_loaded or parsing_loaded):
                return corrected  # Return original if no trained models
            
            # Apply OCR-level corrections
            if 'master' in corrected:
                master = corrected['master']
                
                # Try to correct supplier name
                if 'supplier_name' in master and parsing_loaded:
                    suggestion, confidence = parsing_model.get_correction_suggestion(
                        'supplier_name',
                        raw_ocr,
                        master.get('supplier_name', '')
                    )
                    if confidence > 0.7:
                        master['supplier_name_suggestion'] = suggestion
                        master['supplier_name_confidence'] = confidence
            
        except Exception as e:
            print(f"[ML] Error applying learned corrections: {e}")
        
        return corrected
