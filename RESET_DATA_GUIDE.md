# Reset Data - Complete Clean Slate

## Updated: Comprehensive Reset Function

The "Reset Data" feature has been updated to clean up **EVERYTHING** so you can start completely fresh.

### What Gets Deleted

#### ✅ Database
```
- All vouchers from vouchers_master table
- All batch processing records
- All validation history
```

#### ✅ Uploaded Files
```
uploads/
├── All receipt images
├── All cropped previews
├── All batch uploads
└── All temporary files
```

#### ✅ ML Models
```
backend/ml_models/
├── ocr_corrections_model.json     ❌ Deleted
├── parsing_corrections_model.json ❌ Deleted
└── smart_crop_model.json          ❌ Deleted
```

#### ✅ ML Training Data
```
backend/ml_dataset/
├── feedback/
│   ├── batch_corrections.jsonl    ❌ Deleted
│   ├── regular_corrections.jsonl  ❌ Deleted
│   └── crop_annotations.jsonl     ❌ Deleted
├── images/
│   └── All training crop images   ❌ Deleted
└── Entire directory              ❌ Deleted and recreated
```

### How to Use

1. **Navigate to**: Dashboard → "Reset Data" button
2. **Confirm**: Yes, delete everything
3. **System**: 
   - Clears all data
   - Deletes all ML models
   - Deletes all training feedback
   - Creates fresh empty directories
   - Ready to start over!

### What Happens After Reset

```
After Reset:
✅ Database: Empty, clean slate
✅ Uploads: Empty folder
✅ ML Models: None exist (fresh training opportunity)
✅ Training Data: Empty (start collecting feedback)
✅ System: Ready for new batch upload
```

### When to Use This

Use "Reset Data" when:
1. **Starting completely fresh** (clean slate)
2. **Fixing data consistency issues** (corrupted feedback)
3. **Retraining from scratch** (better ML models)
4. **Changing receipt types** (different document format)
5. **Testing new workflow** (uncluttered environment)

### What Changed in Code

**File**: [backend/routes/api.py](backend/routes/api.py#L197)

**Function**: `delete_all_data()`

**Improvements**:
- ✅ Now deletes ML models
- ✅ Now deletes all feedback data
- ✅ Now deletes training images
- ✅ Recreates empty directories
- ✅ Better logging/tracking
- ✅ Clear success message

### The Fresh Start Process

```
1. RESET
   Click "Reset Data" → All cleaned
   
2. UPLOAD NEW BATCH
   Upload 50-100 receipts
   System auto-detects and crops
   
3. VALIDATE
   Review crops, OCR, fields
   Make corrections as needed
   System captures: auto-crop + user-crop
   
4. COLLECT FEEDBACK
   150+ crop samples captured
   OCR corrections recorded
   Field corrections recorded
   
5. TRAIN ML MODELS
   OCR model learned from corrections
   Parsing model learned from field fixes
   Smart Crop model learned from crop deltas
   
6. TEST IMPROVEMENTS
   Upload new batch
   Auto-detection now uses learned corrections
   Much fewer manual adjustments needed
   
7. ITERATE
   More batches → More training → Better accuracy
```

### Expected Results

**Before Reset**:
- System has old data mixed in
- Old ML models with limited training
- Confusing feedback files
- Hard to track what was learned

**After Reset + New Training**:
- Clean, fresh dataset
- ML models trained on YOUR specific documents
- Clear improvement visible
- Much faster/more accurate processing

---

## Complete Clean Start Checklist

- [ ] Click "Reset Data" button
- [ ] Confirm deletion
- [ ] Wait for completion (should be fast)
- [ ] See success message
- [ ] Dashboard shows empty state
- [ ] Ready to upload new batch!

