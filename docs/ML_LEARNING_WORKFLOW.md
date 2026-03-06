# ML Learning Workflow - How Learning is Applied in Practice

## Overview
The ML system creates a **continuous feedback loop** where user corrections automatically improve future OCR results. Here's how it works end-to-end:

---

## Complete Learning Pipeline

### **Phase 1: User Correction (Data Collection)**

**When you use `/validate` page:**
```
1. User uploads voucher image
   ↓
2. System performs OCR + parsing
   ↓
3. Data displayed on /review page
   ↓
4. User makes corrections on /validate page (edits fields)
   ↓
5. User clicks "Save" button
   ↓
6. Database updated with corrected values
```

**Database Records Created:**
- Original OCR: `parsed_json` column (what the system initially extracted)
- User Corrections: `voucher_items`, `voucher_deductions` tables (user's corrections)
- Difference: This **gap between OCR and correction = training data**

### **Phase 2: Training Data Collection**

**When you visit `/training` and click "Start ML Training":**

```python
# Automatic process in MLTrainingService.collect_training_data()

1. Query database for all validated vouchers
2. For each voucher, compare:
   - Original parsed_json (what OCR extracted)
   - Database items (what user corrected it to)
3. Extract corrections:
   - "Original OCR had 'XYZ', but user corrected to 'ABC'" → Training example
4. Categorize into two types:
   - OCR Corrections: Wrong characters/text (e.g., "5" → "S")
   - Parsing Corrections: Wrong field extraction (e.g., supplier extracted from wrong line)
```

**Example Training Data Created:**
```python
OCR Correction:
{
    "original_ocr": "TAS FOODS",           # What OCR saw
    "correction": "TK FOODS",              # What user corrected
    "context": "supplier_name field",      # Where it occurred
    "raw_text": "Line 23: TK FOODS PVT LTD" # Full OCR context
}

Parsing Correction:
{
    "field": "supplier_name",
    "original_extraction": "AS",            # Wrong extraction
    "corrected_extraction": "TK FOODS",     # Correct extraction
    "raw_ocr": "...",                       # Full raw text to learn from
    "confidence": 0.85                      # How confident the correction is
}
```

### **Phase 3: Model Training**

**MLTrainingService.train_models() executes:**

```python
# Step 1: Collect corrections (from validated vouchers)
corrections = collect_training_data(limit=5000)  # Use last 5000 corrections
# Results:
# - 127 OCR corrections learned
# - 342 parsing corrections learned

# Step 2: Train OCR Model
ocr_model = OCRCorrectionModel()
ocr_model.train(corrections['ocr_corrections'])
# Learns patterns like:
# - "5" often should be "S"
# - "l" (letter L) often should be "1" (number one)
# - "O" often should be "0"

# Step 3: Train Parsing Model  
parsing_model = ParsingCorrectionModel()
parsing_model.train(corrections['parsing_corrections'])
# Learns patterns like:
# - "supplier_name" should be extracted from line containing "TK" + "FOODS"
# - "invoice_number" usually appears after "INV #" or "NO:"
# - "amount" fields are typically right-aligned numbers

# Step 4: Save Models
ocr_model.save_model('ocr_model.json')
parsing_model.save_model('parsing_model.json')
# Models stored in: backend/ml_models/
```

**How Models Work:**

**OCR Model** (Character Correction):
```python
# Pattern Library Example:
{
    "5_to_S": {
        "context": "supplier_name",
        "occurrences": 12,
        "confidence": 0.95,
        "rule": "When '5' appears in supplier name context, likely 'S'"
    },
    "O_to_0": {
        "context": "amount",
        "occurrences": 34,
        "confidence": 0.98,
        "rule": "When 'O' appears in numeric context, likely '0'"
    }
}
```

**Parsing Model** (Field Extraction):
```python
# Extraction Rules Example:
{
    "supplier_name": {
        "patterns": [
            "Supplier: [text]",
            "Vendor: [text]",
            "To: [text]",
            "CompanyName line usually after first few lines"
        ],
        "confidence": 0.87,
        "trained_on": 342 examples
    },
    "invoice_number": {
        "patterns": [
            "INV #[number]",
            "Invoice No: [number]",
            "Ref #[number]"
        ],
        "confidence": 0.92,
        "trained_on": 320 examples
    }
}
```

### **Phase 4: Using Trained Models on New Vouchers**

**When a new voucher is uploaded and processed:**

```
1. Image uploaded
   ↓
2. Initial OCR performed
   ↓
3. Initial Parsing performed (extracts fields)
   ↓
4. ✨ TRAINED MODELS APPLIED HERE ✨
   │
   ├─ OCR Model loads and checks:
   │  "Does the extracted text have common OCR errors I've learned?"
   │  Example: "5AS FOODS" → "TAS FOODS" → "TK FOODS"
   │
   └─ Parsing Model loads and checks:
      "Does the supplier name extraction look wrong based on what I've learned?"
      Example: If found "AS" instead of "TK FOODS" → Suggests correction
   │
5. Corrected data returned to user
   ↓
6. User sees better OCR on /review page
```

**Code in Action:**

```python
# In app.py or ocr_service.py during processing:

# Initial extraction
parsed_data = parser.parse(raw_ocr_text)
# Result might be: supplier_name: "AS" (because of OCR error "5" → "S")

# Apply learned models
from backend.services.ml_training_service import MLTrainingService

improved_data = MLTrainingService.apply_learned_corrections(
    auto_extracted_data=parsed_data,
    raw_ocr=raw_ocr_text
)
# Models check: "supplier_name is 'AS' but raw OCR contains 'TK'"
# Suggestion: "Did you mean 'TK FOODS'? (confidence: 0.92)"

# Return improved data
return improved_data
```

---

## Concrete Example: Learning Supplier Name

### **Day 1: User Makes a Correction**

User uploads a voucher with "TAS FOODS" instead of "TK FOODS"

**On /validate page:**
- Original OCR shows: `supplier_name: "TAS FOODS"`
- User types: `supplier_name: "TK FOODS"`
- User clicks Save

**Database now has:**
```sql
-- Original parsing (stored)
parsed_json → {"supplier_name": "TAS FOODS", ...}

-- User correction (stored)
supplier_name column → "TK FOODS"
```

### **Day 2: Training Run**

User goes to `/training` and clicks "Start ML Training"

**System does:**
```python
Training Data Collected:
- Found correction: "TAS" → "TK FOODS"
- Context: supplier_name field in OCR text "...TAS FOODS PVT..."
- Added to training set

Model Training:
- OCR Model learns: "When parsing supplier_name, 'TAS' might be 'TK'"
- Parsing Model learns: "Look for words like 'TK' + 'FOODS' for supplier"

Models Saved:
- ocr_model.json updated with this pattern
- parsing_model.json updated with this pattern
```

### **Day 3: New Voucher with Same Issue**

Another user uploads a similar receipt that also has OCR error: "TAS FOODS"

**System does:**
```python
# Initial extraction (same error as Day 1)
parsed_data = {
    "supplier_name": "TAS FOODS"  # OCR error
}

# Apply trained models
improved = MLTrainingService.apply_learned_corrections(
    parsed_data,
    raw_ocr_text
)

# Trained model checks its learned patterns:
# ✓ Sees "TAS" → remembers it learned this should be "TK"
# ✓ Checks context → supplier_name field matches learning
# ✓ Confidence: 0.92

# Result:
{
    "supplier_name": "TAS FOODS",
    "supplier_name_suggestion": "TK FOODS",  # Model's suggestion
    "supplier_name_confidence": 0.92          # How confident
}
```

**User sees on /review page:**
```
Supplier Name: TAS FOODS
  ⚠️ ML Suggestion: "TK FOODS" (92% confident)
  [Accept] [Ignore]
```

Or even better, if confidence is high enough, it auto-corrects!

---

## Real-World Impact: Progressive Improvement

### **Timeline:**

```
Week 1: System deployed, no trained models yet
- 50 vouchers processed
- Users make 50 × ~3 corrections each = ~150 corrections collected

Week 2: First training run
- Training data collected from 150+ corrections
- Models trained (learning patterns from real user corrections)
- New vouchers show ML suggestions (50% accuracy improvement)

Week 3: More corrections + second training
- 100 more corrections accumulated
- Models retrained with 250+ examples
- Accuracy improves to 75%

Week 4-6: Continuous improvement
- Models learn more edge cases
- Accuracy stabilizes at 85-90%
- New common errors are quickly learned and corrected
```

---

## Where Models Are Applied

### **1. Initial Processing** (`backend/ocr_service.py` or `parser.py`)
```python
# After initial OCR and parsing
raw_ocr_text = extract_text_from_image(voucher_image)
parsed_data = parser.parse(raw_ocr_text)

# Apply learned corrections
from backend.services.ml_training_service import MLTrainingService
parsed_data = MLTrainingService.apply_learned_corrections(
    parsed_data, 
    raw_ocr_text
)

# User sees improved data on /review page
return render_template("review.html", parsed_data=parsed_data)
```

### **2. During Validation** (`/validate` page)
```python
# When displaying for user correction
items = parsed_data.get('items', [])  # These already have ML improvements
deductions = parsed_data.get('deductions', [])

# If confidence is high, can be pre-filled
# If confidence is medium, show as suggestions
# If confidence is low, show as-is for user verification
```

---

## Key Benefits

| Benefit | How It Works |
|---------|-------------|
| **Automatic Improvement** | Each correction trains models, next voucher is slightly better |
| **Context-Aware** | Models learn field-specific rules (supplier name ≠ invoice number) |
| **Progressive** | Accuracy improves over time as more corrections accumulate |
| **Scalable** | Works with any number of corrections, learns faster with more data |
| **No Manual Effort** | Models train in background while you review vouchers |
| **Adaptive** | System learns YOUR specific suppliers, formats, OCR patterns |

---

## What Gets Learned?

```
✓ Character recognition errors (OCR errors)
✓ Field extraction patterns (where to find supplier name)
✓ Format-specific rules (your invoice format)
✓ Supplier-specific spelling variations
✓ Amount field patterns and formatting
✓ Date format recognition
✓ Item description extraction quality
✓ Deduction classification

Learning Process:
User Correction → Database → Training Data → Model Training → Better OCR
```

---

## Summary

**The learning workflow:**

1. **User corrects** data on `/validate` page → Stored in database
2. **Admin trains** models on `/training` page → Models learn from corrections
3. **Next voucher** uses trained models → Better accuracy automatically
4. **Cycle repeats** → Continuous improvement

**Result:** With every correction you make, the system gets smarter for the NEXT voucher of the same type.

