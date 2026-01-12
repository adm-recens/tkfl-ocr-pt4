"""
Bulk Upload API for Beta_v2
Handles batch processing of multiple receipts with parallel execution
"""

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from concurrent.futures import ThreadPoolExecutor, as_completed
from backend.ocr_service import extract_text
from backend.parser import parse_receipt_text
from backend.db import get_connection
import os
import uuid
import time
from datetime import datetime

api_bulk_bp = Blueprint('api_bulk', __name__)

# In-memory storage for batch processing (simple approach)
batch_store = {}

def cleanup_old_batches():
    """Remove batches older than 1 hour"""
    now = datetime.now()
    to_remove = []
    for batch_id, batch in batch_store.items():
        age = (now - batch['created_at']).seconds
        if age > 3600:  # 1 hour
            to_remove.append(batch_id)
    
    for batch_id in to_remove:
        del batch_store[batch_id]

def allowed_file(filename):
    """Check if file extension is allowed"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_single_receipt(filepath, filename, batch_id):
    """
    Process a single receipt: OCR + Parse + Validate
    Returns structured result
    """
    try:
        # Run Optimal OCR
        ocr_result = extract_text(filepath, method='optimal')
        raw_text = ocr_result.get('text', '') if isinstance(ocr_result, dict) else str(ocr_result)
        confidence = ocr_result.get('confidence', 0) if isinstance(ocr_result, dict) else 0
        
        # Parse with validation
        parsed_data = parse_receipt_text(raw_text)
        
        # Add metadata
        metadata = parsed_data.get('metadata', {})
        validation_warnings = metadata.get('validation_warnings', [])
        corrections = metadata.get('corrections', [])
        
        return {
            'success': True,
            'filename': filename,
            'filepath': filepath,
            'confidence': confidence,
            'parsed_data': parsed_data,
            'validation_warnings': validation_warnings,
            'corrections': corrections,
            'needs_review': confidence < 85 or len(validation_warnings) > 0,
            'error': None
        }
        
    except Exception as e:
        print(f"[ERROR] Error processing {filename}: {e}")
        return {
            'success': False,
            'filename': filename,
            'filepath': filepath,
            'confidence': 0,
            'parsed_data': None,
            'validation_warnings': [],
            'corrections': [],
            'needs_review': True,
            'error': str(e)
        }

@api_bulk_bp.route('/upload', methods=['POST'])
def upload_batch():
    """
    Upload multiple files and start batch processing
    """
    cleanup_old_batches()
    
    if 'files' not in request.files:
        return jsonify({'success': False, 'message': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    
    if not files or len(files) == 0:
        return jsonify({'success': False, 'message': 'No files selected'}), 400
    
    # Generate batch ID
    batch_id = str(uuid.uuid4())
    
    # Save files and collect paths
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    saved_files = []
    
    for file in files:
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add batch_id prefix to avoid conflicts
            unique_filename = f"{batch_id}_{filename}"
            filepath = os.path.join(upload_folder, unique_filename)
            file.save(filepath)
            saved_files.append({
                'filepath': filepath,
                'filename': filename  # Original name for display
            })
    
    if not saved_files:
        return jsonify({'success': False, 'message': 'No valid files uploaded'}), 400
    
    # Initialize batch in store
    batch_store[batch_id] = {
        'batch_id': batch_id,
        'status': 'processing',
        'total': len(saved_files),
        'processed': 0,
        'successful': 0,
        'failed': 0,
        'results': [],
        'created_at': datetime.now()
    }
    
    # Process files in parallel
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all processing tasks
        future_to_file = {
            executor.submit(process_single_receipt, f['filepath'], f['filename'], batch_id): f
            for f in saved_files
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_file):
            try:
                result = future.result()
                results.append(result)
                
                # Update progress
                batch = batch_store[batch_id]
                batch['processed'] += 1
                if result['success']:
                    batch['successful'] += 1
                else:
                    batch['failed'] += 1
                
            except Exception as e:
                print(f"[ERROR] Future execution error: {e}")
                results.append({
                    'success': False,
                    'error': str(e),
                    'needs_review': True
                })
                batch_store[batch_id]['failed'] += 1
                batch_store[batch_id]['processed'] += 1
    
    # Mark as completed
    batch_store[batch_id]['status'] = 'completed'
    batch_store[batch_id]['results'] = results
    
    return jsonify({
        'success': True,
        'batch_id': batch_id,
        'total': len(saved_files),
        'successful': batch_store[batch_id]['successful'],
        'failed': batch_store[batch_id]['failed']
    })

@api_bulk_bp.route('/status/<batch_id>', methods=['GET'])
def batch_status(batch_id):
    """
    Get current status of batch processing
    """
    if batch_id not in batch_store:
        return jsonify({'success': False, 'message': 'Batch not found'}), 404
    
    batch = batch_store[batch_id]
    
    return jsonify({
        'success': True,
        'status': batch['status'],
        'total': batch['total'],
        'processed': batch['processed'],
        'successful': batch['successful'],
        'failed': batch['failed'],
        'progress_percent': int((batch['processed'] / batch['total']) * 100) if batch['total'] > 0 else 0
    })

@api_bulk_bp.route('/results/<batch_id>', methods=['GET'])
def batch_results(batch_id):
    """
    Get all results for a completed batch
    """
    if batch_id not in batch_store:
        return jsonify({'success': False, 'message': 'Batch not found'}), 404
    
    batch = batch_store[batch_id]
    
    if batch['status'] != 'completed':
        return jsonify({'success': False, 'message': 'Batch still processing'}), 400
    
    return jsonify({
        'success': True,
        'batch_id': batch_id,
        'results': batch['results'],
        'total': batch['total'],
        'successful': batch['successful'],
        'failed': batch['failed']
    })

@api_bulk_bp.route('/save/<batch_id>', methods=['POST'])
def save_batch(batch_id):
    """
    Save all validated/corrected vouchers to database
    Accepts corrected data from validation dashboard
    """
    if batch_id not in batch_store:
        return jsonify({'success': False, 'message': 'Batch not found'}), 404
    
    try:
        # Get corrected data from request
        data = request.get_json()
        vouchers = data.get('vouchers', [])
        
        if not vouchers:
            return jsonify({'success': False, 'message': 'No vouchers to save'}), 400
        
        saved_count = 0
        failed_vouchers = []
        
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            for voucher in vouchers:
                try:
                    # Extract master data
                    master = voucher.get('master', {})
                    items = voucher.get('items', [])
                    deductions = voucher.get('deductions', [])
                    filename = voucher.get('filename', 'unknown')
                    filepath = voucher.get('filepath', '')
                    
                    # Insert into vouchers_master_beta
                    cur.execute("""
                        INSERT INTO vouchers_master_beta 
                        (file_name, file_storage_path, voucher_number, voucher_date, 
                         supplier_name, vendor_details, gross_total, total_deductions, net_total, ocr_mode)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        filename, filepath,
                        master.get('voucher_number'), master.get('voucher_date'),
                        master.get('supplier_name'), master.get('vendor_details'),
                        master.get('gross_total'), master.get('total_deductions'),
                        master.get('net_total'), 'optimal'
                    ))
                    
                    master_id = cur.fetchone()[0]
                    
                    # Insert items
                    for item in items:
                        cur.execute("""
                            INSERT INTO voucher_items_beta
                            (voucher_id, item_description, quantity, rate, line_amount)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (
                            master_id,
                            item.get('item_description'),
                            item.get('quantity'),
                            item.get('rate'),
                            item.get('line_amount')
                        ))
                    
                    # Insert deductions
                    for deduction in deductions:
                        cur.execute("""
                            INSERT INTO voucher_deductions_beta
                            (voucher_id, deduction_type, amount)
                            VALUES (%s, %s, %s)
                        """, (
                            master_id,
                            deduction.get('deduction_type'),
                            deduction.get('amount')
                        ))
                    
                    saved_count += 1
                    
                except Exception as e:
                    current_app.logger.error(f"Error saving voucher {filename}: {e}")
                    failed_vouchers.append({
                        'filename': filename,
                        'error': str(e)
                    })
            
            # Commit transaction
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
        
        # Clean up batch from store
        if batch_id in batch_store:
            del batch_store[batch_id]
        
        return jsonify({
            'success': True,
            'saved_count': saved_count,
            'failed_count': len(failed_vouchers),
            'failed_vouchers': failed_vouchers
        })
        
    except Exception as e:
        current_app.logger.error(f"Batch save error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
