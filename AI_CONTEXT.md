# AI Context Document: VoucherOCR Platform

**Instruction for AI Models:** *When starting a new session or task on this repository, you MUST read this document thoroughly to understand the system architecture, the purpose of each component, and the strict rules for development.*

## 1. Description and Purpose
VoucherOCR is a complex optical character recognition and ML-powered parsing system tailored for extracting structured financial data from highly irregular supplier receipts (such as those from local Indian suppliers). It includes automatic receipt cropping, regex-based initial parsing, and an active Machine Learning feedback loop that trains on human corrections.

---

## 2. Core Architecture & Pipeline

The system is built on a **Python Flask backend** and a **Vanilla JS / TailwindCSS frontend**.

### Data Processing Pipeline (The Critical Flow):
When an image is uploaded, it passes through the following highly specific sequence:

1. **Smart Crop Detection (`backend.smart_crop`):** OpenCV detects the actual receipt boundary against dark backgrounds and crops it, enhancing OCR readability.
2. **Text Extraction Pipeline (`backend.ocr_service`):** The image is fed to Tesseract.
3. **ML Phase 1 - Character Level Correction (`backend.services.ml_training_service.apply_ocr_character_corrections`):** Before *any* parsing begins, the ML model looks at the raw OCR text and applies high-confidence character swaps (e.g., swapping `O` for `0` or `1` for `l`) learned from past user validation.
4. **Base Parsing (`backend.tkfl_parser_v2.TKFLReceiptParserV2`):** The cleanly swapped text is processed by a massive suite of regular expressions that look for common date formats, totals, and deduction fields.
5. **ML Phase 2 - Fuzzy Anchor Overrides (`backend.ml_models.ml_correction_model` & `ml_training_service`):** The ML engine overrides the Base Parser. If a user previously corrected an extraction on a supplier's receipt, the system remembers the *anchor text* near the corrected value (using `SequenceMatcher` for fuzzy matching to defeat OCR typos). High-confidence ML predictions *always* overwrite the regex extraction.

---

## 3. UI Navigation & Page Routes

The frontend consists of specialized pages mapping to distinct steps in the user workflow.
**All UI templates reside in `backend/templates/`.**

| URL Route | Template | Purpose & Workflow |
| :--- | :--- | :--- |
| `/` | `index.html` | Dashboard showing total stats and system health. |
| `/queue` | `queue_processor.html` | Batch upland handler. Allows uploading multiple images, previews the smart-cropped bounds, and submits them to the `process-batch-v2` API. |
| `/validate` | `validate.html` | The Human-in-the-Loop review screen. Displays receipts in a data-table where users correct OCR mistakes inline. Committing changes here saves data to the DB as `original_json` vs `corrected_json` (crucial data for the ML engine). |
| `/suppliers` | `suppliers.html` | Management of supplier aliases and specific parsing rules or IDs. |
| `/training` | `training.html` | **The Machine Learning Control Panel.** Contains two split sections: one to trigger the Text Parsing Model training (character swaps & fuzzy anchors) and one to trigger the Smart Crop Model training. |

---

## 4. API Routes Database

**All backend implementations live in `backend/routes/`.**

- **Main Extraction (`api.py`):**
  - `POST /api/process-batch-v2`: Receives multiple image files, runs the cropping and OCR parser multi-threaded, and returns the parsed JSON payload. Does *not* save them to the DB as finalized yet.
- **Queue & Status (`api_queue.py`):**
  - Manages asynchronous status updates for long-running batches.
- **Validation (`api_validation.py`):**
  - `GET /api/validation/receipts`: Fetches pending database items.
  - `POST /api/validation/commit`: This is where a user's final manual review is saved. This route writes the difference between the parser's guess and the user's truth, providing the exact diffs needed for the ML training phase.
- **Machine Learning (`api_training.py`):**
  - `POST /api/training/start`: Triggers the training of the Text Parsing Engine (anchors & chars).
  - `POST /api/training/smart-crop/start`: Triggers the training of the Smart Crop model.
  - `GET /api/training/status/<id>` & `GET /api/training/smart-crop/status`: Polls job progress.

---

## 5. Active ML Rules & Instructions for AI Models

When developing on this application, strictly adhere to the following rules based on past system improvements:

1. **NO Hardcoded Overrides for Specific Suppliers:**
   Do *not* write Python code like `if "NARSIMA" in text: parse_date_this_way()`. 
   **Why:** We stripped all hardcoded supplier logic out. If a supplier has a weird layout, the user must correct it in the UI once, and the **Fuzzy Anchor Engine** (`ml_correction_model.py`) will automatically learn that layout. Do not bypass the ML engine with code hacks.
   
2. **Never Tightly Couple the ML Models:**
   The Smart Crop algorithm and the Text Parsing algorithm must remain strictly separated. Do not merge their endpoints or training cycles.

3. **Database Usage (`database.db`):**
   The application uses SQLite3. Do not attempt to establish heavy ORMs unless specifically requested by the user. Most database operations are managed via raw SQL or lightweight helpers in `backend/services/`.

4. **Testing Context:**
   Always run testing utility scripts from the `scripts/` or `tests/` directories using `python -m tests.test_parser` or similar relative contexts if modifying core parsing rules. Ensure `verify_parser.py` passes immediately following any adjustment to `TKFLReceiptParserV2`.

5. **Style Guidelines:**
   - Visuals: Use TailwindCSS exclusively for styling on frontend HTML files. Achieve modern, clean designs with subtle borders and shadows (e.g., `rounded-xl`, `shadow-lg`, Tailwind base colors). Do not write raw CSS files unless adding complex animations.
   - Frontend Logic: Use Vanilla JavaScript and standard `fetch()` API for client-side routing. No heavy frameworks (React/Vue) exist in this project.

### When to Modify `AI_CONTEXT.md`
If you, as an AI, fundamentally alter the architecture, create a new pipeline stage, or add a major endpoint, you **must** update this `AI_CONTEXT.md` document to ensure future sessions possess the correct structural map.
