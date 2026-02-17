"""
Enhanced ML Training with Validation Metrics

Wraps existing training service to add confidence-building features:
- Before/after accuracy comparison
- Validation metrics
- Improvement tracking
"""

from backend.services.ml_training_service import MLTrainingService
from backend.services.ml_validation_service import MLValidationService
import logging

ml_logger = logging.getLogger('ml')

class EnhancedMLTraining:
    """Enhanced training with validation and confidence metrics"""
    
    @staticmethod
    def train_with_validation(feedback_limit: int = 5000, save_models: bool = True, include_smart_crop: bool = True):
        """
        Train models with validation metrics to prove improvement
        
        Returns enhanced results with:
        - validation.improvement: Before/after accuracy by field
        - validation.summary: Overall improvement statistics
        - confidence_report: Human-readable improvement summary
        """
        ml_logger.info("[ENHANCED-TRAINING] Starting training with validation...")
        
        # Step 1: Collect all training data
        training_data = MLTrainingService.collect_training_data(feedback_limit)
        all_corrections = training_data.get('parsing_corrections', [])
        
        ml_logger.info(f"[ENHANCED-TRAINING] Collected {len(all_corrections)} corrections")
        
        # Step 2: Split into train/validation
        validation_results = None
        if len(all_corrections) >= 10:
            train_set, validation_set = MLValidationService.split_training_data(all_corrections, validation_ratio=0.2)
            
            ml_logger.info(f"[ENHANCED-TRAINING] Split: {len(train_set)} train, {len(validation_set)} validation")
            
            # Step 3: Run BEFORE validation (baseline)
            ml_logger.info("[ENHANCED-TRAINING] Running baseline validation...")
            before_results = MLValidationService.run_validation(validation_set, apply_ml=False)
            
            # Step 4: Train models
            ml_logger.info("[ENHANCED-TRAINING] Training models...")
            training_result = MLTrainingService.train_models(
                feedback_limit=feedback_limit,
                save_models=save_models,
                include_smart_crop=include_smart_crop
            )
            
            # Step 5: Run AFTER validation (with ML)
            ml_logger.info("[ENHANCED-TRAINING] Running post-training validation...")
            after_results = MLValidationService.run_validation(validation_set, apply_ml=True)
            
            # Step 6: Calculate improvement
            improvement = {}
            for field in before_results.keys():
                before_acc = before_results[field].get('accuracy', 0.0)
                after_acc = after_results[field].get('accuracy', 0.0)
                
                if before_acc > 0:
                    pct_improvement = ((after_acc - before_acc) / before_acc) * 100
                else:
                    pct_improvement = 0.0 if after_acc == 0 else 100.0
                
                improvement[field] = {
                    'before_accuracy': round(before_acc * 100, 1),  # Convert to percentage
                    'after_accuracy': round(after_acc * 100, 1),
                    'absolute_improvement': round((after_acc - before_acc) * 100, 1),
                    'percent_improvement': round(pct_improvement, 1),
                    'samples': before_results[field].get('total_samples', 0)
                }
            
            validation_results = {
                'before': before_results,
                'after': after_results,
                'improvement': improvement,
                'validation_samples': len(validation_set)
            }
            
            # Save validation results
            MLValidationService.save_validation_results(validation_results)
            
            # Add to training result
            training_result['validation'] = improvement
            training_result['validation_summary'] = {
                'validation_samples': len(validation_set),
                'fields_tested': len(improvement),
                'avg_improvement_pct': round(
                    sum(v.get('percent_improvement', 0) for v in improvement.values()) / max(1, len(improvement)),
                    1
                ),
                'best_field': max(improvement.items(), key=lambda x: x[1].get('percent_improvement', 0))[0] if improvement else None
            }
            
            ml_logger.info(f"[ENHANCED-TRAINING] Average improvement: {training_result['validation_summary']['avg_improvement_pct']}%")
        else:
            # Not enough data for validation
            ml_logger.warning("[ENHANCED-TRAINING] Not enough data for validation (need at least 10 samples)")
            training_result = MLTrainingService.train_models(
                feedback_limit=feedback_limit,
                save_models=save_models,
                include_smart_crop=include_smart_crop
            )
            training_result['validation_summary'] = {
                'error': 'Not enough data for validation',
                'samples_needed': 10,
                'samples_available': len(all_corrections)
            }
        
        # Generate confidence report
        training_result['confidence_report'] = EnhancedMLTraining._generate_confidence_report(training_result)
        
        return training_result
    
    @staticmethod
    def _generate_confidence_report(training_result: dict) -> str:
        """Generate human-readable confidence report"""
        lines = []
        lines.append("=" * 60)
        lines.append("ML TRAINING CONFIDENCE REPORT")
        lines.append("=" * 60)
        
        # Training summary
        lines.append(f"\n📊 Training Summary:")
        lines.append(f"  • Total corrections used: {training_result.get('corrections_used_count', 0)}")
        lines.append(f"  • Patterns learned: {len(training_result.get('new_patterns', []))}")
        lines.append(f"  • Training time: {training_result.get('training_time', 0):.1f}s")
        
        # Validation results
        validation = training_result.get('validation', {})
        validation_summary = training_result.get('validation_summary', {})
        
        if validation and not validation_summary.get('error'):
            lines.append(f"\n✅ Validation Results:")
            lines.append(f"  • Validation samples: {validation_summary.get('validation_samples', 0)}")
            lines.append(f"  • Fields tested: {validation_summary.get('fields_tested', 0)}")
            lines.append(f"  • Average improvement: +{validation_summary.get('avg_improvement_pct', 0)}%")
            
            lines.append(f"\n📈 Field-by-Field Improvement:")
            for field, metrics in sorted(validation.items(), key=lambda x: x[1].get('percent_improvement', 0), reverse=True):
                before = metrics.get('before_accuracy', 0)
                after = metrics.get('after_accuracy', 0)
                improvement = metrics.get('percent_improvement', 0)
                samples = metrics.get('samples', 0)
                
                if improvement > 0:
                    emoji = "🚀" if improvement > 20 else "📈" if improvement > 10 else "✓"
                elif improvement < 0:
                    emoji = "⚠️"
                else:
                    emoji = "→"
                
                lines.append(f"  {emoji} {field}: {before}% → {after}% ({improvement:+.1f}%) [{samples} samples]")
        else:
            error_msg = validation_summary.get('error', 'Unknown error')
            lines.append(f"\n⚠️  Validation: {error_msg}")
        
        # Top patterns learned
        patterns = training_result.get('new_patterns', [])
        if patterns:
            lines.append(f"\n🎓 Top Patterns Learned (showing first 10):")
            for i, pattern in enumerate(patterns[:10], 1):
                field = pattern.get('field', 'unknown')
                auto = pattern.get('auto', '')
                corrected = pattern.get('corrected', '')
                lines.append(f"  {i}. {field}: '{auto}' → '{corrected}'")
        
        lines.append("\n" + "=" * 60)
        
        return "\n".join(lines)
