# ML Training API - Quick Reference

## 🎯 All Available Endpoints

### 1. OCR/Parsing Correction Training API

#### Start Training Job
```bash
POST /api/training/start
Content-Type: application/json

{
  "feedback_limit": 5000
}
```

**Response:**
```json
{
  "success": true,
  "job_id": "job_1705310000",
  "feedback_limit": 5000,
  "eta_seconds": 600,
  "message": "Training job started"
}
```

---

#### Check Training Progress (By Job ID)
```bash
GET /api/training/status/job_1705310000
```

**Response (In Progress):**
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

**Response (Failed):**
```json
{
  "success": true,
  "job_id": "job_1705310000",
  "status": "failed",
  "error": "No training data available",
  "completed_at": 1705310600.456
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
      "fields_trained": [
        "supplier_name",
        "voucher_date",
        "voucher_number"
      ]
    },
    "parsing_model_stats": {
      "fields": [
        "supplier_name",
        "voucher_date",
        "voucher_number"
      ],
      "total_parsing_rules": 34
    }
  },
  "completed_at": 1705310600.456,
  "training_time": 600.333
}
```

---

#### Get Current Model Status
```bash
GET /api/training/status
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
      "fields_trained": [
        "supplier_name",
        "voucher_date",
        "voucher_number"
      ]
    },
    "parsing_fields": [
      "supplier_name",
      "voucher_date",
      "voucher_number"
    ]
  }
}
```

---

#### Get Detailed Model Information
```bash
GET /api/training/models
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
        "fields_trained": [
          "supplier_name",
          "voucher_date",
          "voucher_number"
        ]
      }
    },
    "parsing_model": {
      "available": true,
      "fields": [
        "supplier_name",
        "voucher_date",
        "voucher_number"
      ]
    }
  },
  "last_trained": "2026-01-27T11:15:30.123456"
}
```

---

### 2. Smart Crop Training (Data Collection Only)

#### View Training Data Status
```
UI Page: http://localhost:5000/training
```

**Shows:**
- Total annotated images
- Total annotations (JSONL records)
- Last updated timestamp

---

## 📋 Common Workflows

### Workflow 1: Train After Collecting Corrections

```bash
# Step 1: Start training
curl -X POST http://localhost:5000/api/training/start \
  -H "Content-Type: application/json" \
  -d '{"feedback_limit": 5000}'

# Returns job_id: job_1705310000

# Step 2: Monitor progress
watch -n 2 'curl http://localhost:5000/api/training/status/job_1705310000 | jq ".result.progress"'

# Step 3: Check results when complete
curl http://localhost:5000/api/training/models | jq ".models"
```

---

### Workflow 2: Check If Models Are Ready

```bash
# Check model availability
curl http://localhost:5000/api/training/status | jq ".training_status.ocr_model_available"

# Expected output:
# true   → Models trained and ready
# false  → No models trained yet
```

---

### Workflow 3: Get Training Details in Python

```python
import requests
import json

# Start training
response = requests.post('http://localhost:5000/api/training/start', 
    json={"feedback_limit": 5000})
job_id = response.json()['job_id']
print(f"Training started: {job_id}")

# Poll for completion
import time
while True:
    status = requests.get(f'http://localhost:5000/api/training/status/{job_id}').json()
    
    if status['status'] == 'completed':
        print(f"Training completed!")
        print(f"Total samples: {status['result']['total_samples']}")
        print(f"OCR patterns: {status['result']['ocr_model_stats']['total_ocr_patterns']}")
        break
    elif status['status'] == 'failed':
        print(f"Training failed: {status['error']}")
        break
    else:
        print(f"Progress: {status['progress']}% - {status['message']}")
        time.sleep(5)

# Get final model info
models = requests.get('http://localhost:5000/api/training/models').json()
print(json.dumps(models, indent=2))
```

---

## 🔍 Understanding Responses

### What Different Status Values Mean

| Status | Meaning | Next Action |
|--------|---------|-------------|
| `queued` | Job waiting to start | Wait a moment, check again |
| `training` | Currently training | Monitor progress |
| `completed` | Successfully finished | Check results in response |
| `failed` | Training failed | Check error message |

### What Fields Trained Means

```
"fields_trained": ["supplier_name", "voucher_date", "voucher_number"]

Means:
- System learned patterns for supplier_name extraction
- System learned patterns for voucher_date extraction
- System learned patterns for voucher_number extraction
```

### What OCR Patterns Means

```
"total_ocr_patterns": 45

Means:
- System learned 45 different text substitution patterns
- Example: "3" → "B", "l" → "1", "SuppNane" → "Supp Name"
- Each pattern has a frequency/confidence score
```

### What Parsing Rules Means

```
"total_parsing_rules": 34

Means:
- System learned 34 context-aware extraction rules
- Example: "TK before Supp Name label" → supplier_name = TK
```

---

## 🚨 Troubleshooting

### Issue: "No training data available"

**Cause**: No corrections have been made yet

**Solution**: 
1. Upload batch
2. Review and correct vouchers
3. Click "Save" on each correction
4. Wait for at least 10 corrections, then train

---

### Issue: Training Job Returns 500 Error

**Cause**: Database connection issue

**Solution**:
1. Verify Flask app is running
2. Check database connection in logs
3. Try again

---

### Issue: Models Show "available: false"

**Cause**: Models haven't been trained yet

**Solution**:
1. Collect training data (50+ corrections recommended)
2. Run: `POST /api/training/start`
3. Wait for training to complete

---

## 📊 Example Full Workflow

```bash
#!/bin/bash

echo "=== ML Training Workflow ==="

# 1. Check current status
echo "1. Checking current model status..."
curl http://localhost:5000/api/training/status | jq .

# 2. Start training
echo "2. Starting training job..."
JOB=$(curl -X POST http://localhost:5000/api/training/start \
  -H "Content-Type: application/json" \
  -d '{"feedback_limit": 5000}' | jq -r '.job_id')
echo "Job ID: $JOB"

# 3. Monitor progress
echo "3. Monitoring training progress..."
for i in {1..60}; do
  STATUS=$(curl http://localhost:5000/api/training/status/$JOB | jq -r '.status')
  PROGRESS=$(curl http://localhost:5000/api/training/status/$JOB | jq '.progress')
  echo "[$i/60] Status: $STATUS, Progress: $PROGRESS%"
  
  if [ "$STATUS" = "completed" ]; then
    echo "Training completed!"
    break
  fi
  
  sleep 5
done

# 4. Get results
echo "4. Training results:"
curl http://localhost:5000/api/training/status/$JOB | jq '.result'

# 5. Verify models
echo "5. Checking models:"
curl http://localhost:5000/api/training/models | jq '.models'
```

---

## 🔗 Integration Points

### Where Corrections Are Captured
**File**: `backend/routes/api.py`
**Function**: `save_validated_data()`
**Trigger**: When user clicks "Save" on validated voucher

### Where Training Is Executed
**File**: `backend/routes/api_training.py`
**Function**: `start_training()`
**Background**: Threading service

### Where Models Are Stored
**Directory**: `backend/ml_models/`
**Files**:
- `ocr_corrections_model.json` (OCR patterns)
- `parsing_corrections_model.json` (Parsing rules)

---

Generated: 2026-01-27
