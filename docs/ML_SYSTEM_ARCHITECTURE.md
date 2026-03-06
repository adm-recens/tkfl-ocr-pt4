# ML Training System - Architecture

## System Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        VOUCHER PROCESSING PIPELINE                              │
└─────────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────────┐
    │  Upload Image    │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │  OCR Extraction  │
    │  (extract_text)  │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────────────────┐
    │  Apply OCR Corrections       │◄──── Learned from previous errors
    │ (text_correction.py)         │
    └────────┬─────────────────────┘
             │
             ▼
    ┌──────────────────┐
    │  Parse Fields    │
    │ (parser.py)      │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────────────────┐
    │  Apply Parsing Suggestions   │◄──── Learned from user corrections
    │ (ML model)                   │
    └────────┬─────────────────────┘
             │
             ▼
    ┌──────────────────────────────┐
    │  Present to User             │
    │  With Confidence Scores      │
    └────────┬─────────────────────┘
             │
             ▼
    ┌──────────────────────────────┐
    │  User Validates/Corrects     │
    │  (validation page)           │
    └────────┬─────────────────────┘
             │
             ▼
    ┌──────────────────────────────┐
    │  SAVE TO DATABASE            │
    │  Capture corrections ───────────┐
    │  (validation_status=VALIDATED)  │
    └──────────────────────────────┘  │
                                      │
                                      ▼
                              ┌─────────────────────┐
                              │  Feedback Loop      │
                              │  (auto-captured)    │
                              └─────────┬───────────┘
                                        │
                                        ▼
                              ┌──────────────────────────────┐
                              │  Training (On-Demand)        │
                              │  /api/training/start         │
                              └─────────┬────────────────────┘
                                        │
                                        ▼
                              ┌──────────────────────────────┐
                              │  Train ML Models             │
                              │  - OCR corrections model     │
                              │  - Parsing rules model       │
                              └─────────┬────────────────────┘
                                        │
                                        ▼
                              ┌──────────────────────────────┐
                              │  Save Models to Disk         │
                              │  backend/ml_models/          │
                              └──────────────────────────────┘
                                        ▲
                                        │
                                        │ (cycle repeats)
                                        │
```

## Component Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                         REST API Layer                              │
│  ┌──────────────────┬──────────────────┬──────────────────┐        │
│  │  /api/upload     │  /api/validate   │  /api/training/* │        │
│  └────────┬─────────┴────────┬─────────┴────────┬─────────┘        │
└───────────┼──────────────────┼──────────────────┼─────────────────┘
            │                  │                  │
            ▼                  ▼                  ▼
┌────────────────────────────────────────────────────────────────────┐
│                       Service Layer                                 │
│  ┌──────────────────────┬────────────────────┬──────────────────┐  │
│  │  OCR Service         │ Voucher Service    │ ML Training      │  │
│  │  (text extraction)   │ (DB persistence)   │ Service          │  │
│  └──────────────────────┴────────────────────┴──────────────────┘  │
└──────────────┬────────────────────────────────────────┬─────────────┘
               │                                        │
               ▼                                        ▼
┌──────────────────────────┐        ┌─────────────────────────────┐
│    Text Correction       │        │   ML Models & Training      │
│   (text_correction.py)   │        │   (ml_correction_model.py)  │
│                          │        │                             │
│  - Static replacements   │        │  - OCRCorrectionModel      │
│  - Dictionary-based      │        │  - ParsingCorrectionModel  │
└──────────────────────────┘        │                             │
                                    │  - Pattern learning         │
                                    │  - Confidence scoring       │
            ┌───────────────────────┴─────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────────────────────────────────┐
│                    Parser Layer                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  parse_receipt_text() - Regex-based field extraction          │ │
│  │  Extracts: supplier_name, date, voucher_number, items, etc.   │ │
│  └───────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  PostgreSQL Database │
                    │  - vouchers_master   │
                    │  - voucher_items     │
                    │  - voucher_deductions│
                    └──────────────────────┘
```

## Data Flow: Training Process

```
                    TRAINING PIPELINE
┌──────────────────────────────────────────────────────────────────┐

1. COLLECTION PHASE
   ┌───────────────────────┐
   │ Database Query        │
   │ SELECT validated      │
   │ vouchers              │
   └───────────┬───────────┘
               │
               ▼
   ┌───────────────────────────────────────────┐
   │ For each voucher:                         │
   │ - Get raw OCR text                        │
   │ - Get auto-parsed fields                  │
   │ - Get user-corrected values               │
   │ - Compare and extract differences         │
   └───────────┬───────────────────────────────┘
               │
               ▼
   ┌───────────────────────────────────────────┐
   │ Training Samples Created:                 │
   │ {raw_ocr, auto, corrected, field_type}    │
   │                                           │
   │ Example:                                  │
   │ - field: supplier_name                    │
   │ - auto: "AS"                              │
   │ - corrected: "TK"                         │
   │ - raw_ocr: "TK\nSuppNane..."              │
   └───────────┬───────────────────────────────┘
               │
2. TRAINING PHASE
               │
               ▼
   ┌───────────────────────────────────────────┐
   │ Initialize Models                         │
   │ - OCRCorrectionModel()                    │
   │ - ParsingCorrectionModel()                │
   └───────────┬───────────────────────────────┘
               │
               ├─────────────────┬──────────────────────┐
               │                 │                      │
               ▼                 ▼                      ▼
   ┌─────────────────┐ ┌──────────────────┐ ┌──────────────────┐
   │ OCR Learning    │ │ Field Learning   │ │ Context Learning │
   │                 │ │                  │ │                  │
   │ Input:          │ │ By field_type:   │ │ From raw_ocr:    │
   │ "SuppNane" →    │ │ supplier_name,   │ │ Extract context  │
   │ "Supp Name"     │ │ voucher_date,    │ │ around errors    │
   │                 │ │ voucher_number   │ │                  │
   │ Learn:          │ │                  │ │ Learn context +  │
   │ - Character     │ │ Learn:           │ │ → correction     │
   │ - Word changes  │ │ - Specific rules │ │                  │
   │ - Confidence    │ │ - Patterns       │ │ Learn:           │
   │                 │ │                  │ │ - Context-aware  │
   │ Store:          │ │ Store:           │ │ - Field-specific │
   │ Frequency count │ │ Examples         │ │                  │
   │                 │ │ Corrections      │ │ Store:           │
   │                 │ │                  │ │ Context patterns │
   └────────┬────────┘ └────────┬─────────┘ └────────┬─────────┘
            │                   │                    │
            └───────────────────┼────────────────────┘
                                │
3. PERSISTENCE PHASE
                                │
                                ▼
                    ┌──────────────────────────┐
                    │ Serialize Models to JSON │
                    │ - Patterns with counts   │
                    │ - Examples with context  │
                    │ - Confidence metrics     │
                    └────────────┬─────────────┘
                                │
                                ▼
                    ┌──────────────────────────┐
                    │ Save to Disk             │
                    │ ocr_model.json           │
                    │ parsing_model.json       │
                    │ (backend/ml_models/)     │
                    └──────────────────────────┘

└──────────────────────────────────────────────────────────────────┘
```

## Inference Process (Applied to New Vouchers)

```
                    INFERENCE PIPELINE
┌──────────────────────────────────────────────────────────────────┐

    Raw OCR Text
         │
         ▼
    ┌─────────────────────┐
    │ Load Trained Models │  ◄─── From backend/ml_models/
    │ (if available)      │
    └────────┬────────────┘
             │
             ├─── Model 1: OCRCorrectionModel (learned patterns)
             ├─── Model 2: ParsingCorrectionModel (context rules)
             │
             ▼
    ┌─────────────────────────────────┐
    │ Apply OCR Corrections           │
    │                                 │
    │ For each word/phrase in OCR:    │
    │ - Check if in learned patterns  │
    │ - Get most frequent correction  │
    │ - Apply if confidence > 50%     │
    │                                 │
    │ Example:                        │
    │ "SuppNane" → check patterns     │
    │ → found: {"Supp Name": 50}      │
    │ → confidence: 100%              │
    │ → APPLY: "Supp Name"            │
    └────────┬────────────────────────┘
             │
             ▼
    ┌─────────────────────────────────┐
    │ Parse Corrected Text            │
    │ (regex-based extraction)        │
    │                                 │
    │ Extract fields:                 │
    │ - supplier_name = "TK"          │
    │ - voucher_date = "26/04/2024"   │
    │ - voucher_number = "214"        │
    └────────┬────────────────────────┘
             │
             ▼
    ┌─────────────────────────────────┐
    │ Apply Parsing Corrections       │
    │                                 │
    │ For each field:                 │
    │ - Check if context in model     │
    │ - Get suggested value           │
    │ - Attach confidence score       │
    │                                 │
    │ Example:                        │
    │ Field: supplier_name            │
    │ Context: "TK\nSupp Name..."     │
    │ → Check patterns                │
    │ → suggestion: "TK"              │
    │ → confidence: 95%               │
    │ → ATTACH: suggestion            │
    └────────┬────────────────────────┘
             │
             ▼
    ┌─────────────────────────────────┐
    │ Return Enhanced Extraction      │
    │                                 │
    │ {                               │
    │   supplier_name: "TK",          │
    │   supplier_name_suggestion:     │
    │       "TK",                     │
    │   supplier_name_confidence:     │
    │       0.95,                     │
    │   ...                           │
    │ }                               │
    └─────────────────────────────────┘
             │
             ▼
    Presented to User with Confidence Indicators

└──────────────────────────────────────────────────────────────────┘
```

## Class Relationships

```
┌──────────────────────────────────────────────────────────────────┐
│                     ML Models Package                             │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ OCRCorrectionModel                                         │  │
│  │ ─────────────────────────────────────────────────────────  │  │
│  │ - ocr_patterns: Dict[str, Counter]                         │  │
│  │ - vocab_corrections: Dict[str, Counter]                   │  │
│  │ - field_patterns: Dict[str, Dict]                         │  │
│  │                                                            │  │
│  │ Methods:                                                   │  │
│  │ + learn_from_correction(raw, auto, corrected, field)      │  │
│  │ + apply_correction(text) -> str                           │  │
│  │ + get_correction_confidence(text, correction) -> float    │  │
│  │ + save_model(name) -> path                                │  │
│  │ + load_model(name) -> bool                                │  │
│  │ + get_stats() -> Dict                                     │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ ParsingCorrectionModel                                     │  │
│  │ ─────────────────────────────────────────────────────────  │  │
│  │ - parsing_corrections: Dict[str, Dict[str, Counter]]       │  │
│  │                                                            │  │
│  │ Methods:                                                   │  │
│  │ + learn_from_correction(field, raw_ocr, auto, corrected)  │  │
│  │ + get_correction_suggestion(field, ocr, extracted)        │  │
│  │ + save_model(name) -> path                                │  │
│  │ + load_model(name) -> bool                                │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│               ML Training Service                                 │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ MLTrainingService                                          │  │
│  │ ─────────────────────────────────────────────────────────  │  │
│  │ Static Methods:                                            │  │
│  │ + collect_training_data(limit) -> Dict                     │  │
│  │ + train_models(feedback_limit, save) -> Dict              │  │
│  │ + get_training_status() -> Dict                           │  │
│  │ + apply_learned_corrections(data, ocr) -> Dict            │  │
│  │                                                            │  │
│  │ Workflow:                                                  │  │
│  │ collect → train → save → apply                            │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                  Training API Routes                              │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ POST /api/training/start                                   │  │
│  │ → Returns job_id, starts background training               │  │
│  │                                                            │  │
│  │ GET /api/training/status/<job_id>                         │  │
│  │ → Returns progress, final result, or error                │  │
│  │                                                            │  │
│  │ GET /api/training/status                                  │  │
│  │ → Returns current model availability and stats             │  │
│  │                                                            │  │
│  │ GET /api/training/models                                  │  │
│  │ → Returns detailed model information                       │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## File Organization

```
project_root/
│
├── backend/
│   ├── ml_models/                    ← NEW
│   │   ├── __init__.py
│   │   ├── ml_correction_model.py    ← Core ML models
│   │   ├── ocr_corrections_model.json (after training)
│   │   └── parsing_corrections_model.json (after training)
│   │
│   ├── services/
│   │   ├── ml_training_service.py    ← NEW: Training orchestration
│   │   └── ml_feedback_service.py    (existing: feedback collection)
│   │
│   ├── routes/
│   │   ├── api_training.py           ← MODIFIED: Real training endpoints
│   │   └── api.py                    ← MODIFIED: Feedback capture
│   │
│   └── ...
│
├── ML_QUICKSTART.md                  ← NEW: Quick start guide
├── ML_TRAINING_GUIDE.md              ← NEW: Full documentation
├── ML_IMPLEMENTATION_SUMMARY.md      ← NEW: Architecture overview
├── ML_SYSTEM_ARCHITECTURE.md         ← NEW: This file
│
├── init_ml_training.py               ← NEW: Setup script
└── examples_ml_training.py           ← NEW: Usage examples

```

---

**Key Points:**
- ML models are **non-intrusive** - system works without them
- Learning is **automatic** - no code changes needed for feedback
- Training is **on-demand** - run when you want via API
- Models are **persistent** - saved to disk, loaded on need
- Performance is **fast** - millisecond latency for inference
