# ML Training System - Understanding the Current State

## Current Status

Your database has:
- **30 validated vouchers** (with `validation_status = 'VALIDATED'`)
- **0 training corrections** detected

## Why Training Shows 0 Corrections

The ML system learns by comparing:
1. **What OCR automatically extracted** (`parsed_json_original` field)
2. **What you manually corrected** (`parsed_json` field)

### Example:
```
OCR Output:        "AYDAIA/A"      (supplier name)
Your correction:   "AYDAIA/A"      (same - no correction)

Result: No training sample created (match = no learning needed)
```

```
OCR Output:        "AYDAIA/A"      (supplier name)
Your correction:   "AYADAIA/A"     (you fixed OCR error)

Result: Training sample created! (mismatch = system learns the correction)
```

## How to Enable ML Training

### Step 1: Make Actual Corrections on Receipts Page
Go to the **Receipts page** and click on vouchers to edit:

1. Look for fields that are **incorrectly OCR'd**
2. Click on the field to edit it
3. **Make a change** - even if small:
   - Wrong supplier name → correct it
   - Wrong date → fix it  
   - Wrong amount → correct it
4. Save the correction

### Step 2: Verify Corrections are Captured
After saving, the system will:
- Store the original OCR output (what machine read)
- Store your corrected version (what you entered)
- Create a training sample when you hit "Save Corrections"

### Step 3: Run Training
Once you've made several corrections:
1. Go to **Training page**
2. Click **"Start ML Training (All Models)"**
3. System will use your corrections to improve accuracy

## Current Database State Analysis

**Your 30 validated vouchers:**
- All have `parsed_json` (the data)
- Most have `parsed_json_original` (backup of original)
- **But**: No differences detected between them!

**Possible reasons:**
1. ✓ Vouchers were validated correctly on first try (auto-parse was perfect)
2. ✗ Corrections were made but not saved with original data tracking
3. ✗ The receipts editing form isn't working properly

## Next Steps

### Option A: Make Test Corrections (5 minutes)
1. Go to **Receipts** page
2. Click on 5-10 vouchers
3. Make obvious changes to test (e.g., change supplier name)
4. Save each one
5. Return to Training page and run training
6. You should see corrections appear

### Option B: Debug Current Corrections
If you believe you've made corrections, run this check:
```bash
python check_corrections_detailed.py
```

This will show you:
- Which vouchers have corrections
- What the differences are
- Why training isn't seeing them

## Quick Reference: What the System Tracks

| Field | Purpose | Example |
|-------|---------|---------|
| `parsed_json_original` | What OCR extracted | `{supplier: "AYDAIA"}` |
| `parsed_json` | What you corrected | `{supplier: "AYADAIA"}` |
| Difference | Training sample | Learn: AYDAIA → AYADAIA |

