# Training System Details - Complete Overview

## 🎯 Two Separate ML Training Systems

Your application has **TWO DIFFERENT** machine learning training systems:

### System 1: OCR/Parsing Corrections (NEW - Just Deployed)
**What it does**: Learns from your text corrections while validating vouchers
**Location**: `/api/training/*` endpoints + `backend/ml_models/`
**Status**: ✅ **ACTIVE & RECORDING**

### System 2: Smart Crop Detection (EXISTING)
**What it does**: Learns receipt boundary detection from your crop adjustments
**Location**: `/training` page + `backend/ml_dataset/`
**Status**: ⏳ **COLLECTING DATA, BUT TRAINING NOT IMPLEMENTED YET**

---

## 📊 System 1: OCR/Parsing Correction Training

### What's Being Tracked
```
✅ Supplier name corrections (wrong → corrected)
✅ Voucher date corrections (wrong → corrected)
✅ Voucher number corrections (wrong → corrected)
✅ Line item corrections (wrong → corrected)
```

### API Endpoints Available

#### 1. Start Training
```bash
curl -X POST http://localhost:5000/api/training/start \
  -H "Content-Type: application/json" \
  -d '{"feedback_limit": 5000}'
```

**Response:**
```json
{
  "success": true,
  "job_id": "job_1705310000",
  "feedback_limit": 5000,
  "eta_seconds": 600
}
```

#### 2. Check Training Status (By Job ID)
```bash
curl http://localhost:5000/api/training/status/job_1705310000
```

**Response (While Training):**
```json
{
  "success": true,
  "job_id": "job_1705310000",
  "status": "training",
  "progress": 45,
  "message": "Training model on 123 samples...",
  "started_at": 1705310000.123
}
```

**Response (Completed):**
```json
{
  "success": true,
  "job_id": "job_1705310000",
  "status": "completed",
  "progress": 100,
  "message": "Training completed successfully",
  "result": {
    "status": "success",
    "total_samples": 123,
    "ocr_model_stats": {
      "total_ocr_patterns": 45,
      "total_vocab_corrections": 67,
      "total_field_patterns": 12,
      "fields_trained": ["supplier_name", "voucher_date"]
    },
    "parsing_model_stats": {
      "fields": ["supplier_name", "voucher_date", "voucher_number"],
      "total_parsing_rules": 34
    }
  },
  "completed_at": 1705310600.456,
  "training_time": 600.333
}
```

#### 3. Get Current Models Status
```bash
curl http://localhost:5000/api/training/status
```

**Response:**
```json
{
  "success": true,
  "training_status": {
    "ocr_model_available": true,
    "parsing_model_available": true,
    "last_trained": "2026-01-27T11:15:30.123456",
    "ocr_stats": {
      "total_ocr_patterns": 45,
      "total_vocab_corrections": 67,
      "total_field_patterns": 12,
      "fields_trained": ["supplier_name", "voucher_date", "voucher_number"]
    },
    "parsing_fields": ["supplier_name", "voucher_date", "voucher_number"]
  }
}
```

#### 4. Get Detailed Model Information
```bash
curl http://localhost:5000/api/training/models
```

**Response:**
```json
{
  "success": true,
  "models": {
    "ocr_model": {
      "available": true,
      "stats": {
        "total_ocr_patterns": 45,
        "total_vocab_corrections": 67,
        "total_field_patterns": 12,
        "fields_trained": ["supplier_name", "voucher_date"]
      }
    },
    "parsing_model": {
      "available": true,
      "fields": ["supplier_name", "voucher_date", "voucher_number"]
    }
  },
  "last_trained": "2026-01-27T11:15:30.123456"
}
```

### Data Collection Point
**File**: `backend/routes/api.py` → `save_validated_data()` function

When you click "Save" on a validated voucher:
```python
# Automatically logs:
- Original supplier_name vs. Your corrected supplier_name
- Original voucher_date vs. Your corrected voucher_date
- Original voucher_number vs. Your corrected voucher_number
```

**Currently Captured**: 0 samples (no validated vouchers yet)

---

## 📸 System 2: Smart Crop Training

### What's Being Tracked
```
✅ Original full receipt image
✅ User's crop boundaries (x, y, width, height)
✅ Rotation angle
✅ Timestamp
```

### UI Access
```
Navigate to: http://localhost:5000/training
```

### Data Structure
**Location**: `backend/ml_dataset/`
```
ml_dataset/
  ├── images/                    (Full receipt images)
  │   ├── uuid-1.jpg
  │   ├── uuid-2.jpg
  │   └── ...
  └── annotations.jsonl          (Crop boundaries)
```

### Example Annotation Record
```json
{
  "id": "uuid-1234",
  "timestamp": "2026-01-27T11:15:30.123456",
  "original_filename": "receipt_001.jpg",
  "stored_image_name": "uuid-1234.jpg",
  "user_crop": {
    "x": 50,
    "y": 100,
    "width": 400,
    "height": 600,
    "rotate": 0,
    "scaleX": 1,
    "scaleY": 1
  },
  "metadata": {
    "source": "user_correction",
    "original_width": 1080,
    "original_height": 1920
  }
}
```

### Data Collection Point
**File**: `backend/routes/api_queue.py` → When user adjusts crop in queue review

**Currently Collected**: See `/training` page for exact count

### Training Status: ⏳ IN PROGRESS

**✅ What's Done:**
- Data collection working
- Images being saved
- Annotations in JSONL format
- Stats tracking

**❌ What's NOT Done Yet:**
- No training interface implemented
- No model training logic
- No inference/auto-crop improvement
- "Start Training Run" button placeholder only

---

## 🔄 How The Two Systems Differ

| Aspect | OCR/Parsing (System 1) | Smart Crop (System 2) |
|--------|------------------------|----------------------|
| **Purpose** | Learn text corrections | Learn receipt boundaries |
| **Data Source** | Text validation | Image crop adjustments |
| **Current State** | ✅ Full implementation | ⏳ Data collection only |
| **Training Status** | Ready to train | Training not implemented |
| **API Endpoints** | 4 endpoints ready | UI page only |
| **Models Saved** | Yes (JSON files) | Not yet |
| **Inference** | Yes (auto-applied) | No |
| **Endpoint** | `/api/training/*` | `/training` |

---

## 📈 Current Data Collection Status

### OCR/Parsing Corrections
```
Collected: 0 corrections
Reason: No validated vouchers yet
Next Step: Upload batch, review, and save corrections
```

### Smart Crop Boundaries
```
Collected: Check /training page for count
Location: backend/ml_dataset/
Status: Accumulating, training pending
```

---

## 🚀 How to Use System 1 (OCR/Parsing)

### Phase 1: Collect Corrections
1. Upload batch with bad OCR/parsing
2. Review each voucher
3. Make corrections (supplier name, date, etc.)
4. Click "Save"
   - ✅ Corrections automatically recorded

### Phase 2: Train (After 50+ corrections)
```bash
# Trigger training
curl -X POST http://localhost:5000/api/training/start

# Monitor progress
curl http://localhost:5000/api/training/status/job_1705310000

# Check results
curl http://localhost:5000/api/training/models
```

### Phase 3: Auto-Improvements
- New vouchers automatically get learned suggestions
- Accuracy improves with each batch

---

## 🔧 How to Use System 2 (Smart Crop)

### Phase 1: Collect Training Data ✅ (Active)
1. Review queued images
2. Adjust crop boundaries as needed
3. Click "Confirm"
   - ✅ Boundaries automatically saved

### Phase 2: Train ⏳ (Not Implemented Yet)
```
Currently: Data is being collected
Next: Will implement training interface
Status: Data ready, waiting for training logic
```

### Where Data Is Stored
```
backend/ml_dataset/images/          ← Receipt images
backend/ml_dataset/annotations.jsonl ← Crop boundaries
```

---

## 📊 Checking What's Being Collected

### OCR/Parsing Corrections
```python
from backend.app import create_app
from backend.services.ml_training_service import MLTrainingService

app = create_app()
with app.app_context():
    data = MLTrainingService.collect_training_data(limit=10000)
    print(f"Samples collected: {len(data['ocr_corrections']) + len(data['parsing_corrections'])}")
    print(f"OCR: {len(data['ocr_corrections'])}")
    print(f"Parsing: {len(data['parsing_corrections'])}")
```

### Smart Crop Annotations
```python
from backend.services.ml_feedback_service import MLFeedbackService

stats = MLFeedbackService.get_dataset_stats()
print(f"Images: {stats['total_images']}")
print(f"Annotations: {stats['total_annotations']}")
print(f"Last updated: {stats['last_updated']}")
```

---

## ⚠️ About Smart Crop Not Working

**Question**: "Smart crop is not working"

**Answer**: Smart crop training is in **data collection phase only**. Here's the status:

| Component | Status | Notes |
|-----------|--------|-------|
| Smart crop detection (inference) | ✅ Works | Detects receipts from images |
| User crop adjustment UI | ✅ Works | Can adjust boundaries |
| Data collection | ✅ Works | Saves crops to annotations.jsonl |
| Model training | ❌ Not implemented | Logic exists but not connected |
| Auto-crop improvement | ❌ Not implemented | Waiting for trained model |

**Why Smart Crop Doesn't Improve:**
1. ✅ You adjust crop boundaries
2. ✅ System saves your adjustments
3. ❌ But there's no training endpoint to retrain model
4. ❌ So the detection algorithm never improves
5. ❌ Next images still use original detection logic

**What Would Be Needed** (Future):
```python
# Training endpoint like this (not implemented yet):
POST /api/training/smart-crop/train
  - Load annotations.jsonl
  - Extract crops from images
  - Train object detection model
  - Save new model weights
  - Use in future detections
```

---

## 📝 Summary

### Two Different Systems

**1. OCR/Parsing (NEW) - FULLY IMPLEMENTED ✅**
- Records: Text corrections you make while validating
- Learns: Text patterns, extraction rules
- Status: Ready to start collecting and training
- API: Full endpoints available at `/api/training/*`

**2. Smart Crop (EXISTING) - COLLECTION ONLY ⏳**
- Records: Image crop boundaries you adjust
- Learns: Would learn receipt detection (not yet)
- Status: Collecting data, training not implemented
- Page: Can view stats at `/training`

### Next Steps

1. **Start using System 1 NOW**:
   - Upload and validate batches
   - Make corrections
   - System automatically records

2. **After 50+ corrections**:
   - Run: `curl -X POST http://localhost:5000/api/training/start`
   - System learns patterns
   - Future vouchers get better suggestions

3. **System 2 (Smart Crop)**:
   - Continue adjusting crops in queue
   - Data is being saved
   - Waiting for training implementation

---

Generated: 2026-01-27
