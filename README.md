# VoucherOCR Application

A production-ready OCR application for processing and validating vouchers/receipts.

## Features

- **OCR Processing**: Supports Tesseract (Default, Contrast, Threshold, Resize) and EasyOCR.
- **Data Parsing**: Automatically extracts Supplier Name, Date, Voucher Number, Line Items, and Totals.
- **Validation UI**: User-friendly interface to review and correct parsed data.
- **Security**: CSRF protection, Security Headers, and Input Validation.
- **Stability**: Database connection pooling, structured logging, and global error handling.

## Tech Stack

- **Backend**: Flask, PostgreSQL (psycopg2), Python
- **Frontend**: HTML5, Tailwind CSS, Vanilla JS
- **OCR**: Tesseract-OCR, EasyOCR, Pillow

## Setup & Installation

### Prerequisites
- Python 3.8+
- PostgreSQL
- Tesseract-OCR installed and in PATH

### 1. Clone & Install Dependencies
```bash
git clone <repository-url>
cd tkfl_ocr/pt4
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Configuration
Create a `.env` file in the root directory:
```ini
FLASK_APP=backend.app
FLASK_ENV=development
SECRET_KEY=your_secure_secret_key
DATABASE_URL=postgresql://user:password@localhost:5432/voucher_db
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### 3. Initialize Database
The application automatically initializes tables on startup. Ensure your PostgreSQL database exists.

### 4. Run the Application
```bash
flask run
```
Access the app at `http://localhost:5000`.

## Project Structure

- `backend/`
  - `config.py`: Configuration classes.
  - `db.py`: Database connection pooling.
  - `routes/`: API and Main routes.
  - `services/`: Business logic (VoucherService, OCR).
  - `templates/`: HTML templates.
  - `static/`: CSS/JS assets.
- `uploads/`: Temporary storage for uploaded images.
- `logs/`: Application logs.

## Security Features

- **CSRF Protection**: All forms and AJAX requests are protected.
- **Security Headers**: HSTS, X-Frame-Options, X-Content-Type-Options.
- **Input Validation**: Secure filename handling and type checks.

## License
MIT
