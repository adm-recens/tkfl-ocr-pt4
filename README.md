# VoucherOCR - Intelligent Receipt Processing Platform

An automated, ML-powered Optical Character Recognition (OCR) platform designed specifically to extract structured data from complex, unstructured supplier receipts and invoices.

VoucherOCR is a complete web application built for local Indian businesses and enterprises that process large volumes of irregular, paper-based receipts. It handles everything from bulk image uploading to human-verified data exportation.

## Core Features

- **Bulk Queue Processing:** Upload multiple receipt images at once. A streamlined wizard interface automatically runs initial text detection and image filtering.
- **Smart Crop Detection:** Automatically detects receipt boundaries and crops out dark backgrounds using OpenCV Edge and Contour detection. 
- **Learning Smart Crop:** An independent ML model that learns from user-adjusted cropping bounds over time to improve the automatic crop accuracy for varying lighting conditions.
- **Advanced Text Parsing (TKFL Parser V2):** Deep regex and rule-based extraction tailored to complex supplier layouts (handles multi-line values, dynamic tables, varying date formats).
- **ML Smart Template Engine:** A sophisticated machine learning feedback loop that *genuinely learns* from user corrections:
  - **Character-Level OCR Correction:** Learns typical OCR mistakes (like '0' vs 'O') and proactively patches the scanned text before parsing.
  - **Fuzzy Anchor Matching:** Learns the spatial relationship between labels and values (e.g. knowing "Net Total" is found 2 lines below "Subtotal") even if the label has typos.
  - **Active Confidence Overrides:** Once the system is highly confident based on historical corrections for a specific supplier, the ML actively overrides the regex base parser's guesses.
- **Human-in-the-Loop Validation:** An intuitive UI for reviewing and correcting extracted fields before finalizing them into the master database. This is where the ML engine gets its "ground truth" training data.
- **Supplier Directory:** A built-in management system for tracking unique suppliers, mapping aliases, and assigning persistent system IDs across receipts.
- **Voucher Vault:** A historical table view of all parsed receipts, showing their visual snips alongside final financial data.

## Overall Architecture

The project is built around a lightweight **Python/Flask backend** and a fast, modern **Vanilla JS / TailwindCSS frontend**. The platform avoids heavy ORMs and JS frameworks for maximum control and speed.

### Processing Pipeline
1. Images are uploaded into `batches`.
2. Asynchronous workers apply the `SmartCrop` to clean the image.
3. Tesseract OCR extracts raw structural text.
4. The `MLTrainingService` intercepts the raw text to apply known character defect patches.
5. `TKFLReceiptParserV2` searches the text for business logic (Net Totals, Dates, Deductions).
6. High-confidence ML anchors override the base regex where historical corrections dictate.
7. Output is stored in `database.db` (`vouchers_master` table) as `original_json` awaiting human validation.

## Installation

### Prerequisites
- Python 3.9+
- Tesseract OCR engine installed and added to your system PATH
- OpenCV
- PostgreSQL Database

### Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd tkfl_ocr/pt5
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialize the Database:**
   Ensure your PostgreSQL instance is running. Create a database (e.g., `tkfl_ocr`) and set the `DATABASE_URL` environment variable appropriately in `.env`. The application handles table generation.

4. **Environment Variables:**
   Ensure the application has access to Tesseract. If it's not in your system path, you may need to configure `pytesseract.pytesseract.tesseract_cmd` directly in `backend/ocr_service.py`.

## Running the Application

Start the Flask development server:

```bash
python run.py
```

The application will be accessible at `http://localhost:5000`.

## Training the ML Models

The system requires initial manual validation to begin learning. 
1. Upload receipts via the **Queue Upload** interface.
2. Review and correct the extracted data on the **Validate** page.
3. Once you have a batch of corrections, navigate to the **Training Hub** (`/training`).
4. You can train the **Text Parsing Models** and the **Smart Crop Model** independently.
5. Watch the validation accuracy improve on subsequent uploads!

## Project Structure

```text
tkfl_ocr/pt5/
├── run.py                    # Application entry point
├── backend/
│   ├── routes/               # Flask API endpoints (main views, APIs, queue logic)
│   ├── services/             # Core business logic (DB inserts, Batch tracking, ML orchestrator)
│   ├── ml_models/            # JSON mapping of learned spatial anchors and OCR corrections
│   ├── templates/            # HTML structural views (Tailwind)
│   ├── smart_crop.py         # OpenCV image boundary detector
│   ├── ocr_service.py        # Tesseract execution layer
│   └── tkfl_parser_v2.py     # Base rule-based text extractor
├── docs/                     # Detailed architectural plans and historical analysis logs
├── scripts/                  # Helpful standalone scripts for deep debugging and database checking
├── tests/                    # Unit tests ensuring core parsing logic doesn't regress
└── uploads/                  # Temporary storage for raw and cropped images
```

## Contributing
When contributing to this repository, please review `AI_CONTEXT.md` in the root folder. It contains strict guidelines regarding architectural separation, UI libraries, and ML learning behaviors for developers and AI agents alike.
