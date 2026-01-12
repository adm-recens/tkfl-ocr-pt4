"""
Queue Management API for Wizard Workflow
Session-based queue storage for guided receipt processing
"""

from flask import Blueprint, request, jsonify, current_app, session
from werkzeug.utils import secure_filename
from backend.ocr_service import extract_text
from backend.parser import parse_receipt_text
from backend.db import get_connection
import os
import uuid
from datetime import datetime
from backend.services.batch_service import BatchService
import hashlib

def calculate_file_hash(filepath):
    """Calculate MD5 hash of a file"""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

api_queue_bp = Blueprint('api_queue', __name__)

import json
from backend.services.batch_service import BatchService

api_queue_bp = Blueprint('api_queue', __name__)

# Persistent Queue Storage
QUEUE_STORE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'queue_store.json')

def load_queue_store():
    """Load queue store from JSON file"""
    try:
        if os.path.exists(QUEUE_STORE_FILE):
            with open(QUEUE_STORE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load queue store: {e}")
    return {}

def save_queue_store(store):
    """Save queue store to JSON file"""
    try:
        os.makedirs(os.path.dirname(QUEUE_STORE_FILE), exist_ok=True)
        with open(QUEUE_STORE_FILE, 'w') as f:
            json.dump(store, f, indent=4, default=str)
    except Exception as e:
        print(f"[ERROR] Failed to save queue store: {e}")

# Initialize local store from file
queue_store = load_queue_store()

def allowed_file(filename):
    """Check if file extension is allowed"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@api_queue_bp.route('/create', methods=['POST'])
def create_queue():
    """
    Upload multiple files and create processing queue
    """
    if 'files' not in request.files:
        return jsonify({'success': False, 'message': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    
    if not files or len(files) == 0:
        return jsonify({'success': False, 'message': 'No files selected'}), 400
    
    # Generate queue ID
    queue_id = str(uuid.uuid4())
    
    # Save files
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
        
    saved_files = []
    
    # Create batch reference
    batch_name = request.form.get('batch_name')
    batch_id = BatchService.create_batch(batch_name=batch_name, total_files=len(files))
    
    for file in files:
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = f"{queue_id}_{filename}"
            filepath = os.path.join(upload_folder, unique_filename)
            file.save(filepath)

            # Metadata Logging
            try:
                conn = get_connection()
                cur = conn.cursor()
                
                file_hash = calculate_file_hash(filepath)
                file_size = os.path.getsize(filepath)
                
                cur.execute("""
                    INSERT INTO file_lifecycle_meta
                    (original_filename, stored_filename, file_path, file_size_bytes, file_hash, mime_type, 
                     upload_batch_id, source_type, client_ip, user_agent, processing_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    filename,
                    unique_filename,
                    filepath,
                    file_size,
                    file_hash,
                    file.content_type,
                    batch_id,
                    'web_bulk_upload',
                    request.remote_addr,
                    request.user_agent.string,
                    'pending'
                ))
                conn.commit()
            except Exception as e:
                print(f"[ERROR] Failed to save file metadata: {e}")
            
            saved_files.append({
                'original_filename': filename,
                'original_path': filepath,
                'cropped_path': None,
                'ocr_result': None,
                'parsed_data': None,
                'validated_data': None,
                'status': 'pending'  # pending, processing, validated, skipped
            })
            print(f"[DEBUG] Saved file: {filename} to {filepath}")
        else:
            print(f"[DEBUG] Skipped invalid file: {file.filename}")
    
    print(f"[DEBUG] Create Queue: {len(saved_files)} valid files saved")
    
    if not saved_files:
        return jsonify({'success': False, 'message': 'No valid files uploaded'}), 400
    
    # Create queue object
    queue_data = {
        'queue_id': queue_id,
        'batch_id': batch_id,
        'files': saved_files,
        'current_index': 0,
        'total': len(saved_files),
        'completed': 0,
        'skipped': 0,
        'created_at': datetime.now().isoformat() # ISO format for JSON serialization
    }
    
    # Update in-memory and persistent store
    queue_store[queue_id] = queue_data
    save_queue_store(queue_store)
    
    # Store queue_id in session for easy access
    session['current_queue_id'] = queue_id
    
    return jsonify({
        'success': True,
        'queue_id': queue_id,
        'total': len(saved_files)
    })

@api_queue_bp.route('/<queue_id>/current', methods=['GET'])
def get_current_receipt(queue_id):
    """
    Get current receipt to process
    """
    if queue_id not in queue_store:
        return jsonify({'success': False, 'message': 'Queue not found'}), 404
        
    queue = queue_store[queue_id]
    current_index = queue['current_index']
    
    # DEBUG LOG
    print(f"[DEBUG] Queue {queue_id}: State Dump -> Index: {current_index}, Total: {queue['total']}, Type: {type(queue['total'])}")
    print(f"[DEBUG] Queue {queue_id}: Files Array Length: {len(queue.get('files', []))}")

    # Check termination condition FIRST
    if current_index >= queue['total']:
        print(f"[DEBUG] Queue {queue_id}: COMPLETED")
        return jsonify({
            'success': True,
            'completed': True,
            'completed_count': queue['completed'],
            'skipped_count': queue['skipped'],
            'progress': {
                'current': queue['total'],
                'total': queue['total'],
                'percent': 100
            }
        })
    

    
    # Safe Total Check
    # FORCE INT CAST
    try:
        total = int(queue.get('total', 0))
    except (ValueError, TypeError):
        total = 0
        
    print(f"[DEBUG] Queue {queue_id}: Retrieved total={total} (type={type(total)})")

    if total == 0:
        print(f"[DEBUG] Queue {queue_id}: Total is 0! forcing completion.")
        return jsonify({
            'success': True,
            'completed': True,
            'completed_count': 0,
            'skipped_count': 0
        })

    # Retrieve current file
    try:
        current_file = queue['files'][current_index]
        print(f"[DEBUG] Retrieved file: {current_file.get('original_file', 'unknown')}")
    except IndexError:
        print(f"[ERROR] Index {current_index} out of bounds for files list (len={len(queue['files'])})")
        return jsonify({'success': False, 'message': 'Index error'}), 500
    
    # Safe percent
    percent = 0
    if total > 0:
        percent = int(((current_index) / total) * 100)

    return jsonify({
        'success': True,
        'completed': False,
        'current_index': current_index,
        'total': total,
        'current_file': {
            'filename': current_file['original_filename'],
            'original_path': current_file['original_path'],
            'cropped_path': current_file.get('cropped_path'),
            'status': current_file['status']
        },
        'progress': {
            'current': current_index + 1,
            'total': total,
            'percent': percent
        },
        # Add missing fields needed by frontend
        'ocr_confidence': current_file.get('ocr_result', {}).get('confidence', 0) if current_file.get('ocr_result') else 0,
        'parsed_data': current_file.get('parsed_data')
    })

@api_queue_bp.route('/<queue_id>/crop', methods=['POST'])
def save_crop(queue_id):
    """
    Save cropped image for current receipt
    """
    if queue_id not in queue_store:
        return jsonify({'success': False, 'message': 'Queue not found'}), 404
    
    queue = queue_store[queue_id]
    current_index = queue['current_index']
    
    if 'cropped_image' not in request.files:
        return jsonify({'success': False, 'message': 'No cropped image provided'}), 400
    
    cropped_file = request.files['cropped_image']
    
    # Save cropped image
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    cropped_filename = f"{queue_id}_cropped_{current_index}.jpg"
    cropped_path = os.path.join(upload_folder, cropped_filename)
    cropped_file.save(cropped_path)
    
    # Update queue
    queue['files'][current_index]['cropped_path'] = cropped_path
    queue['files'][current_index]['status'] = 'cropped'
    save_queue_store(queue_store)
    
    return jsonify({'success': True})

@api_queue_bp.route('/<queue_id>/skip_crop', methods=['POST'])
def skip_crop(queue_id):
    """
    Skip cropping, use original image
    """
    if queue_id not in queue_store:
        return jsonify({'success': False, 'message': 'Queue not found'}), 404
    
    queue = queue_store[queue_id]
    current_index = queue['current_index']
    
    # Mark as using original
    queue['files'][current_index]['cropped_path'] = None
    queue['files'][current_index]['status'] = 'crop_skipped'
    save_queue_store(queue_store)
    
    return jsonify({'success': True})

@api_queue_bp.route('/<queue_id>/ocr', methods=['POST'])
def run_ocr(queue_id):
    """
    Run OCR on current receipt (cropped or original)
    """
    print(f"[OCR] Starting OCR for queue_id: {queue_id}")
    
    if queue_id not in queue_store:
        print(f"[OCR] Error: Queue {queue_id} not found")
        return jsonify({'success': False, 'message': 'Queue not found'}), 404
    
    queue = queue_store[queue_id]
    current_index = queue['current_index']
    current_file = queue['files'][current_index]
    
    print(f"[OCR] Processing file {current_index}: {current_file['original_filename']}")
    
    # Use cropped image if available, otherwise original
    image_path = current_file.get('cropped_path') or current_file['original_path']
    print(f"[OCR] Using image: {image_path}")
    
    try:
        # Check if file exists
        if not os.path.exists(image_path):
            print(f"[OCR] Error: Image file not found at {image_path}")
            return jsonify({'success': False, 'message': f'Image file not found: {image_path}'}), 400
        
        print(f"[OCR] Running OCR with optimal mode...")
        # Run OCR
        ocr_result = extract_text(image_path, method='optimal')
        print(f"[OCR] OCR complete, result type: {type(ocr_result)}")
        
        raw_text = ocr_result.get('text', '') if isinstance(ocr_result, dict) else str(ocr_result)
        confidence = ocr_result.get('confidence', 0) if isinstance(ocr_result, dict) else 0
        
        print(f"[OCR] Confidence: {confidence}, Text length: {len(raw_text)}")
        print(f"[OCR] Running parser...")
        
        # Parse
        parsed_data = parse_receipt_text(raw_text)
        print(f"[OCR] Parser complete")
        
        # Store results
        queue['files'][current_index]['ocr_result'] = {
            'text': raw_text,
            'confidence': confidence
        }
        queue['files'][current_index]['parsed_data'] = parsed_data
        queue['files'][current_index]['status'] = 'ocr_complete'
        save_queue_store(queue_store)
        
        print(f"[OCR] Success! Returning data...")
        
        return jsonify({
            'success': True,
            'confidence': confidence,
            'parsed_data': parsed_data
        })
        
    except Exception as e:
        print(f"[OCR] Exception occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@api_queue_bp.route('/<queue_id>/validate', methods=['POST'])
def validate_receipt(queue_id):
    """
    Save validated data and move to next receipt
    """
    if queue_id not in queue_store:
        return jsonify({'success': False, 'message': 'Queue not found'}), 404
    
    queue = queue_store[queue_id]
    current_index = queue['current_index']
    
    # Get validated data from request
    validated_data = request.get_json()
    
    # Store validated data
    queue['files'][current_index]['validated_data'] = validated_data
    queue['files'][current_index]['status'] = 'validated'
    queue['completed'] += 1
    
    # Move to next
    queue['current_index'] += 1
    save_queue_store(queue_store)
    
    return jsonify({
        'success': True,
        'next_index': queue['current_index'],
        'completed': queue['current_index'] >= queue['total']
    })

@api_queue_bp.route('/<queue_id>/skip', methods=['POST'])
def skip_receipt(queue_id):
    """
    Skip current receipt and move to next
    """
    if queue_id not in queue_store:
        return jsonify({'success': False, 'message': 'Queue not found'}), 404
    
    queue = queue_store[queue_id]
    current_index = queue['current_index']
    
    # Mark as skipped
    queue['files'][current_index]['status'] = 'skipped'
    queue['skipped'] += 1
    
    # Move to next
    queue['current_index'] += 1
    save_queue_store(queue_store)
    
    return jsonify({
        'success': True,
        'next_index': queue['current_index'],
        'completed': queue['current_index'] >= queue['total']
    })

@api_queue_bp.route('/<queue_id>/previous', methods=['POST'])
def go_previous(queue_id):
    """
    Go back to previous receipt
    """
    if queue_id not in queue_store:
        return jsonify({'success': False, 'message': 'Queue not found'}), 404
    
    queue = queue_store[queue_id]
    
    if queue['current_index'] > 0:
        queue['current_index'] -= 1
        save_queue_store(queue_store)
    
    return jsonify({
        'success': True,
        'current_index': queue['current_index']
    })

@api_queue_bp.route('/<queue_id>/save_batch', methods=['POST'])
def save_batch(queue_id):
    """
    Save all validated receipts to database
    """
    if queue_id not in queue_store:
        return jsonify({'success': False, 'message': 'Queue not found'}), 404
    
    queue = queue_store[queue_id]
    validated_files = [f for f in queue['files'] if f['status'] == 'validated' and f.get('validated_data')]
    
    if not validated_files:
        return jsonify({'success': False, 'message': 'No validated receipts to save'}), 400
    
    try:
        saved_count = 0
        failed_vouchers = []
        batch_id = queue.get('batch_id')
        
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            for file_info in validated_files:
                try:
                    # Start a sub-transaction for this voucher
                    cur.execute("SAVEPOINT sp_save_voucher")
                    
                    data = file_info['validated_data']
                    master = data.get('master', {})
                    items = data.get('items', [])
                    deductions = data.get('deductions', [])
                    
                    # Insert master
                    cur.execute("""
                        INSERT INTO vouchers_master 
                        (file_name, file_storage_path, voucher_number, voucher_date, 
                         supplier_name, vendor_details, gross_total, total_deductions, net_total, ocr_mode, batch_id, ocr_confidence, parsed_json)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        file_info['original_filename'],
                        file_info.get('cropped_path') or file_info['original_path'],
                        master.get('voucher_number'),
                        master.get('voucher_date'),
                        master.get('supplier_name'),
                        master.get('vendor_details'),
                        master.get('gross_total'),
                        master.get('total_deductions'),
                        master.get('net_total'),
                        'optimal',
                        batch_id,
                        file_info.get('ocr_result', {}).get('confidence', 0),
                        json.dumps(data, ensure_ascii=False)
                    ))
                    
                    master_id = cur.fetchone()['id']
                    
                    # Insert items
                    for item in items:
                        cur.execute("""
                            INSERT INTO voucher_items
                            (master_id, item_name, quantity, unit_price, line_amount)
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
                            INSERT INTO voucher_deductions
                            (master_id, deduction_type, amount)
                            VALUES (%s, %s, %s)
                        """, (
                            master_id,
                            deduction.get('deduction_type'),
                            deduction.get('amount')
                        ))
                    
                    # If we get here, this voucher is good
                    cur.execute("RELEASE SAVEPOINT sp_save_voucher")
                    saved_count += 1
                    
                    # Update Lifecycle Metadata
                    try:
                        cur.execute("""
                            UPDATE file_lifecycle_meta
                            SET voucher_id = %s, processing_status = 'processed', processed_at = CURRENT_TIMESTAMP
                            WHERE file_path = %s
                        """, (master_id, file_info['original_path']))
                    except Exception as e:
                        print(f"[WARN] Failed to update lifecycle meta for {master_id}: {e}")
                    
                except Exception as e:
                    # Rollback this specific voucher but keep the connection alive
                    cur.execute("ROLLBACK TO SAVEPOINT sp_save_voucher")
                    
                    print(f"[ERROR] Save failed for {file_info['original_filename']}: {e}")
                    failed_vouchers.append({
                        'filename': file_info['original_filename'],
                        'error': str(e)
                    })
                    
                    # Insert a placeholder record for the failed voucher so it appears in the UI
                    try:
                        cur.execute("SAVEPOINT sp_save_failed")
                        cur.execute("""
                            INSERT INTO vouchers_master 
                            (file_name, file_storage_path, supplier_name, vendor_details, batch_id, net_total)
                            VALUES (%s, %s, 'UPLOAD FAILED', %s, %s, 0)
                        """, (
                            file_info['original_filename'],
                            file_info.get('cropped_path') or file_info['original_path'],
                            str(e),
                            batch_id
                        ))
                        cur.execute("RELEASE SAVEPOINT sp_save_failed")
                    except Exception as ie:
                        print(f"[ERROR] Failed to insert failure placeholder: {ie}")
                        cur.execute("ROLLBACK TO SAVEPOINT sp_save_failed")
            
            conn.commit()
            
            # Update batch stats and complete/close it
            if batch_id:
                BatchService.update_batch_stats(
                    batch_id, 
                    success_count=saved_count, 
                    failure_count=len(failed_vouchers)
                )
                BatchService.complete_batch(batch_id)
            
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
        
        # Clean up queue
        if queue_id in queue_store:
            del queue_store[queue_id]
            save_queue_store(queue_store)
        
        return jsonify({
            'success': True,
            'batch_id': batch_id,
            'saved_count': saved_count,
            'failed_count': len(failed_vouchers),
            'failed_vouchers': failed_vouchers
        })
        
    except Exception as e:
        print(f"[ERROR] Batch save error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
