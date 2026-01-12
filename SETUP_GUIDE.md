# TKFL OCR - Complete Setup Guide

## Prerequisites

Before starting, ensure you have the following installed:

### 1. Python 3.8 or higher
- Download from: https://www.python.org/downloads/
- During installation, check "Add Python to PATH"
- Verify installation:
  ```powershell
  python --version
  ```

### 2. PostgreSQL Database
- Download from: https://www.postgresql.org/download/windows/
- During installation, remember your postgres password
- Default port: 5432
- Verify installation:
  ```powershell
  psql --version
  ```

### 3. Tesseract OCR
- Download from: https://github.com/UB-Mannheim/tesseract/wiki
- Install to default location: `C:\Program Files\Tesseract-OCR\`
- Add to PATH or note the installation path
- Verify installation:
  ```powershell
  tesseract --version
  ```

## Installation Steps

### Step 1: Clone/Navigate to Project
```powershell
cd c:\Users\ramst\Documents\apps\tkfl_ocr\pt4
```

### Step 2: Create Virtual Environment
```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate

# You should see (.venv) in your prompt
```

### Step 3: Install Dependencies
```powershell
# Upgrade pip first
python -m pip install --upgrade pip

# Install all requirements
pip install -r requirements.txt
```

### Step 4: Configure Environment

Create/Update the `.env` file in the project root:
```env
# Database Configuration
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/tkfl_ocr

# Flask Configuration
FLASK_SECRET_KEY=your-secret-key-here-change-this
FLASK_ENV=development
FLASK_DEBUG=1

# Tesseract Configuration
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe

# Upload Configuration
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=16777216
```

**Important:** Replace `YOUR_PASSWORD` with your actual PostgreSQL password.

### Step 5: Database Setup

1. **Create Database:**
   ```powershell
   # Open PostgreSQL shell
   psql -U postgres
   
   # In psql shell:
   CREATE DATABASE tkfl_ocr;
   \q
   ```

2. **Initialize Tables:**
   ```powershell
   # Run the beta database initialization script
   python init_beta_db.py
   ```

   This will create the following table sets:
   - Production tables: `vouchers_master`, `voucher_items`, `voucher_deductions`
   - Beta tables: `vouchers_master_beta`, `voucher_items_beta`, `voucher_deductions_beta`

### Step 6: Verify Installation

Run the dependency test:
```powershell
python test_deps.py
```

Expected output:
```
OpenCV Version: 4.x.x
NumPy Version: 1.x.x
Basic OpenCV test passed!
```

### Step 7: Start the Application

```powershell
python run.py
```

You should see:
```
============================================================
🚀 OCR Application Starting...
============================================================

📍 Access the application at: http://localhost:5000

✅ New Features Active:
   - Optimal OCR Mode (92%+ confidence)
   - Enhanced Parser with Auto-Correction
   - Validation Warnings & Alerts

⏹️  Press Ctrl+C to stop the server

============================================================

 * Debug mode: on
 * Running on http://0.0.0.0:5000
```

Visit http://localhost:5000 in your browser to access the application.

## Application Routes

### Production Environment
- **Homepage:** http://localhost:5000/
- **Upload Receipt:** http://localhost:5000/upload
- **Review Voucher:** http://localhost:5000/review/{voucher_id}
- **Receipts History:** http://localhost:5000/receipts

### Beta V2 Environment (Testing)
- **Beta Upload:** http://localhost:5000/beta_v2/upload
- **Beta Review:** http://localhost:5000/beta_v2/review/{voucher_id}
- **Beta History:** http://localhost:5000/beta_v2/vouchers

### Queue Upload (Batch Processing)
- **Queue Upload:** http://localhost:5000/queue_upload

## ⚠️ IMPORTANT: Using Virtual Environment Correctly

### The Problem
If you just run `python run.py`, it may use your global Python installation instead of the virtual environment where packages are installed.

### The Solution - Always Use Full Path
```powershell
# Correct way to run the application
.\.venv\Scripts\python.exe run.py
```

### Or Create a Helper Script
Create `start.ps1` in the project root:
```powershell
.\.venv\Scripts\python.exe run.py
```

Then run:
```powershell
.\start.ps1
```

### Verify Your Python
Check which Python is being used:
```powershell
python -c "import sys; print(sys.executable)"
```

**Expected:** `C:\Users\ramst\Documents\apps\tkfl_ocr\pt4\.venv\Scripts\python.exe`  
**Wrong:** `C:\Python314\python.exe` (or any other global Python)

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'flask'"
**Solution:** Activate virtual environment and reinstall requirements
```powershell
.venv\Scripts\activate
pip install -r requirements.txt
```

### Issue: "psycopg2.OperationalError: could not connect to server"
**Solution:** 
1. Verify PostgreSQL is running (check Services)
2. Check DATABASE_URL in `.env` has correct password
3. Ensure database `tkfl_ocr` exists

### Issue: "TesseractNotFoundError"
**Solution:** 
1. Verify Tesseract is installed
2. Update `TESSERACT_CMD` in `.env` with correct path
3. Common paths:
   - `C:\Program Files\Tesseract-OCR\tesseract.exe`
   - `C:\Program Files (x86)\Tesseract-OCR\tesseract.exe`

### Issue: Application starts but pages show errors
**Solution:**
1. Check database tables are created:
   ```powershell
   psql -U postgres -d tkfl_ocr
   \dt
   ```
2. Run initialization script if tables missing:
   ```powershell
   python init_beta_db.py
   ```

### Issue: Upload folder errors
**Solution:** Create uploads directory structure:
```powershell
mkdir -p uploads, uploads\beta_v2, uploads\queue
```

## Development Workflow

### Running Tests
```powershell
# Test OCR functionality
python test_ocr_direct.py

# Test parser
python test_phase4_logic.py

# Test database connection
python check_db.py
```

### Database Management
```powershell
# Check database tables
python check_beta_tables.py

# List all vouchers
python list_vouchers.py

# Check specific voucher
python check_beta_voucher.py
```

## Next Steps

1. **Upload a test receipt** at `/upload`
2. **Review the extracted data** and validate accuracy
3. **Test the Beta V2 features** at `/beta_v2/upload` for enhanced OCR
4. **Monitor the logs** for any errors or warnings
5. **Read the README.md** for detailed feature documentation

## Project Structure Overview

```
pt4/
├── backend/                 # Main application code
│   ├── __init__.py         # Flask app factory
│   ├── app.py              # Entry point
│   ├── config.py           # Configuration
│   ├── db.py               # Database connection
│   ├── ocr_service.py      # Production OCR
│   ├── ocr_service_beta.py # Enhanced Beta OCR
│   ├── parser.py           # Production parser
│   ├── parser_beta.py      # Enhanced Beta parser
│   ├── routes/             # Route blueprints
│   ├── services/           # Business logic
│   ├── templates/          # HTML templates
│   └── static/             # CSS, JS, images
├── uploads/                # Uploaded receipt images
├── .venv/                  # Virtual environment
├── .env                    # Environment configuration
├── requirements.txt        # Python dependencies
├── run.py                  # Application launcher
└── README.md              # Project documentation
```

## Support

For issues or questions:
1. Check the [README.md](README.md) for detailed documentation
2. Review the troubleshooting section above
3. Check application logs in the `logs/` directory
4. Examine the `.env` file for configuration issues

## Security Notes

- ⚠️ Change `FLASK_SECRET_KEY` in production
- ⚠️ Never commit `.env` file to version control
- ⚠️ Use strong PostgreSQL passwords
- ⚠️ Disable DEBUG mode in production
