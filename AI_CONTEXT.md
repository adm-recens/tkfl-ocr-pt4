# AI Context Document: VoucherOCR Platform (Full Application)

**Instruction for AI Models:** *When starting a new session or task on this repository, you MUST read this document thoroughly to understand the ENTIRE system architecture, the purpose of each component, the data flows, and the strict rules for development.*

## 1. Description and Purpose
VoucherOCR is a comprehensive, end-to-end optical character recognition (OCR) and Machine Learning-powered data extraction application. Its primary goal is to process highly irregular supplier receipts and invoices (such as those from local Indian markets) and extract structured financial data (Dates, Totals, Deductions, Supplier Names). 

The platform supports bulk image processing, automated "smart cropping" to remove background noise, a deep regex-based parser, a Human-in-the-Loop validation UI, and an active Machine Learning feedback loop that trains on human corrections.

---

## 2. Technology Stack
- **Backend:** Python 3.9+, Flask (Routing, API).
- **Frontend:** HTML5, Vanilla JavaScript (ES6+), Server-Side Templating (Jinja2), TailwindCSS (Styling).
- **Core Processing:** Tesseract OCR (Text Extraction), OpenCV (Image Manipulation & Contours).
- **Database:** PostgreSQL (with raw SQL data access combined with light service objects via connection pooling).

---

## 3. Core Architecture & Modules

The backend is cleanly separated into Models/Core Logic, Services, and Route Handlers.

### A. Core Processing Engine
- `backend/smart_crop.py`: Uses CV2 Edge/Contour detection to find the actual paper receipt within an image and crops out dark backgrounds.
- `backend/ocr_service.py`: Interfaces with Tesseract to extract raw text and layout block data from the cropped image.
- `backend/tkfl_parser_v2.py`: The "Base Parser." A massive suite of regular expressions that looks for common date formats, totals, and specific industry deduction fields (e.g., "Unloading", "Commission").

### B. The Machine Learning Layer
The ML system does *not* use deep neural networks (like PyTorch/TensorFlow). Instead, it uses intelligent, algorithm-driven template matching and statistical analysis that actively learns from user corrections.
- **`ml_correction_model.py`:** 
  1. **Character Matrix:** Learns consistent OCR mistakes (e.g., reading `O` as `0`) based on string diffs.
  2. **Fuzzy Anchor Engine:** Memorizes the spatial relationship between labels and values (e.g. knowing "Net Total" is found 2 lines below "Subtotal") using `difflib.SequenceMatcher` to defeat spelling typos.
- **`ml_training_service.py` & `enhanced_ml_training.py`:** Handles the heavy lifting of gathering validation data, applying OCR character corrections *before* parsing, and applying high-confidence fuzzy anchor overrides *after* parsing.
- **`smart_crop_training_service.py`:** An independent model that looks at how humans adjusted crop bounding boxes and adjusts the mathematical thresholds in `smart_crop.py` for future images.
- **`learning_history_tracker.py` & `ml_feedback_service.py`:** Tracks statistical improvements, saving validation snapshots to prove accuracy gains over time.

### C. Services Layer (`backend/services/`)
Handles all database operations and business logic execution.
- `batch_service.py`: Manages upload "Batches" (groups of receipts processed together).
- `voucher_service.py` / `voucher_service_beta.py`: Handles individual receipt records (Vouchers), including saving the `original_json` (parser guess) vs `corrected_json` (human truth).
- `supplier_service.py`: Manages the supplier database tables.
- `production_sync_service.py`: Handles exporting finalized, validated data out of the system.

---

## 4. Frontend UI & Workflows (`backend/templates/`)

The application is SPA-like but utilizes multi-page routing. All views use `base.html` for layout.

| UI Component | Template | User Workflow |
| :--- | :--- | :--- |
| **Dashboard** | `index.html` | The landing page. Shows key metrics (total processed, ML health, recent batches). |
| **Queue Upload** | `queue_upload.html` | Drag-and-drop interface to upload multiple `.jpg`/`.png` images. |
| **Queue Processor** | `queue_processor.html` | The core processing UI. Shows previews of Smart Crop bounds, allows manual crop adjustment, and triggers the massive backend processing loop via WebSockets/Polling. |
| **Validation** | `validate.html` | The most critical human-in-the-loop screen. Displays parsed data alongside the image snippet. Users correct wrong data here. Saving commits the "Truth" for ML. |
| **Review** | `review.html` | Similar to Validate, but for read-only or finalized states. |
| **Batch Management**| `batch_list.html`, `batch_summary.html` | List views of uploaded batches and their current processing status. |
| **Voucher Vault** | `view_receipts.html` | A searchable table of every individual receipt processed in the system. |
| **Supplier Mgmt** | `suppliers.html`, `supplier_detail.html` | UI to manage known suppliers and aliases. |
| **Training Hub** | `training.html` | Split UI to independently trigger ML computations for **Text Parsing** and **Smart Crop**. |
| **Learning Logs** | `learning_history.html` | Visual timeline of what the ML engine has learned. |

---

## 5. API Routing (`backend/routes/`)

- **`main.py`:** Serves all the HTML templates above. Handles auth/session rendering if applicable.
- **`api.py`:** Core extraction triggers (e.g., `POST /api/process-batch-v2`).
- **`api_queue.py`:** Polling endpoints for the long-running queue processor UI.
- **`api_training.py`:** Triggers the background worker threads for ML training (`POST /api/training/start`, `/api/training/smart-crop/start`).
- **`learning.py`:** Exposes the history and statistics of ML effectiveness.

---

## 6. Database Entities (PostgreSQL)

Key tables the system relies on:
- `vouchers_master` / `beta_vouchers`: The core receipt records. Stores image paths, `original_json`, `corrected_json`, and validation status.
- `batches`: Metadata about a group upload.
- `suppliers`: Supplier ID mapping.
- `ml_learning_history`: Time-series logs of improvement runs.
- `ml_models/` (Directory): Stores JSON representations of the learned rules (not in SQLite, but critical data tier).

---

## 7. Active Instructions for AI Models

When developing on this application, strictly adhere to the following rules:

1. **NO Hardcoded Overrides for Specific Suppliers:**
   Do *not* write Python code like `if "NARSIMA" in text: parse_date()`. 
   **Why:** We stripped all hardcoded supplier logic out. If a supplier has a weird layout, the user must correct it in the `validate.html` UI once, and the **Fuzzy Anchor Engine** will learn that layout organically. Do not bypass the ML engine with code hacks.
   
2. **Maintain Separation of Concerns:**
   The Smart Crop algorithm and the Text Parsing algorithm must remain strictly separated. Do not merge their endpoints or UI training cycles. 

3. **Frontend Rules:**
   Use TailwindCSS exclusively. Achieve modern, clean designs (`rounded-xl`, soft shadows, vibrant indicators). Use Vanilla JS `fetch()` for API calls. Do not introduce React, Vue, jQuery, or custom CSS files unless absolute necessary for a complex animation.

4. **Database Rules:**
   Do not introduce heavy ORMs like SQLAlchemy unless requested. We are using raw SQL execution logic wrapped in service classes (e.g., `voucher_service.py`) leveraging `psycopg2` (or similar PostgreSQL adapters) for speed and simplicity. 

5. **Testing & QA Context:**
   Always run testing utility scripts from the `scripts/` or `tests/` directories using `python -m tests.test_parser` or similar module constructs. Ensure `verify_parser.py` passes immediately following any adjustment to `TKFLReceiptParserV2`.

### When to Modify `AI_CONTEXT.md`
If you, as an AI, fundamentally alter the architecture, create a new pipeline stage, or add a major endpoint, you **must** update this `AI_CONTEXT.md` document to ensure future sessions possess the correct structural map.
