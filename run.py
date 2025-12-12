"""
Simple run script for the OCR application
This avoids PATH and virtual environment issues
"""
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend import create_app

if __name__ == "__main__":
    app = create_app()
    print("\n" + "="*60)
    print("🚀 OCR Application Starting...")
    print("="*60)
    print("\n📍 Access the application at: http://localhost:5000")
    print("\n✅ New Features Active:")
    print("   - Optimal OCR Mode (92%+ confidence)")
    print("   - Enhanced Parser with Auto-Correction")
    print("   - Validation Warnings & Alerts")
    print("\n⏹️  Press Ctrl+C to stop the server\n")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
