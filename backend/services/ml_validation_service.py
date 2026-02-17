"""
ML Validation Service - Measures actual model performance

Provides:
- Train/validation split
- Field-level accuracy metrics
- Before/after comparison
- Performance tracking over time
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Tuple
import random
from pathlib import Path

class MLValidationService:
    """Service to validate ML model performance"""
    
    VALIDATION_RESULTS_FILE = Path('backend/data/validation_results.json')
    
    @staticmethod
    def _ensure_results_file():
        """Create validation results file if it doesn't exist"""
        if not MLValidationService.VALIDATION_RESULTS_FILE.exists():
            MLValidationService.VALIDATION_RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            initial_data = {
                'version': '1.0',
                'created_at': datetime.now().isoformat(),
                'validation_runs': []
            }
            with open(MLValidationService.VALIDATION_RESULTS_FILE, 'w') as f:
                json.dump(initial_data, f, indent=2)
    
    @staticmethod
    def split_training_data(corrections: List[Dict], validation_ratio: float = 0.2) -> Tuple[List[Dict], List[Dict]]:
        """
        Split corrections into training and validation sets
        
        Args:
            corrections: List of correction examples
            validation_ratio: Fraction to use for validation (default 0.2 = 20%)
        
        Returns:
            (training_set, validation_set)
        """
        # Shuffle to randomize
        shuffled = corrections.copy()
        random.shuffle(shuffled)
        
        split_idx = int(len(shuffled) * (1 - validation_ratio))
        training = shuffled[:split_idx]
        validation = shuffled[split_idx:]
        
        return training, validation
    
    @staticmethod
    def calculate_field_accuracy(predictions: List[Dict], ground_truth: List[Dict], field_name: str) -> Dict:
        """
        Calculate accuracy for a specific field
        
        Args:
            predictions: List of predicted values
            ground_truth: List of actual values
            field_name: Name of field to evaluate
        
        Returns:
            {
                'accuracy': float,  # 0-1
                'total_samples': int,
                'correct_count': int,
                'error_examples': List[Dict]  # Sample of errors
            }
        """
        if not predictions or not ground_truth or len(predictions) != len(ground_truth):
            return {'accuracy': 0.0, 'total_samples': 0, 'correct_count': 0, 'error_examples': []}
        
        correct = 0
        total = len(predictions)
        errors = []
        
        for pred, truth in zip(predictions, ground_truth):
            pred_val = pred.get(field_name)
            truth_val = truth.get(field_name)
            
            # Handle None/empty values
            if pred_val is None:
                pred_val = ''
            if truth_val is None:
                truth_val = ''
            
            # Normalize for comparison
            pred_str = str(pred_val).strip().lower()
            truth_str = str(truth_val).strip().lower()
            
            if pred_str == truth_str:
                correct += 1
            else:
                # Record error example
                if len(errors) < 10:  # Keep max 10 examples
                    errors.append({
                        'predicted': pred_val,
                        'actual': truth_val,
                        'raw_text_snippet': pred.get('raw_ocr', '')[:100]  # First 100 chars
                    })
        
        return {
            'accuracy': correct / total if total > 0 else 0.0,
            'total_samples': total,
            'correct_count': correct,
            'error_examples': errors
        }
    
    @staticmethod
    def calculate_numeric_accuracy(predictions: List[Dict], ground_truth: List[Dict], field_name: str) -> Dict:
        """
        Calculate accuracy for numeric fields (amounts, totals)
        Uses mean absolute percentage error (MAPE)
        """
        if not predictions or not ground_truth:
            return {'mape': 0.0, 'mae': 0.0, 'total_samples': 0}
        
        errors = []
        absolute_errors = []
        
        for pred, truth in zip(predictions, ground_truth):
            pred_val = pred.get(field_name)
            truth_val = truth.get(field_name)
            
            # Skip if either is None/empty
            if pred_val is None or truth_val is None:
                continue
            
            try:
                pred_num = float(pred_val)
                truth_num = float(truth_val)
                
                if truth_num != 0:
                    # Percentage error
                    pct_error = abs((pred_num - truth_num) / truth_num)
                    errors.append(pct_error)
                
                # Absolute error
                absolute_errors.append(abs(pred_num - truth_num))
            except (ValueError, TypeError):
                continue
        
        if not errors:
            return {'mape': 0.0, 'mae': 0.0, 'total_samples': 0}
        
        mape = sum(errors) / len(errors)
        mae = sum(absolute_errors) / len(absolute_errors)
        
        # Convert MAPE to accuracy (1 - error)
        accuracy = max(0.0, 1.0 - mape)
        
        return {
            'accuracy': accuracy,
            'mape': mape,
            'mae': mae,
            'total_samples': len(errors)
        }
    
    @staticmethod
    def run_validation(validation_data: List[Dict], apply_ml: bool = False) -> Dict:
        """
        Run validation on a dataset
        
        Args:
            validation_data: List of examples with 'raw_ocr', 'auto', 'corrected', 'field'
            apply_ml: Whether to apply ML corrections
        
        Returns:
            Validation metrics by field
        """
        from backend.parser import parse_receipt_text
        from backend.services.ml_training_service import MLTrainingService
        
        results_by_field = {}
        
        # Group by field
        field_groups = {}
        for example in validation_data:
            field = example.get('field', 'unknown')
            if field not in field_groups:
                field_groups[field] = []
            field_groups[field].append(example)
        
        # Evaluate each field
        for field, examples in field_groups.items():
            predictions = []
            ground_truth = []
            
            for example in examples:
                raw_ocr = example.get('raw_ocr', '')
                corrected_value = example.get('corrected')
                
                # Parse the text
                parsed = parse_receipt_text(raw_ocr)
                
                # Apply ML if requested
                if apply_ml:
                    parsed = MLTrainingService.apply_learned_corrections(parsed, raw_ocr)
                
                # Extract the field value
                if field.startswith('item_'):
                    # Item field
                    item_field = field.replace('item_', '')
                    pred_value = parsed.get('items', [{}])[0].get(item_field) if parsed.get('items') else None
                elif field.startswith('deduction_'):
                    # Deduction field
                    pred_value = None  # Complex to extract
                else:
                    # Master field
                    pred_value = parsed.get('master', {}).get(field)
                
                predictions.append({
                    field: pred_value,
                    'raw_ocr': raw_ocr
                })
                ground_truth.append({
                    field: corrected_value
                })
            
            # Calculate accuracy
            if field in ['gross_total', 'net_total', 'total_deductions']:
                metrics = MLValidationService.calculate_numeric_accuracy(predictions, ground_truth, field)
            else:
                metrics = MLValidationService.calculate_field_accuracy(predictions, ground_truth, field)
            
            results_by_field[field] = metrics
        
        return results_by_field
    
    @staticmethod
    def compare_before_after(validation_data: List[Dict]) -> Dict:
        """
        Compare parser performance before and after ML corrections
        
        Returns:
            {
                'before': {...},
                'after': {...},
                'improvement': {...}
            }
        """
        print("[ML-VALIDATION] Running before/after comparison...")
        
        # Run without ML
        before_results = MLValidationService.run_validation(validation_data, apply_ml=False)
        
        # Run with ML
        after_results = MLValidationService.run_validation(validation_data, apply_ml=True)
        
        # Calculate improvement
        improvement = {}
        for field in before_results.keys():
            before_acc = before_results[field].get('accuracy', 0.0)
            after_acc = after_results[field].get('accuracy', 0.0)
            
            if before_acc > 0:
                pct_improvement = ((after_acc - before_acc) / before_acc) * 100
            else:
                pct_improvement = 0.0
            
            improvement[field] = {
                'before_accuracy': round(before_acc, 3),
                'after_accuracy': round(after_acc, 3),
                'absolute_improvement': round(after_acc - before_acc, 3),
                'percent_improvement': round(pct_improvement, 1)
            }
        
        return {
            'before': before_results,
            'after': after_results,
            'improvement': improvement,
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    def save_validation_results(results: Dict):
        """Save validation results to file"""
        MLValidationService._ensure_results_file()
        
        with open(MLValidationService.VALIDATION_RESULTS_FILE, 'r') as f:
            data = json.load(f)
        
        data['validation_runs'].append(results)
        
        with open(MLValidationService.VALIDATION_RESULTS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    
    @staticmethod
    def get_latest_validation() -> Dict:
        """Get the most recent validation results"""
        MLValidationService._ensure_results_file()
        
        with open(MLValidationService.VALIDATION_RESULTS_FILE, 'r') as f:
            data = json.load(f)
        
        runs = data.get('validation_runs', [])
        return runs[-1] if runs else None
