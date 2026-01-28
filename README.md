# 🧾 TKFL OCR - Advanced Voucher Processing System

![Version](https://img.shields.io/badge/version-2.0-blue)
![Python](https://img.shields.io/badge/Python-3.8+-green)
![Flask](https://img.shields.io/badge/Flask-2.0+-red)
![Database](https://img.shields.io/badge/PostgreSQL-12+-blue)

**TKFL OCR** is an advanced Optical Character Recognition (OCR) system for automated voucher processing. It extracts structured data from receipt images, learns from user corrections, and provides transparent ML training insights.

---

## 🌟 Key Features

### 📸 OCR Processing
- **Tesseract Integration**: Advanced OCR with automatic image preprocessing
- **Smart Preprocessing**: Auto-deskew, contrast enhancement, binarization
- **Multiple OCR Methods**: Optimal PSM 4, Standard PSM 6, Adaptive, Aggressive modes
- **Confidence Scoring**: Calculates OCR reliability (0-100%)
- **Dynamic Whitelisting**: Reduces OCR errors through character filtering
- **Multi-Scale Analysis**: Handles various image qualities and resolutions

### 📋 Intelligent Parsing
- **Field Extraction**: Automatically extracts 8+ core fields from vouchers
  - Voucher number, date, supplier name, vendor details
  - Gross total, net total, total deductions
  - Items (quantity, unit price, line amount)
  - Deductions (type and amount)
- **Flexible Format Support**: Handles multiple date formats and number styles
- **Text Correction**: Auto-fixes common OCR errors before parsing
- **Math Verification**: Validates totals and calculations
- **Deduction Categorization**: Automatically categorizes deduction types

### ✅ Validation & Review
- **Rich Review Interface**: Edit and validate extracted data
- **Editable Form Fields**: All fields can be corrected by users
- **Items & Deductions Tables**: Manage line items and deductions
- **Real-time Calculations**: Auto-calculates totals and line amounts
- **Correction Tracking**: Records all user corrections for ML training

### 🤖 ML Training System
- **Auto-Learning**: Models learn from user corrections
- **Correction Deduplication**: Prevents training on same correction twice
- **Pattern Extraction**: Identifies and learns OCR correction patterns
- **Performance Metrics**: Tracks OCR and parsing model accuracy
- **Model Status Dashboard**: Shows trained patterns and model statistics

### 📊 Learning Transparency System
- **Learning History Page**: Complete dashboard of what models have learned
- **Session Tracking**: Records every training session with details
- **Pattern Visualization**: Shows specific corrections learned by field
- **Learning Statistics**: Total corrections, patterns, fields trained
- **Real-time Updates**: Learning history updates after each training

### 📈 Interactive Data Tables
- **DataTables Integration**: Professional data table with advanced features
- **Search**: Real-time full-text search across all fields
- **Sorting**: Click column headers to sort ascending/descending
- **Filtering**: Filter by any column
- **Page Size Selection**: Choose 5, 10, 25, or 50 rows per page
- **Responsive Design**: Works on desktop, tablet, mobile

### 🏢 Supplier Management
- **Supplier Directory**: Complete supplier database
- **Supplier Profiles**: View supplier details and transaction history
- **Receipts by Supplier**: See all receipts from specific suppliers
- **Supplier Analytics**: Track supplier statistics

### 📁 Batch Processing
- **Bulk Upload**: Process multiple receipts in one batch
- **Batch Tracking**: Monitor processing status per batch
- **Batch Summary**: Overview of all batches with completion status
- **Error Handling**: Detailed error reporting for failed uploads

### 🔍 Advanced Features
- **Duplicate Detection**: Identify potentially duplicate vouchers
- **Data History**: Complete audit trail of all changes
- **File Tracking**: Know exactly which image produced which data
- **Metadata Preservation**: Keep original OCR output separate from corrections
- **JSON Export**: Export parsed data in structured format

## 🛠 Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Backend** | Flask | 2.0+ |
| **Language** | Python | 3.8+ |
| **Database** | PostgreSQL | 12+ |
| **OCR Engine** | Tesseract | 5.x |
| **Image Processing** | OpenCV, Pillow | Latest |
| **Frontend Framework** | Tailwind CSS | 3.0+ |
| **Data Tables** | DataTables | 1.13.8 |
| **JavaScript** | jQuery | 3.7.0 |
| **Templating** | Jinja2 | 3.0+ |

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL 12+
- Tesseract OCR 5.x

### Installation

1. **Clone repository**
   ```bash
   git clone https://github.com/adm-recens/tkfl-ocr-pt4.git
   cd tkfl_ocr/pt5
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Linux/macOS
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Tesseract OCR**
   - **Windows**: Download from https://github.com/UB-Mannheim/tesseract/wiki
   - **Linux**: `sudo apt-get install tesseract-ocr`
   - **macOS**: `brew install tesseract`

5. **Configure database**
   - Edit `backend/config.py` with your PostgreSQL connection
   - Initialize database: `python backend/db.py`

6. **Run application**
   ```bash
   python run.py
   ```
   - Access at http://localhost:5000

## 📖 Usage Guide

### Uploading a Voucher
1. Click **"Upload Receipt"** button
2. Select image file or take photo
3. Optional: Crop/rotate image using the crop tool
4. Click **"Process"** to extract data via OCR

### Reviewing Results
1. View extracted data in the review form
2. All fields are editable - make corrections as needed
3. Edit **Items** and **Deductions** tables if needed
4. Click **"Save Corrections"** to record data

### Training the ML Models
1. After reviewing and correcting, click **"Train Models"**
2. Models learn from your corrections
3. See **"Learning History"** to view what models learned
4. As you correct more, models become more accurate

### Viewing Learning History
1. Go to **"ML Training"** menu
2. Click **"View Learning History"**
3. See all sessions, patterns learned, and statistics
4. Each field shows specific corrections the model learned

### Searching Receipts
1. Go to **"All Receipts"** page
2. Use search box for any field (voucher number, date, supplier, etc.)
3. Sort by clicking column headers
4. Filter results as needed
5. Export data if needed

## 📋 Project Structure

```
tkfl_ocr/pt5/
├── backend/
│   ├── __init__.py                 # Flask app initialization
│   ├── app.py                      # Main application file
│   ├── config.py                   # Configuration settings
│   ├── db.py                       # Database connection
│   ├── errors.py                   # Error definitions
│   ├── logger.py                   # Logging setup
│   │
│   ├── ocr_service.py             # OCR processing core
│   ├── parser.py                   # Voucher data extraction
│   ├── security.py                 # Security utilities
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── main.py                # Main UI routes
│   │   ├── api.py                 # REST API endpoints
│   │   ├── learning.py            # Learning history API
│   │   └── training.py            # ML training routes
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── learning_history_tracker.py  # Learning tracker
│   │   └── voucher_service.py           # Database operations
│   │
│   ├── templates/
│   │   ├── base.html              # Base template
│   │   ├── index.html             # Homepage
│   │   ├── upload.html            # Upload form
│   │   ├── review.html            # Review/edit interface
│   │   ├── receipts.html          # Receipts list
│   │   ├── training.html          # ML training hub
│   │   ├── learning_history.html  # Learning dashboard
│   │   └── suppliers.html         # Supplier directory
│   │
│   ├── static/
│   │   ├── css/                   # Stylesheets
│   │   └── js/                    # JavaScript files
│   │
│   ├── data/
│   │   └── learning_history.json  # ML learning persistence
│   │
│   └── migrations/                # Database migrations
│
├── uploads/                       # User uploaded files
├── tests/                         # Test suite
├── logs/                          # Application logs
│
├── requirements.txt               # Python dependencies
├── run.py                        # Application entry point
├── README.md                     # This file
├── SETUP_GUIDE.md               # Detailed setup instructions
└── technical_documentation.md    # Technical architecture docs
```

## 🔌 API Reference

### Upload & Processing
- **POST** `/api/upload_file` - Upload and process receipt image
- **GET** `/api/voucher/<id>` - Get voucher details
- **POST** `/api/voucher/<id>/save` - Save corrections to voucher
- **DELETE** `/api/voucher/<id>` - Delete a voucher

### Learning & Training
- **POST** `/api/train` - Train models from corrections
- **GET** `/api/learning/page` - Get learning history page
- **GET** `/api/learning/history` - Get full learning history JSON
- **GET** `/api/learning/summary` - Get learning summary statistics
- **GET** `/api/learning/report` - Get text report of learning

### Data Access
- **GET** `/api/vouchers` - List all vouchers with pagination
- **GET** `/api/suppliers` - List all suppliers
- **GET** `/api/supplier/<id>/vouchers` - Get vouchers by supplier

## 🗄️ Database Schema

### Core Tables
- **vouchers_master** - Voucher headers (number, date, supplier, totals)
- **voucher_items** - Line items (quantity, price, amount)
- **voucher_deductions** - Deductions (type, amount)
- **suppliers** - Supplier information
- **batches** - Batch upload tracking

### Metadata Tables
- **file_tracking** - Maps images to extracted data
- **training_data** - ML training corrections
- **learning_history** - ML learning sessions and patterns

## 🤖 ML System Architecture

### Correction Collection
1. User reviews OCR results
2. User makes corrections to any field
3. Corrections are saved with OCR confidence scores
4. System prevents duplicate corrections from being trained twice

### Model Training
1. **OCR Correction Model**: Learns patterns in what Tesseract got wrong
2. **Parsing Correction Model**: Learns field extraction improvements
3. Models trained on deduplicat corrections only
4. Each model tracks patterns by field

### Learning Transparency
1. All training sessions recorded with:
   - Timestamp and corrections learned
   - Specific field improvements
   - Pattern extraction results
2. Dashboard shows exactly what models learned:
   - How many corrections used
   - Which fields improved most
   - Specific OCR→Corrected examples
3. Learning history persisted in JSON for audit trail

## 🔒 Security Features

- **CSRF Protection**: All forms CSRF-protected
- **SQL Injection Prevention**: Parameterized queries throughout
- **Input Validation**: All user inputs validated and sanitized
- **Secure File Upload**: Files validated before processing
- **Session Management**: Secure Flask session handling

## 🐛 Troubleshooting

### Tesseract Not Found
- Verify Tesseract installation: `tesseract --version`
- Update path in `backend/config.py` if needed
- Restart application after installation

### OCR Not Extracting Text
- Check image quality - ensure receipt is readable
- Try uploading a clearer image
- Check Tesseract configuration in `backend/config.py`

### Database Connection Error
- Verify PostgreSQL is running
- Check connection string in `backend/config.py`
- Ensure database exists and user has access

### Models Not Learning
- Check `backend/data/learning_history.json` file exists
- Verify corrections are being saved properly
- Check application logs for errors

## 📝 Development

### Running Tests
```bash
python -m pytest tests/ -v
```

### Code Style
- Follow PEP 8 guidelines
- Use type hints where applicable
- Document functions with docstrings
- Max line length: 100 characters

### Adding New Features
1. Create feature branch: `git checkout -b feature/my-feature`
2. Make changes and test thoroughly
3. Commit: `git commit -m "Add feature description"`
4. Push: `git push origin feature/my-feature`
5. Submit Pull Request

## 📄 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

- **Tesseract OCR Team** - Core OCR engine
- **Flask Community** - Web framework
- **DataTables** - Interactive tables
- **Tailwind CSS** - Styling framework
- **PostgreSQL** - Robust database

## 📞 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed setup
- See [technical_documentation.md](technical_documentation.md) for architecture
