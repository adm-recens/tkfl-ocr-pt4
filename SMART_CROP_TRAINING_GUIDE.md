# Smart Crop Model Training Implementation

## Overview

Smart Crop training has been fully implemented alongside OCR and Parsing model training. The system now learns from user crop corrections to improve automatic receipt boundary detection.

---

## How Smart Crop Training Works

### **Data Collection Phase**

When users manually adjust crop boundaries in the batch workflow:

```
User uploads image
  ↓
Auto-detect crops receipt (SmartReceiptDetector)
  ↓
User manually adjusts/corrects crop area
  ↓
Crop coordinates saved as feedback
  ↓
Added to training data for Smart Crop model
```

**Stored in:** `backend/ml_dataset/feedback/` (JSONL format)

### **Training Phase**

When you click "Start ML Training":

```
1. Collect crop feedback (user-corrected crops)
2. Extract crop patterns:
   - Average width/height learned from user crops
   - Aspect ratios of typical receipts
   - Position distributions
   - Variation statistics
3. Save as Smart Crop Model
4. Model ready for next batch!
```

### **Application Phase**

When processing new receipts:

```
New image auto-detected
  ↓
Auto-crop vs learned patterns compared
  ↓
If learned patterns suggest better crop → Suggest adjustment
  ↓
User sees SmartCrop suggestion (with confidence)
  ↓
Continue processing or accept suggestion
```

---

## Technical Architecture

### **SmartCropTrainingService** (New)

**File:** `backend/services/smart_crop_training_service.py`

#### Key Methods:

**`collect_crop_training_data(limit)`**
- Gathers user-corrected crop coordinates
- Returns training examples with crop statistics
- Calculates average correction magnitude

**`train_smart_crop_model(data_limit)`**
- Analyzes crop patterns from collected data
- Extracts statistical insights:
  - Average crop dimensions
  - Standard deviation (variation)
  - Aspect ratios
  - Position distribution
- Saves trained model to JSON

**`get_training_status()`**
- Returns current model availability
- Shows training samples count
- Displays learned patterns

**`load_model()`**
- Loads trained smart crop model from disk
- Returns model data or None

**`apply_learned_crop_suggestions(image_shape, auto_detected_crop)`**
- Compares auto-detected crop against learned patterns
- Suggests improvements if deviation is significant
- Returns confidence level

---

## Data Flow Integration

### **In Batch Workflow**

```
api_queue.py: save_crop()
  ↓
MLFeedbackService.save_crop_feedback()
  ↓
backend/ml_dataset/images/         (original full images)
backend/ml_dataset/annotations.jsonl  (crop coordinates)
```

**Example feedback stored:**
```json
{
  "id": "uuid-1234",
  "timestamp": "2026-01-27T14:30:00",
  "original_filename": "receipt.jpg",
  "stored_image_name": "uuid-1234.jpg",
  "user_crop": {
    "x": 45,
    "y": 120,
    "width": 310,
    "height": 680,
    "rotate": 0,
    "scaleX": 1,
    "scaleY": 1
  }
}
```

### **In ML Training**

**File:** `backend/services/ml_training_service.py`

```python
# train_models() now includes smart crop:

result = MLTrainingService.train_models(
    feedback_limit=5000,
    include_smart_crop=True  # NEW parameter
)

# Returns:
{
    'status': 'success',
    'ocr_model_stats': {...},
    'parsing_model_stats': {...},
    'smart_crop_stats': {        # NEW
        'training_samples': 87,
        'patterns_learned': 2,   # dimensions + position
        'avg_crop_size': {'width': 320, 'height': 710, ...},
        'crop_variations': {'width_std': 25, 'height_std': 45, ...}
    },
    'training_time': 12.5
}
```

---

## Learned Patterns

### **Pattern 1: Average Dimensions**

Learns typical receipt crop size from your corrections:

```json
{
  "pattern_type": "average_dimensions",
  "avg_width": 320.5,
  "avg_height": 710.3,
  "std_width": 25.4,        // variation in width
  "std_height": 45.2,       // variation in height
  "typical_aspect_ratio": 0.45,
  "width_range": [250, 400],
  "height_range": [600, 850]
}
```

**Application:** If auto-detect suggests 250×500 crop but learned data shows typical crops are 320×710, system can suggest adjustment.

### **Pattern 2: Position Distribution**

Learns where receipts typically appear in your images:

```json
{
  "pattern_type": "position_distribution",
  "avg_x": 35.2,      // average X position
  "avg_y": 110.5,     // average Y position
  "std_x": 15.3,      // variation in X
  "std_y": 25.7,      // variation in Y
  "x_range": [0, 100],
  "y_range": [50, 300]
}
```

**Application:** Can pre-position crop area based on where receipts typically appear.

---

## Training Dashboard Updates

### **In `/training` Page**

**New Status Card:**
```
Smart Crop Model Status
✓ Active
Samples: 87
```

**Training Results (After Training):**
```
Smart Crop Model:
- Crop Samples Trained: 87
- Patterns Learned: 2
```

---

## Configuration

### **In ML Training Service**

```python
# Include/exclude smart crop from training
MLTrainingService.train_models(
    feedback_limit=5000,
    include_smart_crop=True   # Can set to False to skip
)
```

### **Smart Crop Model Storage**

```
Location: backend/ml_models/smart_crop_model.json

Size: ~2-5 KB (just patterns, no heavy model)

Contains:
- Version information
- Training metadata
- Learned crop patterns
- Statistics (mean, std dev, ranges)
```

---

## Typical Usage Scenario

### **Week 1: Initial Deployment**
- Users crop 50-100 images manually
- Feedback data collected: 100 crop examples
- Models untrained: Cannot improve auto-detect yet

### **Week 2: First Training**
- Run training: `MLTrainingService.train_models()`
- Smart Crop trains on 100 crop examples
- Learns average crop size: 320×710
- Learns typical position: (35, 110)

### **Week 3: Second Batch**
- New receipts processed
- Auto-detect suggests 280×650 crop
- Smart Crop model compares:
  - Learned average: 320×710
  - Suggested: 280×650
  - Deviation > 10% → **Suggests adjustment to 320×710**
- User sees suggestion, accepts or rejects

### **Week 4+: Continuous Improvement**
- Model refines with each batch
- Learns variations and edge cases
- Auto-detect suggestions become better
- User corrections needed less frequently

---

## Accuracy Metrics

Smart Crop learns these metrics:

```
Coefficient of Variation (CV) by dimension:
- Width CV: std_width / avg_width  (0.08 = 8% variation)
- Height CV: std_height / avg_height

Example:
  avg_width: 320, std_width: 25 → CV = 0.078 (low variation)
  avg_height: 710, std_height: 45 → CV = 0.063 (low variation)

Interpretation:
  CV < 0.1: Very consistent crop sizes
  CV 0.1-0.2: Moderate consistency
  CV > 0.2: High variation in crops
```

---

## Monitoring Training Progress

### **Before Training**
```
Smart Crop Model Status: ○ Not Trained
```

### **During Training**
```
Training in progress...
Job ID: job_12345
Progress: 45%
```

### **After Training**
```
Smart Crop Model: ✓ Active
Crop Samples Trained: 87
Patterns Learned: 2

Training Results:
- Crop Samples Trained: 87
- Patterns Learned: 2
- Average crop size: 320×710 px
- Width variation: 25 px (8%)
- Height variation: 45 px (6%)
```

---

## Implementation Details

### **Files Added/Modified**

**New Files:**
- `backend/services/smart_crop_training_service.py` (NEW)

**Modified Files:**
- `backend/services/ml_training_service.py` - Added SmartCrop integration
- `backend/templates/training.html` - Added UI elements
- `backend/routes/main.py` - Already had crop feedback capture

### **Backward Compatibility**

✅ **Fully backward compatible**
- Old systems without smart crop still work
- Parameter `include_smart_crop=True` by default
- Can disable with `include_smart_crop=False`

---

## Error Handling

If smart crop training fails:

```python
try:
    result = SmartCropTrainingService.train_smart_crop_model()
except Exception as e:
    # Logged but doesn't block OCR/Parsing training
    result['smart_crop_stats'] = {'error': str(e)}
```

Users still get OCR/Parsing improvements even if Smart Crop fails.

---

## Testing Smart Crop Training

### **Manual Test**
```python
from backend.services.smart_crop_training_service import SmartCropTrainingService

# Check if crop data exists
data = SmartCropTrainingService.collect_crop_training_data()
print(f"Crop examples: {len(data['training_examples'])}")

# Train model
result = SmartCropTrainingService.train_smart_crop_model()
print(result['message'])
print(result['model_stats'])

# Check status
status = SmartCropTrainingService.get_training_status()
print(f"Model available: {status['model_available']}")
```

### **UI Test**
1. Go to `/training` page
2. Look for "Smart Crop Model Status" card
3. Run training via dashboard
4. Check results include Smart Crop stats

---

## Summary

| Feature | Status |
|---------|--------|
| Crop data collection | ✅ Automatic |
| Pattern extraction | ✅ Implemented |
| Model training | ✅ Fully integrated |
| Dashboard display | ✅ Updated |
| Suggestion system | ✅ Ready to integrate |
| Error handling | ✅ Complete |
| Backward compatibility | ✅ Full |

Smart Crop training is **production-ready** and integrated into the ML training pipeline!

