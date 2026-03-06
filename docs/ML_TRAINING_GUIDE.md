# ML-Based OCR & Parsing Improvement System

## Overview

The system now includes a machine learning feedback loop that learns from user corrections and improves OCR extraction and parsing over time. This allows the application to get smarter with each validated voucher.

## Architecture

### 1. **ML Correction Models** (`backend/ml_models/ml_correction_model.py`)

#### OCRCorrectionModel
- **Purpose**: Learns common OCR error patterns (e.g., "3" → "m", "SuppNane" → "Supp Name")
- **Learning Method**: 
  - Tracks character-level replacements with frequency counts
  - Identifies word-level substitutions
  - Builds confidence scores based on error frequency
- **Output**: Applied corrections with confidence scores

#### ParsingCorrectionModel  
- **Purpose**: Learns parsing mistakes from extracted OCR (e.g., extracting "AS" instead of "TK" as supplier)
- **Learning Method**:
  - Captures context around extraction mistakes
  - Associates context patterns with correct values
  - Builds field-specific correction rules
- **Output**: Field-specific suggestions with context-awareness

### 2. **ML Training Service** (`backend/services/ml_training_service.py`)

Orchestrates the complete training pipeline:

```python
# Training workflow
1. Collect validated vouchers from database
2. Extract training samples (where auto != corrected)
3. Initialize OCR and Parsing models
4. Train models from collected feedback
5. Save trained models to disk
6. Apply learned corrections to new extractions
```

### 3. **Training API Routes** (`backend/routes/api_training.py`)

New endpoints for managing ML training:

#### `POST /api/training/start`
Starts a background training job

**Request:**
```json
{
  "feedback_limit": 5000  // Optional: limit training samples
}
```

**Response:**
```json
{
  "success": true,
  "job_id": "job_1234567890",
  "message": "Training job started",
  "eta_seconds": 600
}
```

#### `GET /api/training/status/<job_id>`
Check training job progress

**Response:**
```json
{
  "success": true,
  "job_id": "job_1234567890",
  "status": "training|completed|failed",
  "progress": 45,
  "message": "Processing training data...",
  "result": {
    "status": "success",
    "training_time": 12.5,
    "total_samples": 342,
    "ocr_model_stats": {...},
    "parsing_model_stats": {...}
  }
}
```

#### `GET /api/training/status`
Get current training status (models available, last trained)

#### `GET /api/training/models`
Get detailed information about trained models

## How It Works

### Phase 1: Feedback Collection

When a user validates a voucher:
1. System captures original OCR text
2. System captures auto-extracted data
3. User makes corrections
4. Corrections are saved to database
5. Differences are logged for training

### Phase 2: Model Training

When training is triggered:
1. System collects all validated vouchers
2. Identifies cases where auto extraction ≠ user correction
3. OCR model learns character/word substitution patterns
4. Parsing model learns context-specific extraction improvements
5. Models are saved to `backend/ml_models/`

### Phase 3: Inference (Applied Automatically)

For new vouchers (when re-extraction happens):
1. Raw OCR text is processed
2. Learned OCR corrections are applied (if models available)
3. Parser extracts fields from corrected text
4. Parsing suggestions are applied (if models available)
5. Confidence scores guide user validation

## Integration Points

### In OCR Processing
When `extract_text_default()` is called, learned OCR corrections can be applied.

### In Parsing
When `parse_receipt_text()` is called, learned parsing suggestions can enhance results.

### In Validation
When user saves validated data, corrections are automatically tracked for future training.

## Usage Examples

### 1. Trigger Training from Python
```python
from backend.services.ml_training_service import MLTrainingService

# Train models from validated vouchers
result = MLTrainingService.train_models(
    feedback_limit=5000,  # Use last 5000 validated vouchers
    save_models=True
)

print(f"Training completed: {result['training_time']}s")
print(f"OCR patterns learned: {result['ocr_model_stats']['total_ocr_patterns']}")
print(f"Parsing corrections learned: {result['parsing_samples']}")
```

### 2. Trigger Training from API
```bash
# Start training job
curl -X POST http://localhost:5000/api/training/start \
  -H "Content-Type: application/json" \
  -d '{"feedback_limit": 3000}'

# Check status
curl http://localhost:5000/api/training/status/<job_id>

# Get model info
curl http://localhost:5000/api/training/models
```

### 3. Apply Learned Corrections
```python
from backend.services.ml_training_service import MLTrainingService

# Get auto-extracted data
parsed_data = parse_receipt_text(raw_ocr)

# Apply learned corrections
improved_data = MLTrainingService.apply_learned_corrections(
    parsed_data,
    raw_ocr
)

# Now improved_data includes suggestions from learned models
if 'supplier_name_suggestion' in improved_data['master']:
    print(f"Suggested correction: {improved_data['master']['supplier_name_suggestion']}")
    print(f"Confidence: {improved_data['master']['supplier_name_confidence']}")
```

## Data Flow Example: Supplier Name Correction

### Initial Problem (Before ML)
```
OCR Text: "TK\nSuppNane"
         ↓ (text_correction applied)
         "TK\nSupp Name"
         ↓ (parser extracts)
         supplier_name = "AS" (WRONG!)
         
User corrects to: "TK"
```

### After ML Training
```
1. System learns: "SuppNane" → "Supp Name" (OCR correction)
2. System learns: In context of "TK\nSupp Name" → supplier = "TK" (parsing correction)

Next time same pattern appears:
OCR Text: "TK\nSuppNane"
         ↓ (learned OCR correction applied)
         "TK\nSupp Name"
         ↓ (learned parsing context applied)
         supplier_name = "TK" (CORRECT!)
         confidence = 0.95
```

## File Locations

- **Models**: `backend/ml_models/ocr_corrections_model.json`, `backend/ml_models/parsing_corrections_model.json`
- **Dataset**: `backend/ml_dataset/images/`, `backend/ml_dataset/annotations.jsonl`
- **Training Logs**: Check Flask app logs
- **Training Code**: `backend/ml_models/ml_correction_model.py`
- **Training Service**: `backend/services/ml_training_service.py`
- **Training Routes**: `backend/routes/api_training.py`

## Configuration Recommendations

### Training Frequency
- **Recommendation**: Train after every 50-100 validated vouchers
- **Or**: Weekly batch training from accumulated feedback
- **Or**: On-demand via admin dashboard when ready

### Confidence Thresholds
- Adjust in `ParsingCorrectionModel.get_correction_suggestion()`: currently 0.7 (70%)
- Higher = more conservative suggestions
- Lower = more aggressive suggestions

### Sample Size
- **Minimum**: 100 validated vouchers for meaningful training
- **Optimal**: 1000+ samples for robust learning
- **Maximum**: No hard limit, but diminishing returns after 10,000

## Advanced: Custom Training Logic

You can extend the models for custom field types:

```python
from backend.ml_models.ml_correction_model import OCRCorrectionModel

model = OCRCorrectionModel()

# Train on custom field
model.learn_from_correction(
    raw_ocr="Invoice123",
    auto_extracted="Invoice123",
    user_corrected="INV-123",
    field_name="invoice_id"
)

# Get suggestions
corrected = model.apply_correction("Invoice456")  # May suggest "INV-456"

# Save for later use
model.save_model('custom_ocr_model.json')
```

## Monitoring & Metrics

Check training effectiveness:

```python
from backend.services.ml_training_service import MLTrainingService

status = MLTrainingService.get_training_status()

print(f"OCR Patterns learned: {status['ocr_stats']['total_ocr_patterns']}")
print(f"Fields with parsing rules: {status['parsing_fields']}")
print(f"Last trained: {status['last_trained']}")
```

## Future Enhancements

1. **Deep Learning Integration**: Add neural networks for complex pattern learning
2. **Transfer Learning**: Use pre-trained models from similar domains
3. **Active Learning**: Identify and request user feedback on uncertain cases
4. **A/B Testing**: Compare model versions on production data
5. **Federated Learning**: Combine learning from multiple instances
6. **Confidence Calibration**: Better confidence scoring for model suggestions

## Troubleshooting

### Models not improving
- Check if corrections are being saved (validation_status='VALIDATED')
- Ensure training samples have meaningful differences (auto ≠ corrected)
- Try with more feedback_limit (e.g., 10000)

### Training takes too long
- Reduce feedback_limit
- Run training off-peak
- Implement batch processing with Celery

### Models not being applied
- Check if model files exist in `backend/ml_models/`
- Verify models loaded successfully with `MLTrainingService.get_training_status()`
- Check logs for load errors

## Database Schema

The feedback is tracked through validated vouchers:
- `vouchers_master.validation_status = 'VALIDATED'`
- Differences between `parsed_json` and user-corrected values are used as training data

Optional: Create dedicated feedback table for more detailed tracking:
```sql
CREATE TABLE ml_training_feedback (
    id SERIAL PRIMARY KEY,
    voucher_id INTEGER REFERENCES vouchers_master(id),
    field_name VARCHAR(50),
    raw_ocr_excerpt TEXT,
    auto_extracted TEXT,
    user_corrected TEXT,
    field_type VARCHAR(20),  -- 'master', 'item', 'deduction'
    created_at TIMESTAMP DEFAULT NOW()
);
```
