#!/usr/bin/env python
"""Test the ML training with current data"""

from backend import create_app
from backend.services.ml_training_service import MLTrainingService
import json

app = create_app()
with app.app_context():
    # Collect training data
    training_data = MLTrainingService.collect_training_data(limit=100)
    
    print("Training Data Collection Results:")
    print(f"  OCR Corrections: {len(training_data.get('ocr_corrections', []))}")
    print(f"  Parsing Corrections: {len(training_data.get('parsing_corrections', []))}")
    print(f"  Source Breakdown: {training_data.get('source_breakdown', {})}")
    
    # Show first few corrections if any
    parsing_corr = training_data.get('parsing_corrections', [])
    if parsing_corr:
        print(f"\nFirst correction example:")
        sample = parsing_corr[0]
        print(f"  Field: {sample.get('field')}")
        print(f"  Auto-detected: {sample.get('auto')}")
        print(f"  User corrected to: {sample.get('corrected')}")
        print(f"  Raw OCR: {sample.get('raw_ocr')[:100] if sample.get('raw_ocr') else 'None'}...")
    else:
        print("\nNo parsing corrections found yet.")
        print("This means either:")
        print("  1. No vouchers have been validated yet")
        print("  2. The validated vouchers don't have corrections (auto-parse matches manual input)")
        print("  3. The corrections haven't been saved with original OCR data")
