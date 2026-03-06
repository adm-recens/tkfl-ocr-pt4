# VoucherOCR - Intelligent Receipt Processing Platform

An automated, ML-powered Optical Character Recognition (OCR) platform designed specifically to extract structured data from complex, unstructured supplier receipts and invoices.

## Features

- **Bulk Queue Processing:** Upload multiple receipt images at once and process them in a streamlined wizard interface.
- **Smart Crop Detection:** Automatically detects receipt boundaries and crops out dark backgrounds using OpenCV Edge and Contour detection. 
- **Learning Smart Crop:** An independent ML model that learns from user-adjusted cropping bounds over time to improve the automatic crop accuracy.
- **Advanced Text Parsing (TKFL Parser V2):** Deep regex and rule-based extraction tailored to complex supplier layouts (handles multi-line values, dynamic tables, varying date formats).
- **ML Smart Template Engine:** A sophisticated machine learning feedback loop that *genuinely learns* from user corrections:
  - **Character-Level OCR Correction:** Learns typical OCR mistakes (like '0' vs 'O') and proactively patches the scanned text before parsing.
  - **Fuzzy Anchor Matching:** Learns the spatial relationship between labels and values (e.g. knowing "Net Total" is found 2 lines below "Subtotal") even if the label has typos.
  - **Active Confidence Overrides:** Once the system is highly confident (rating > 80%) based on historical corrections for a specific supplier, the ML actively overrides the regex base parser's guesses.
- **Human-in-the-Loop Validation:** An intuitive UI for reviewing and correcting extracted fields before finalizing them into the master database.
- **Dataset Management:** Track statistics on total images uploaded, corrections made, and view historical learning logs.

## Architecture

The project is built around a Flask (Python) backend with a Vanilla JS/TailwindCSS frontend.

### Key Components

- `TKFLReceiptParserV2`: The core regex/rule-based extraction engine (`backend/tkfl_parser_v2.py`).
- `SmartReceiptDetector`: OpenCV-based automatic cropping utility (`backend/smart_crop.py`).
- **ML Training Layer:**
  - `SmartCropTrainingService`: Learns boundary adjustments from `x, y, w, h` delta values.
  - `MLTrainingService`: Orchestrates the training of the text parsing and OCR correction models based on user validations.
  - `OCRCorrectionModel` & `ParsingCorrectionModel`: The actual models that store learned character swaps and fuzzy anchor mappings.
- **REST APIs:** Full suite of API endpoints for queue management, validation, and ML training triggers (`backend/routes/`).

## Installation

### Prerequisites
- Python 3.9+
- Tesseract OCR engine installed and added to your system PATH
- SQLite (built-in with Python)

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
   The SQLite database (`database.db`) will be automatically initialized with the required schema on the first run.

4. **Environment Variables:**
   Ensure the application has access to Tesseract. If it's not in your system path, you may need to configure `pytesseract.pytesseract.tesseract_cmd` directly in the backend code.

## Running the Application

Start the Flask development server:

```bash
python run.py
```

The application will be accessible at `http://localhost:5000`.

## Training the ML Models

The system requires initial manual validation to begin learning. 
1. Upload receipts via the **Queue** interface.
2. Review and correct the extracted data on the **Validate** page.
3. Once you have a batch of corrections, navigate to the **Training Hub** (`/training`).
4. You can train the **Text Parsing Models** and the **Smart Crop Model** independently.
5. Watch the validation accuracy improve on subsequent uploads!

## Project Structure

```text
tkfl_ocr/pt5/
├── run.py                    # Application entry point
├── analyze_all.py            # Utility script for mass log analysis
├── backend/
│   ├── routes/               # Flask API endpoints (main, queue, training, etc.)
│   ├── services/             # Core business logic (ML, Vouchers, Batches)
│   ├── ml_models/            # JSON representations of learned ML patterns
│   ├── templates/            # HTML views
│   └── tkfl_parser_v2.py     # Rule-based text extractor
├── database.db               # SQLite database
└── uploads/                  # Temporary storage for raw and cropped images
```
