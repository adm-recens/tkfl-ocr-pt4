"""
ML Training Service - Trains correction models from user feedback
"""

import json
import os
from datetime import datetime
from backend.db import get_connection
from backend.ml_models.ml_correction_model import OCRCorrectionModel, ParsingCorrectionModel
from backend.services.ml_feedback_service import MLFeedbackService
import logging
from backend.services.learning_history_tracker import LearningHistoryTracker

# Initialize ML logger
ml_logger = logging.getLogger('ml')


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
                        'supplier_name': original_master.get('supplier_name') or corrected_master.get('supplier_name'),
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
                        'supplier_name': original_master.get('supplier_name') or corrected_master.get('supplier_name'),
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
                        'supplier_name': original_master.get('supplier_name') or corrected_master.get('supplier_name'),
                        'source': 'database'
                    })
                    training_data['source_breakdown']['database'] += 1
                # Check Deductions correction
                # Compare original vs corrected deductions list
                original_deductions = original_parsed_json.get('deductions', [])
                corrected_deductions = parsed_json.get('deductions', [])
                
                # Simple check: if different, we can try to learn. 
                # For now, we only learn patterns for deduction TYPES.
                # If user added a deduction that wasn't there, we want to learn the anchor for that type.
                if original_deductions != corrected_deductions:
                     for ded in corrected_deductions:
                        # If this deduction wasn't in original or was different
                        # (Simplification: just treat all validated deductions as positive training data)
                        training_data['parsing_corrections'].append({
                            'field': f"deduction_{ded.get('deduction_type')}", # e.g. deduction_Damage
                            'raw_ocr': raw_ocr,
                            'auto': '',  # We don't have a clear "before" value always, but anchor learning needs 'corrected'
                            'corrected': str(ded.get('amount')), # The value we want to find next time
                            'supplier_name': original_master.get('supplier_name') or corrected_master.get('supplier_name'),
                            'source': 'database'
                        })
                     training_data['source_breakdown']['database'] += 1
        except Exception as e:
            ml_logger.error(f"[ML-TRAINING] Error collecting database training data: {e}")
        
        # Source 2 & 3: Batch and regular validation feedback
        try:
            all_corrections = MLFeedbackService.get_all_corrections(limit=limit)
            
            # Process batch validation feedback
            for correction in all_corrections.get('batch_corrections', []):
                corrections_dict = correction.get('corrections', {})
                raw_ocr = correction.get('raw_ocr_text', '')
                
                for field, change in corrections_dict.items():
                    # Handle standard fields
                    if field not in ['items', 'items_count'] and isinstance(change, dict) and 'original' in change and 'corrected' in change:
                        training_data['parsing_corrections'].append({
                            'field': field,
                            'raw_ocr': raw_ocr,
                            'auto': change['original'],
                            'corrected': change['corrected'],
                            'source': 'batch_validation'
                        })
                        training_data['source_breakdown']['batch_feedback'] += 1
                    
                    # Handle Line Items
                    elif field == 'items' and isinstance(change, list):
                        for item_change in change:
                            # each item_change is {'item_index': X, 'corrections': {field: {original, corrected}}}
                            if 'corrections' in item_change:
                                for sub_field, sub_change in item_change['corrections'].items():
                                    if isinstance(sub_change, dict) and 'original' in sub_change:
                                        training_data['parsing_corrections'].append({
                                            'field': f"item_{sub_field}",  # e.g. item_description, item_line_amount
                                            'raw_ocr': raw_ocr,
                                            'auto': sub_change['original'],
                                            'corrected': sub_change['corrected'],
                                            'source': 'batch_validation'
                                        })
                                        training_data['source_breakdown']['batch_feedback'] += 1
                                        
                    # Handle Deductions
                    elif field == 'deductions':
                        # Change could be list diff or just list
                        # If it's a list correction structure
                        if isinstance(change, list):
                            for ded in change: # assuming it's the corrected list
                                if isinstance(ded, dict) and 'deduction_type' in ded:
                                     training_data['parsing_corrections'].append({
                                        'field': f"deduction_{ded.get('deduction_type')}",
                                        'raw_ocr': raw_ocr,
                                        'auto': '', 
                                        'corrected': str(ded.get('amount')),
                                        'source': 'batch_validation'
                                    })
                                     training_data['source_breakdown']['batch_feedback'] += 1
                        # If it's a direct replacement dict (rare for lists but possible in feedback service structure)
                        elif isinstance(change, dict) and 'corrected' in change:
                             for ded in change['corrected']:
                                  training_data['parsing_corrections'].append({
                                        'field': f"deduction_{ded.get('deduction_type')}",
                                        'raw_ocr': raw_ocr,
                                        'auto': '', 
                                        'corrected': str(ded.get('amount')),
                                        'source': 'batch_validation'
                                    })
                                  training_data['source_breakdown']['batch_feedback'] += 1
            
            # Process regular validation feedback
            for correction in all_corrections.get('regular_corrections', []):
                corrections_dict = correction.get('corrections', {})
                raw_ocr = correction.get('raw_ocr_text', '')
                
                for field, change in corrections_dict.items():
                    # Handle standard fields
                    if field not in ['items', 'items_count'] and isinstance(change, dict) and 'original' in change and 'corrected' in change:
                        training_data['parsing_corrections'].append({
                            'field': field,
                            'raw_ocr': raw_ocr,
                            'auto': change['original'],
                            'corrected': change['corrected'],
                            'source': 'regular_validation'
                        })
                        training_data['source_breakdown']['regular_feedback'] += 1

                    # Handle Line Items
                    elif field == 'items' and isinstance(change, list):
                        for item_change in change:
                            if 'corrections' in item_change:
                                for sub_field, sub_change in item_change['corrections'].items():
                                    if isinstance(sub_change, dict) and 'original' in sub_change:
                                        training_data['parsing_corrections'].append({
                                            'field': f"item_{sub_field}",
                                            'raw_ocr': raw_ocr,
                                            'auto': sub_change['original'],
                                            'corrected': sub_change['corrected'],
                                            'source': 'regular_validation'
                                        })
                                        training_data['source_breakdown']['regular_feedback'] += 1
        
        except Exception as e:
            ml_logger.error(f"[ML-TRAINING] Error collecting feedback training data: {e}")
        
        return training_data
    
    @staticmethod
    def train_models(feedback_limit: int = 5000, save_models: bool = True):
        """
        Train OCR and Parsing correction models from collected user feedback.
        
        Note: Smart Crop model is trained separately via SmartCropTrainingService.
        
        Args:
            feedback_limit: Max number of corrections to use
            save_models: Whether to save trained models to disk
        
        Returns: {
            'status': 'success|error',
            'ocr_model_stats': {...},
            'parsing_model_stats': {...},
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
            'models_saved': save_models
        }
        
        try:
            # Train OCR and Parsing models
            correction_result = MLTrainingService._train_correction_models(feedback_limit, save_models)
            result.update(correction_result)
            
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
            seen_patterns = set()
            for corr in corrections_used:
                pattern_key = f"{corr.get('field')}|{corr.get('auto')}|{corr.get('corrected')}"
                if pattern_key not in seen_patterns:
                    new_patterns.append({
                        'field': corr.get('field'),
                        'auto': corr.get('auto'),
                        'corrected': corr.get('corrected'),
                        'source': corr.get('source')
                    })
                    seen_patterns.add(pattern_key)
            
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
                # Standard value learning
                parsing_model.learn_from_correction(
                    field_name=correction.get('field'),
                    raw_ocr=correction.get('raw_ocr'),
                    auto_extracted=correction.get('auto'),
                    user_corrected=correction.get('corrected')
                )
                
                # New: Anchor Learning (Adaptive Parsing)
                # Learn identifying labels for next time
                supplier_name = correction.get('supplier_name')
                if supplier_name:
                    parsing_model.learn_anchor(
                        field_name=correction.get('field'),
                        raw_ocr=correction.get('raw_ocr'),
                        corrected_value=correction.get('corrected'),
                        supplier_name=supplier_name
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
        """Get status of text parsing models: OCR and Parsing."""
        ocr_model = OCRCorrectionModel()
        parsing_model = ParsingCorrectionModel()
        
        ocr_loaded = ocr_model.load_model(MLTrainingService.OCR_MODEL_NAME)
        parsing_loaded = parsing_model.load_model(MLTrainingService.PARSING_MODEL_NAME)
        
        return {
            'ocr_model_available': ocr_loaded,
            'parsing_model_available': parsing_loaded,
            'ocr_stats': ocr_model.get_stats() if ocr_loaded else None,
            'parsing_fields': list(parsing_model.parsing_corrections.keys()) if parsing_loaded else [],
            'last_trained': ocr_model.last_trained if isinstance(ocr_model.last_trained, str) else (ocr_model.last_trained.isoformat() if ocr_model.last_trained else None)
        }
    
    @staticmethod
    def apply_ocr_character_corrections(raw_text: str) -> str:
        """Globally apply OCR character swaps learned from user corrections before standard parsing."""
        try:
            ocr_model = OCRCorrectionModel()
            if ocr_model.load_model(MLTrainingService.OCR_MODEL_NAME):
                return ocr_model.apply_ocr_corrections(raw_text)
        except Exception as e:
            ml_logger.error(f"[ML] Error applying OCR corrections: {e}")
        return raw_text
    
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
                    result = parsing_model.get_correction_suggestion(
                        'supplier_name',
                        raw_ocr,
                        master.get('supplier_name', '')
                    )
                    suggestion = result.get('suggestion')
                    confidence = result.get('confidence', 0.0)
                    
                    if confidence > 0.7:
                        master['supplier_name_suggestion'] = suggestion
                        master['supplier_name_confidence'] = confidence
                
                # RE-PARSING STRATEGY: Use learned anchors to find missing/better values
                supplier_name = master.get('supplier_name_suggestion') or master.get('supplier_name')
                
                if supplier_name and parsing_loaded:
                    # 1. Recover/Overwrite Date
                    anchor_result = parsing_model.find_value_by_anchor('voucher_date', raw_ocr, supplier_name)
                    if anchor_result and anchor_result.get('confidence', 0) > 0.8:
                        from backend.parser import try_parse_date
                        parsed_date = try_parse_date(anchor_result['value'])
                        if parsed_date:
                            master['voucher_date'] = parsed_date
                    
                    # 2. Recover/Overwrite Voucher Number
                    anchor_result = parsing_model.find_value_by_anchor('voucher_number', raw_ocr, supplier_name)
                    if anchor_result and anchor_result.get('confidence', 0) > 0.8:
                        cleaned_vn = "".join(c for c in anchor_result['value'] if c.isalnum() or c in '-/')
                        if cleaned_vn:
                            master['voucher_number'] = cleaned_vn
                                
                    # 3. Recover/Overwrite Totals
                    for total_field in ['net_total', 'gross_total']:
                        anchor_result = parsing_model.find_value_by_anchor(total_field, raw_ocr, supplier_name)
                        if anchor_result and anchor_result.get('confidence', 0) > 0.8:
                            from backend.parser import safe_float_conversion
                            val = safe_float_conversion(anchor_result['value'])
                            if val:
                                master[total_field] = val
            
            # Apply Item-level corrections
            if 'items' in corrected and parsing_loaded:
                for item in corrected['items']:
                    # Correct Item Name
                    if 'item_name' in item:
                        result = parsing_model.get_correction_suggestion(
                            'item_item_name',  # Matches field name in training data
                            raw_ocr,
                            item.get('item_name', '')
                        )
                        if result.get('confidence', 0.0) > 0.7:
                            item['item_name'] = result.get('suggestion')  # Apply directly
                    
                    # Correct Quantity
                    if 'quantity' in item:
                        result = parsing_model.get_correction_suggestion(
                            'item_quantity', 
                            raw_ocr,
                            str(item.get('quantity', ''))
                        )
                        if result.get('confidence', 0.0) > 0.7:
                            item['quantity'] = result.get('suggestion')
                            
                    # Correct Unit Price
                    if 'unit_price' in item:
                        result = parsing_model.get_correction_suggestion(
                            'item_unit_price', 
                            raw_ocr,
                            str(item.get('unit_price', ''))
                        )
                        if result.get('confidence', 0.0) > 0.7:
                            item['unit_price'] = result.get('suggestion')

                    # Correct Line Amount
                    if 'line_amount' in item:
                        result = parsing_model.get_correction_suggestion(
                            'item_line_amount', 
                            raw_ocr,
                            str(item.get('line_amount', ''))
                        )
                        if result.get('confidence', 0.0) > 0.7:
                            item['line_amount'] = result.get('suggestion')
                            
            # 4. Recover/Overwrite Deductions (Adaptive Deduction Parsing)
            if parsing_loaded and supplier_name:
                learned_deductions = parsing_model.learned_anchors.get(supplier_name.upper(), {})
                from backend.parser import safe_float_conversion
                
                # Keep existing deductions, but overwrite if ML has high confidence
                existing_deductions = {d.get('deduction_type'): d.get('amount') for d in corrected.get('deductions', [])}
                
                for field, anchors in learned_deductions.items():
                    if field.startswith('deduction_'):
                        ded_type = field.replace('deduction_', '')
                        anchor_result = parsing_model.find_value_by_anchor(field, raw_ocr, supplier_name)
                        
                        if anchor_result and anchor_result.get('confidence', 0) > 0.8:
                            val = safe_float_conversion(anchor_result['value'])
                            if val and val > 0:
                                existing_deductions[ded_type] = val

                if existing_deductions:
                    corrected['deductions'] = [{'deduction_type': k, 'amount': v} for k, v in existing_deductions.items()]
            
        except Exception as e:
            ml_logger.error(f"[ML] Error applying learned corrections: {e}")
        
        return corrected
