# TKFL OCR - Technical Documentation

## Overview
The TKFL OCR application is an advanced OCR-based voucher processing system designed to extract structured data from receipt images. It features a production environment and a beta environment for testing new OCR improvements.

## Features
- **OCR Processing**: Utilizes OCR technology to extract text from images.
- **Data Validation**: Allows users to review and validate extracted data before saving.
- **Batch Processing**: Supports bulk uploads and processing of multiple receipts.
- **API Endpoints**: Provides various endpoints for uploading, reviewing, and managing vouchers.

## Architecture
### High-Level Components
- **App Bootstrap**: The application is initiated through `run.py`, which calls `create_app()` from `backend/__init__.py`.
- **Blueprints/Routes**: Organized into main and API routes for handling UI and processing requests.
- **Services**: Contains business logic for managing vouchers and database interactions.

### Data Flow
1. **Upload**: Users upload receipt images via the `/upload` endpoint.
2. **Processing**: The application runs OCR on the uploaded images and extracts relevant data.
3. **Review**: Users can review the extracted data at the `/review/<id>` endpoint.
4. **Validation**: Users validate the data before it is saved to the database.
5. **History**: Users can view all processed receipts at the `/receipts` endpoint.

## Installation
### Prerequisites
- Python 3.x
- Required packages listed in `requirements.txt`

### Setup Steps
1. Clone the repository.
2. Install dependencies: `pip install -r requirements.txt`
3. Start the application: `python run.py`
4. Access the application at `http://localhost:5000`

## API Endpoints
### Production
- `GET /` - Homepage
- `POST /api/upload_file` - Upload and process receipt images.
- `GET /review/<id>` - Review extracted data for a specific voucher.

### Beta V2
- `POST /api/beta_v2/upload` - Upload for beta processing.
- `POST /api/beta_v2/re_extract/<id>` - Re-extract data with different OCR methods.

## Development
### Running Tests
To run tests, use the following command:
```bash
python -m pytest tests/
```

### Code Style
- Follow PEP 8 guidelines.
- Use type hints where applicable.
- Document functions with docstrings.

## Conclusion
This document provides a high-level overview of the TKFL OCR application, its architecture, features, and setup instructions. For further details, refer to the individual module documentation and the README file.