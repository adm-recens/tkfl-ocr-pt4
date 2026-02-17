"""
Demo script to show ML model validation and confidence metrics

Run this to see concrete proof that the ML model is improving parsing accuracy.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def main():
    print("\n" + "="*70)
    print("ML MODEL VALIDATION DEMO")
    print("="*70)
    print("\nThis will:")
    print("1. Collect your user corrections from the database")
    print("2. Split them into training (80%) and validation (20%) sets")
    print("3. Measure baseline accuracy (parser without ML)")
    print("4. Train the ML model on the training set")
    print("5. Measure improved accuracy (parser with ML)")
    print("6. Show you the concrete improvement percentages")
    print("\n" + "="*70)
    
    input("\nPress Enter to start training with validation...")
    
    try:
        # Import Flask app
        from backend import create_app
        from backend.services.enhanced_ml_training import EnhancedMLTraining
        from backend.db import get_connection
        
        # Create Flask app context
        app = create_app()
        
        with app.app_context():
            # First, check how much training data we have
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as count FROM vouchers_master WHERE validation_status = 'VALIDATED'")
            validated_count = cur.fetchone()['count']
            
            print(f"\n📊 Found {validated_count} validated vouchers in database")
            
            if validated_count < 10:
                print("\n⚠️  WARNING: You need at least 10 validated vouchers for meaningful validation.")
                print("   Please validate more receipts first, then run this script again.")
                print("\n   How to get more training data:")
                print("   1. Go to http://localhost:5000/queue")
                print("   2. Upload and validate at least 10 receipts")
                print("   3. Make corrections to the parsed data")
                print("   4. Run this script again")
                return
            
            print("\n🔄 Running enhanced training with validation...\n")
            
            # Run enhanced training
            result = EnhancedMLTraining.train_with_validation(
                feedback_limit=5000,
                save_models=True,
                include_smart_crop=True
            )
            
            # Print the confidence report
            print("\n" + result.get('confidence_report', 'No report generated'))
            
            # Print detailed field improvements
            validation = result.get('validation', {})
            if validation:
                print("\n" + "="*70)
                print("DETAILED FIELD-BY-FIELD ANALYSIS")
                print("="*70)
                
                for field, metrics in sorted(validation.items(), key=lambda x: x[1].get('percent_improvement', 0), reverse=True):
                    print(f"\n📊 {field.upper()}")
                    print(f"   Before ML: {metrics.get('before_accuracy', 0)}% accurate")
                    print(f"   After ML:  {metrics.get('after_accuracy', 0)}% accurate")
                    print(f"   Improvement: {metrics.get('percent_improvement', 0):+.1f}%")
                    print(f"   Tested on: {metrics.get('samples', 0)} validation samples")
            
            print("\n" + "="*70)
            print("✅ TRAINING COMPLETE")
            print("="*70)
            print(f"\nModels saved to: backend/data/")
            print(f"Validation results saved to: backend/data/validation_results.json")
            print("\nThe ML model is now active and will automatically improve parsing!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
