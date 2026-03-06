# ML Training System - Quick Start Guide

## 30-Second Overview

Your OCR/Parsing system now **learns from user corrections** and improves automatically.

```
User corrects voucher → System learns pattern → Future vouchers get suggested corrections → System gets smarter
```

## Getting Started (5 minutes)

### Step 1: Initialize Models
```bash
cd /path/to/tkfl_ocr/pt5
python init_ml_training.py
```

This trains initial models from your existing validated vouchers.

### Step 2: Trigger Training via API
```bash
# Start training
curl -X POST http://localhost:5000/api/training/start \
  -H "Content-Type: application/json" \
  -d '{"feedback_limit": 1000}'

# Check progress
curl http://localhost:5000/api/training/status/<job_id>

# View model info
curl http://localhost:5000/api/training/models
```

Or in Python:
```python
from backend.services.ml_training_service import MLTrainingService

# Train models
result = MLTrainingService.train_models(feedback_limit=1000)
print(f"Training complete: {result['status']}")

# Check status
status = MLTrainingService.get_training_status()
print(f"OCR model available: {status['ocr_model_available']}")
print(f"Parsing model available: {status['parsing_model_available']}")
```

### Step 3: System Automatically Learns
That's it! When users validate vouchers, the system automatically:
1. Captures their corrections
2. Stores them for training
3. Uses them to improve future extractions

## Recommended Workflow

### Weekly
```python
# Retrain after ~100 new validated vouchers
from backend.services.ml_training_service import MLTrainingService

result = MLTrainingService.train_models(feedback_limit=5000)
if result['status'] == 'success':
    print(f"✓ Trained on {result['total_samples']} samples")
```

### Monthly
- Review model performance
- Adjust confidence thresholds if needed
- Archive old models if desired

## What Gets Learned

### OCR Patterns
```
Example: "SuppNane" appears in 50 vouchers
         User corrects to "Supp Name" each time
         Model learns: 100% should be "Supp Name"
```

### Parsing Patterns
```
Example: Voucher shows "TK" on line 7, "Supp Name" on line 8
         Parser extracts "AS" (wrong)
         User corrects to "TK"
         Model learns: In this context → use "TK"
```

## Expected Results

| Time | Improvement |
|------|-------------|
| After 1st training | Baseline - learn common patterns |
| After 1 week | 10-20% fewer manual corrections needed |
| After 1 month | 30-50% reduction in correction work |
| After 3 months | 50-70% system accuracy without user fixes |

## API Reference

### Training Endpoints

**Start Training**
```
POST /api/training/start
Body: {"feedback_limit": 5000}  // optional
Returns: {"job_id": "...", "eta_seconds": 600}
```

**Check Training Progress**
```
GET /api/training/status/<job_id>
Returns: {
  "status": "training|completed|failed",
  "progress": 0-100,
  "message": "...",
  "result": {... if completed ...}
}
```

**Get Current Model Status**
```
GET /api/training/status
Returns: {
  "ocr_model_available": true,
  "parsing_model_available": true,
  "last_trained": "2024-01-27T10:30:00"
}
```

**Get Model Details**
```
GET /api/training/models
Returns: {
  "models": {
    "ocr_model": {"available": true, "stats": {...}},
    "parsing_model": {"available": true, "fields": [...]}
  }
}
```

## Code Examples

### Example 1: Train and Check Status
```python
from backend.services.ml_training_service import MLTrainingService

# Train
print("Training models...")
result = MLTrainingService.train_models(feedback_limit=1000)

print(f"✓ {result['total_samples']} samples trained")
print(f"✓ {result['training_time']:.2f} seconds")

# Check
status = MLTrainingService.get_training_status()
print(f"✓ OCR patterns learned: {status['ocr_stats']['total_ocr_patterns']}")
print(f"✓ Parsing fields: {len(status['parsing_fields'])}")
```

### Example 2: Monitor Model Performance
```python
from backend.services.ml_training_service import MLTrainingService

status = MLTrainingService.get_training_status()

for field in status['parsing_fields']:
    print(f"Field '{field}' has learned patterns")

if status['last_trained']:
    print(f"Last trained: {status['last_trained']}")
else:
    print("Models not yet trained")
```

### Example 3: Use Learned Models
```python
from backend.services.ml_training_service import MLTrainingService
from backend.parser import parse_receipt_text
from backend.text_correction import apply_text_corrections

# Extract normally
raw_ocr = "...OCR text..."
corrected = apply_text_corrections(raw_ocr)
parsed = parse_receipt_text(corrected)

# Apply learned corrections
improved = MLTrainingService.apply_learned_corrections(parsed, raw_ocr)

# Check for suggestions
if 'supplier_name_suggestion' in improved['master']:
    print(f"Suggested: {improved['master']['supplier_name_suggestion']}")
    print(f"Confidence: {improved['master']['supplier_name_confidence']:.0%}")
```

## Files Added

```
backend/
├── ml_models/
│   └── ml_correction_model.py          # ML classes
├── services/
│   └── ml_training_service.py          # Training service
└── routes/
    └── api_training.py                 # REST endpoints (modified)

Root:
├── init_ml_training.py                 # Setup script
├── examples_ml_training.py             # Usage examples
├── ML_TRAINING_GUIDE.md                # Full documentation
└── ML_IMPLEMENTATION_SUMMARY.md        # Implementation details
```

## Troubleshooting

**Q: Models not improving?**
A: Check if vouchers are marked as 'VALIDATED' and have actual corrections.

**Q: Training takes too long?**
A: Use smaller feedback_limit (try 100-500) or run off-peak.

**Q: Models not applying?**
A: Check if model files exist in `backend/ml_models/`. Run `init_ml_training.py` again.

## Configuration

### Adjust Learning Sensitivity
Edit `backend/ml_models/ml_correction_model.py`:
- Line 86: Change `0.7` (70% confidence threshold) to higher/lower

### Change Training Data Source
Edit `backend/services/ml_training_service.py`:
- Line 20: Modify SQL to filter different vouchers

### Custom Fields
Edit `backend/services/ml_training_service.py`:
- Lines 50-70: Add more fields to track

## Next Level: Advanced Usage

See `ML_TRAINING_GUIDE.md` for:
- Custom model training
- Confidence calibration
- Performance monitoring
- Extending to new fields

---

**Questions?** Check:
1. `ML_TRAINING_GUIDE.md` - Complete reference
2. `examples_ml_training.py` - Working code examples
3. `ML_IMPLEMENTATION_SUMMARY.md` - Architecture details

**Ready to train?** Run:
```bash
python init_ml_training.py
```
