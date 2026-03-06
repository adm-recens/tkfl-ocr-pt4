#!/usr/bin/env python3
"""
Initialize ML models directory and train initial models from existing validated vouchers
Run this once after deploying the ML system, or whenever you want to retrain
"""

import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def init_ml_system():
    """Initialize ML models from existing validated vouchers"""
    
    print("=" * 80)
    print("INITIALIZING ML TRAINING SYSTEM")
    print("=" * 80)
    
    # Create ML models directory
    ml_models_dir = os.path.join(os.path.dirname(__file__), 'backend', 'ml_models')
    os.makedirs(ml_models_dir, exist_ok=True)
    print(f"\n[✓] Created ML models directory: {ml_models_dir}")
    
    try:
        # Setup Flask app context for database access
        from backend.app import create_app
        app = create_app()
        
        with app.app_context():
            from backend.services.ml_training_service import MLTrainingService
            
            # Check current status
            print("\n[*] Checking current training status...")
            status = MLTrainingService.get_training_status()
            
            print(f"  OCR model available: {status['ocr_model_available']}")
            print(f"  Parsing model available: {status['parsing_model_available']}")
            print(f"  Last trained: {status['last_trained']}")
            
            # Collect and display training data availability
            print("\n[*] Collecting training data from validated vouchers...")
            training_data = MLTrainingService.collect_training_data(limit=10000)
            
            ocr_samples = len(training_data.get('ocr_corrections', []))
            parsing_samples = len(training_data.get('parsing_corrections', []))
            total_samples = ocr_samples + parsing_samples
            
            print(f"  Found {total_samples} training samples:")
            print(f"    - OCR corrections: {ocr_samples}")
            print(f"    - Parsing corrections: {parsing_samples}")
            
            if total_samples == 0:
                print("\n[!] No validated vouchers found. Cannot train models.")
                print("    Please validate some vouchers first, then run training again.")
                return False
            
            # Train models
            print("\n[*] Training ML models...")
            print("    This may take a few minutes depending on data size...")
            
            start_time = time.time()
            result = MLTrainingService.train_models(
                feedback_limit=10000,
                save_models=True
            )
            elapsed_time = time.time() - start_time
            
            if result['status'] == 'success':
                print(f"\n[✓] Training completed successfully!")
                print(f"  Duration: {elapsed_time:.2f} seconds")
                print(f"  Total samples trained: {result['total_samples']}")
                print(f"  OCR patterns learned: {result['ocr_model_stats']['total_ocr_patterns']}")
                print(f"  Parsing fields: {len(result['parsing_model_stats'].get('fields', []))}")
                
                # Show detailed stats
                if result['ocr_model_stats']:
                    print(f"\nOCR Model Statistics:")
                    print(f"  - Vocabulary corrections: {result['ocr_model_stats']['total_vocab_corrections']}")
                    print(f"  - Field patterns: {result['ocr_model_stats']['total_field_patterns']}")
                    print(f"  - Fields trained: {', '.join(result['ocr_model_stats'].get('fields_trained', []))}")
                
                if result['parsing_model_stats']:
                    print(f"\nParsing Model Statistics:")
                    print(f"  - Fields trained: {', '.join(result['parsing_model_stats'].get('fields', []))}")
                
                print(f"\n[✓] Models saved to: {ml_models_dir}")
                print("    - ocr_corrections_model.json")
                print("    - parsing_corrections_model.json")
            else:
                print(f"\n[✗] Training failed: {result['error']}")
            
            return result['status'] == 'success'
            
    except Exception as e:
        print(f"\n[✗] Error during ML initialization: {e}")
        import traceback
        traceback.print_exc()
        return False

def show_usage():
    """Show how to use the ML system"""
    print("\n" + "=" * 80)
    print("ML TRAINING SYSTEM - USAGE GUIDE")
    print("=" * 80)
    
    print("""
1. AUTOMATIC TRAINING VIA API:
   
   # Start training job
   curl -X POST http://localhost:5000/api/training/start \\
     -H "Content-Type: application/json" \\
     -d '{"feedback_limit": 5000}'
   
   # Check status
   curl http://localhost:5000/api/training/status/<job_id>
   
   # Get model info
   curl http://localhost:5000/api/training/models

2. MANUAL TRAINING IN PYTHON:

   from backend.services.ml_training_service import MLTrainingService
   
   result = MLTrainingService.train_models(feedback_limit=5000)
   print(result)

3. APPLY LEARNED CORRECTIONS:

   # Models are automatically applied when:
   # - Re-extracting vouchers (GET /api/re_extract)
   # - Processing new uploads

4. MONITOR TRAINING:
   
   from backend.services.ml_training_service import MLTrainingService
   
   status = MLTrainingService.get_training_status()
   print(f"Models available: OCR={status['ocr_model_available']}, Parsing={status['parsing_model_available']}")

5. VIEW STATISTICS:

   from backend.ml_models.ml_correction_model import OCRCorrectionModel
   
   model = OCRCorrectionModel()
   model.load_model()
   print(model.get_stats())

For more details, see ML_TRAINING_GUIDE.md
""")

if __name__ == '__main__':
    success = init_ml_system()
    show_usage()
    sys.exit(0 if success else 1)
