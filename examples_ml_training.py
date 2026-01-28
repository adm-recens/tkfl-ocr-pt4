#!/usr/bin/env python3
"""
Example script showing how to use the ML training system
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def example_1_train_models():
    """Example 1: Train models from validated vouchers"""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Train ML Models from Validated Vouchers")
    print("=" * 80)
    
    from backend.services.ml_training_service import MLTrainingService
    
    print("\n[1] Collecting training data...")
    training_data = MLTrainingService.collect_training_data(limit=100)
    print(f"    Found {len(training_data['parsing_corrections'])} parsing corrections")
    print(f"    Found {len(training_data['ocr_corrections'])} OCR corrections")
    
    print("\n[2] Training models...")
    result = MLTrainingService.train_models(feedback_limit=100, save_models=True)
    
    print(f"\n    Status: {result['status']}")
    print(f"    Training time: {result.get('training_time', 0):.2f}s")
    print(f"    Total samples: {result.get('total_samples', 0)}")
    
    if result['status'] == 'success':
        print(f"\n    OCR Model:")
        print(f"      - Patterns learned: {result['ocr_model_stats'].get('total_ocr_patterns', 0)}")
        print(f"      - Vocabulary corrections: {result['ocr_model_stats'].get('total_vocab_corrections', 0)}")
        
        print(f"\n    Parsing Model:")
        print(f"      - Fields trained: {len(result['parsing_model_stats'].get('fields', []))}")
    
    return result['status'] == 'success'


def example_2_check_models():
    """Example 2: Check available trained models"""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Check Available Trained Models")
    print("=" * 80)
    
    from backend.services.ml_training_service import MLTrainingService
    
    print("\n[*] Checking model availability...")
    status = MLTrainingService.get_training_status()
    
    print(f"\n    OCR Model Available: {status['ocr_model_available']}")
    if status['ocr_model_available'] and status['ocr_stats']:
        print(f"      - Patterns learned: {status['ocr_stats'].get('total_ocr_patterns', 0)}")
        print(f"      - Trained fields: {', '.join(status['ocr_stats'].get('fields_trained', []))}")
    
    print(f"\n    Parsing Model Available: {status['parsing_model_available']}")
    if status['parsing_model_available']:
        print(f"      - Fields with rules: {', '.join(status['parsing_fields'])}")
    
    print(f"\n    Last Trained: {status['last_trained']}")


def example_3_apply_corrections():
    """Example 3: Apply learned corrections to extracted data"""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Apply Learned Corrections")
    print("=" * 80)
    
    from backend.ml_models.ml_correction_model import OCRCorrectionModel, ParsingCorrectionModel
    
    # Create models and load trained weights
    print("\n[1] Loading trained models...")
    ocr_model = OCRCorrectionModel()
    parsing_model = ParsingCorrectionModel()
    
    ocr_loaded = ocr_model.load_model()
    parsing_loaded = parsing_model.load_model()
    
    print(f"    OCR model loaded: {ocr_loaded}")
    print(f"    Parsing model loaded: {parsing_loaded}")
    
    if not ocr_loaded and not parsing_loaded:
        print("\n    [!] No trained models found. Train models first with example 1.")
        return False
    
    # Example: Apply OCR correction
    print("\n[2] Example OCR Corrections:")
    test_text = "SuppNane"  # Common OCR error
    corrected = ocr_model.apply_correction(test_text)
    confidence = ocr_model.get_correction_confidence(test_text, corrected)
    
    print(f"    Input: '{test_text}'")
    print(f"    Corrected: '{corrected}'")
    print(f"    Confidence: {confidence:.2%}")
    
    # Example: Get parsing suggestions
    print("\n[3] Example Parsing Suggestions:")
    if parsing_loaded:
        suggestion, conf = parsing_model.get_correction_suggestion(
            'supplier_name',
            'TK\nSuppNane\nOther text',
            'AS'
        )
        print(f"    Field: supplier_name")
        print(f"    Auto extracted: 'AS'")
        print(f"    Suggested: '{suggestion}'")
        print(f"    Confidence: {conf:.2%}")
    
    return True


def example_4_custom_training():
    """Example 4: Train on custom corrections"""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Custom Training on Single Correction")
    print("=" * 80)
    
    from backend.ml_models.ml_correction_model import OCRCorrectionModel
    
    print("\n[1] Creating model and learning from correction...")
    model = OCRCorrectionModel()
    
    # Simulate learning from a user correction
    print("    Learning: 'invoce' -> 'invoice'")
    model.learn_from_correction(
        raw_ocr="Invoice Number: invoce",
        auto_extracted="invoce",
        user_corrected="invoice",
        field_name="invoice_number"
    )
    
    # Try to apply the learned correction
    print("\n[2] Applying learned correction...")
    test = "invoce"
    corrected = model.apply_correction(test)
    print(f"    Input: '{test}'")
    print(f"    Output: '{corrected}'")
    
    # Show model stats
    print("\n[3] Model Statistics:")
    stats = model.get_stats()
    print(f"    Total patterns: {stats['total_ocr_patterns']}")
    print(f"    Vocabulary corrections: {stats['total_vocab_corrections']}")
    
    return True


def main():
    """Run all examples"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "ML TRAINING SYSTEM - USAGE EXAMPLES" + " " * 24 + "║")
    print("╚" + "=" * 78 + "╝")
    
    try:
        # Run examples
        example_2_check_models()
        example_4_custom_training()
        example_3_apply_corrections()
        
        print("\n" + "=" * 80)
        print("ALL EXAMPLES COMPLETED")
        print("=" * 80)
        print("""
For production use, recommend:
1. Train models after every 50-100 validated vouchers
2. Monitor model accuracy and adjust confidence thresholds as needed
3. Retrain monthly to capture latest patterns

See ML_TRAINING_GUIDE.md for complete documentation.
""")
        
    except Exception as e:
        print(f"\n[✗] Error running examples: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
