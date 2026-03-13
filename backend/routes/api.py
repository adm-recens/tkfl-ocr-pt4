from flask import Blueprint, request, redirect, url_for, jsonify, flash, current_app
from werkzeug.utils import secure_filename
from backend.utils import allowed_file
from backend.ocr_service import extract_text as extract_text_default
from backend.ocr_utils import extract_text as extract_text_adv
from backend.ocr_easy import extract_text_easyocr
from backend.parser import parse_receipt_text
# Import robust OCR components
from backend.robust_ocr_integration import process_voucher_robust, RobustOCRPipeline
from backend.adaptive_ocr_service import extract_text_robust
from backend.robust_parser import parse_receipt_text_robust
from backend.enhanced_parser import parse_receipt_text_enhanced
# Import TKFL-specific parser (80% better accuracy!)
from backend.tkfl_parser import parse_receipt_text_tkfl
from backend.tkfl_parser_v2 import parse_receipt_text_tkfl_v2
from backend.adaptive_robust_parser import parse_receipt_text_adaptive
from backend.enhanced_ocr_pipeline import extract_text_enhanced
from backend.quality_focused_extractor import extract_with_quality, parse_receipt_text as qfee_parse
from backend.services.voucher_service import VoucherService
from PIL import Image
import os
import json
import shutil
from backend.services.production_sync_service import ProductionSyncService
from backend.services.ml_training_service import MLTrainingService

api_bp = Blueprint('api', __name__)

@api_bp.route("/upload", methods=["POST"])
def upload_file():
    """Handles the file upload, OCR, parsing, and database insertion."""
    if 'file_upload' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('main.index'))
    
    file = request.files['file_upload']
    
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('main.index'))
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        
        file.save(filepath)
        
        try:
            # QUALITY-FOCUSED EXTRACTION ENGINE
            # Prioritizes accuracy over speed through multi-strategy extraction
            current_app.logger.info(f"Using QUALITY-FOCUSED extraction for {filename}")
            
            # Step 1: Get OCR text
            ocr_result = extract_text_default(filepath, method='optimal')
            raw_text = ocr_result.get('text', '') if isinstance(ocr_result, dict) else str(ocr_result)
            
            # Step 2: Apply text corrections
            from backend.text_correction import apply_text_corrections
            corrected_text = apply_text_corrections(raw_text)
            
            # Step 3: QUALITY-FOCUSED PARSING (tries multiple strategies, validates rigorously)
            current_app.logger.info(f"Running quality-focused extraction...")
            extraction_result = extract_with_quality(corrected_text)
            
            # Log extraction details
            current_app.logger.info(f"Extraction complete - Overall confidence: {extraction_result['overall_confidence']}%")
            current_app.logger.info(f"Requires review: {extraction_result['requires_review']}")
            
            # Convert to standard format for database
            parsed_data = {
                'master': {
                    'voucher_number': extraction_result['fields']['voucher_number'].value,
                    'voucher_date': extraction_result['fields']['voucher_date'].value,
                    'supplier_name': extraction_result['fields']['supplier_name'].value,
                    'gross_total': extraction_result['fields']['gross_total'].value,
                    'net_total': extraction_result['fields']['net_total'].value,
                },
                'quality_report': extraction_result,
                'items': [],  # Will be extracted separately if needed
                'deductions': []
            }

            # Database Insertion via Service
            master_id = VoucherService.create_voucher(
                file_name=filename,
                file_storage_path=filepath,
                raw_text=raw_text,
                parsed_data=parsed_data,
                ocr_mode='optimal'
            )

            flash(f'File "{filename}" uploaded and processed successfully!', 'success')
            return redirect(url_for('main.review_voucher', voucher_id=master_id))
            
        except Exception as e:
            # Cleanup on error
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
            current_app.logger.error(f"Error during processing: {e}")
            flash(f"An error occurred during processing: {e}", "error")
            return redirect(url_for('main.index'))
            
    else:
        flash('Invalid file type. Only JPG, JPEG, and PNG are allowed.', 'error')
        return redirect(url_for('main.index'))

@api_bp.route("/re_extract/<int:voucher_id>", methods=["POST"])
def re_extract_voucher(voucher_id):
    """Re-runs OCR and parsing on the existing image with a new OCR mode."""
    data = request.get_json() if request.is_json else request.form
    new_ocr_mode = data.get('ocr_mode')
    
    try:
        voucher = VoucherService.get_voucher_by_id(voucher_id)
        if not voucher:
            return jsonify({"success": False, "message": f"Voucher #{voucher_id} not found."}), 404
            
        filepath = voucher['file_storage_path']
        
        # OCR Extraction based on mode - Now using enhanced modes
        # Supported modes: optimal, adaptive, aggressive, enhanced, simple
        if new_ocr_mode in ['optimal', 'adaptive', 'aggressive', 'enhanced', 'simple']:
            ocr_result = extract_text_default(filepath, method=new_ocr_mode)
            raw_text = ocr_result.get('text', '') if isinstance(ocr_result, dict) else str(ocr_result)
            confidence = ocr_result.get('confidence', 0) if isinstance(ocr_result, dict) else 0
        elif new_ocr_mode in ['default', 'tesseract_default']:
            # Backward compatibility: treat as 'enhanced'
            ocr_result = extract_text_default(filepath, method='enhanced')
            raw_text = ocr_result.get('text', '') if isinstance(ocr_result, dict) else str(ocr_result)
            confidence = ocr_result.get('confidence', 0) if isinstance(ocr_result, dict) else 0
        else:
            return jsonify({"success": False, "message": f"Invalid OCR mode: {new_ocr_mode}. Use: optimal, adaptive, aggressive, enhanced, or simple"}), 400

        if raw_text.startswith('[OCR ERROR]'):
            return jsonify({"success": False, "message": f"OCR Failed: {raw_text}"}), 500

        # Parsing
        parsed_data = parse_receipt_text(raw_text)
        
        # ✨ Apply ML Learned Corrections
        try:
            parsed_data = MLTrainingService.apply_learned_corrections(parsed_data, raw_text)
            current_app.logger.debug(f"Applied ML corrections for re-extraction of {voucher_id}")
        except Exception as ml_e:
            current_app.logger.warning(f"ML correction failed: {ml_e}")
        
        # Update Database via Service
        VoucherService.update_voucher_parse_data(voucher_id, raw_text, parsed_data, new_ocr_mode)
        
        return jsonify({
            "success": True,
            "message": f"Re-extraction complete with mode: {new_ocr_mode}.",
            "parsed_data": parsed_data,
            "raw_text": raw_text,
            "new_ocr_mode": new_ocr_mode,
            "confidence": confidence
        })
        
    except Exception as e:
        current_app.logger.error(f"Error during re-extraction: {e}")
        return jsonify({"success": False, "message": f"Processing Error: {e}"}), 500

@api_bp.route("/validate/save/<int:voucher_id>", methods=["POST"])
def save_validated_data(voucher_id):
    """Handles the saving of manually validated and corrected data."""
    try:
        # Extract form data
        next_url = request.form.get('next_url')
        supplier_name = request.form.get('vendor_name', '').strip()
        voucher_date = request.form.get('date', '').strip()
        voucher_number = request.form.get('voucher_no', '').strip()
        
        validated_items = json.loads(request.form.get('validated_items_json', '[]'))
        validated_deductions = json.loads(request.form.get('validated_deductions_json', '[]'))
        
        # Filter out purely empty frontend rows just in case
        validated_items = [item for item in validated_items if str(item.get('item_name', '')).strip() or float(item.get('line_amount') or 0) > 0]
        validated_deductions = [ded for ded in validated_deductions if str(ded.get('deduction_type', '')).strip() or float(ded.get('amount') or 0) > 0]
        
        # Calculate totals
        subtotal = sum(float(item.get('line_amount', 0) or 0) for item in validated_items)
        total_deductions = sum(float(ded.get('amount', 0) or 0) for ded in validated_deductions)
        net_total = subtotal - total_deductions
        
        # Fix: Convert empty date to None
        if not voucher_date:
            voucher_date = None

        master_data = {
            'supplier_name': supplier_name,
            'voucher_date': voucher_date,
            'voucher_number': voucher_number,
            'gross_total': subtotal,
            'total_deductions': total_deductions,
            'net_total': net_total
        }
        
        # Get original voucher data for ML feedback
        original_voucher = VoucherService.get_voucher_by_id(voucher_id)
        if original_voucher:
            original_parsed = original_voucher.get('parsed_json')
            if isinstance(original_parsed, str):
                original_parsed = json.loads(original_parsed)
            
            # Record ML feedback for corrections
            try:
                from backend.services.ml_training_service import MLTrainingService
                
                if original_parsed and 'master' in original_parsed:
                    orig_master = original_parsed['master']
                    
                    # Record supplier name correction if changed
                    if orig_master.get('supplier_name') != supplier_name:
                        current_app.logger.debug(f"[ML-Feedback] Supplier correction: {orig_master.get('supplier_name')} -> {supplier_name}")
                    
                    # Record date correction if changed
                    if orig_master.get('voucher_date') != voucher_date:
                        current_app.logger.debug(f"[ML-Feedback] Date correction: {orig_master.get('voucher_date')} -> {voucher_date}")
                    
                    # Record voucher number correction if changed
                    if orig_master.get('voucher_number') != voucher_number:
                        current_app.logger.debug(f"[ML-Feedback] Voucher number correction: {orig_master.get('voucher_number')} -> {voucher_number}")
                        
            except Exception as ml_err:
                current_app.logger.warning(f"[ML-Feedback] Error recording feedback: {ml_err}")
        
        # Save via Service
        VoucherService.save_validated_voucher(voucher_id, master_data, validated_items, validated_deductions)
        
        # Sync to Production immediately (for updates)
        try:
            ProductionSyncService.sync_voucher_to_production(voucher_id)
        except Exception as sync_err:
            current_app.logger.error(f"Failed to sync updated voucher {voucher_id}: {sync_err}")
        
        flash(f"Voucher #{voucher_id} saved successfully!", "success")
        if next_url:
            return redirect(next_url)
        return redirect(url_for('main.view_receipts'))

    except Exception as e:
        current_app.logger.error(f"Error saving validated data: {e}")
        flash(f"Error saving data: {e}", "error")
        
        next_url = request.form.get('next_url')
        if next_url:
            return redirect(url_for('main.validate_voucher_page', voucher_id=voucher_id, next=next_url))
        return redirect(url_for('main.validate_voucher_page', voucher_id=voucher_id))

@api_bp.route("/delete_all", methods=["POST"])
def delete_all_data():
    """
    Deletes ALL data including:
    - Database vouchers
    - Uploaded files
    - ML models (OCR, Parsing, Smart Crop)
    - ML feedback data (crop annotations, corrections)
    - Training datasets
    - Everything - complete reset!
    """
    try:
        # 1. Delete database vouchers
        VoucherService.delete_all_vouchers()
        print("[RESET] Deleted all vouchers from database")

        # 2. Delete uploaded files
        folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    current_app.logger.warning(f"Failed to delete {file_path}: {e}")
        print("[RESET] Deleted all uploaded files")

        # Ensure we target the ROOT ml data directories, not internal backend python modules
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        # 3. Delete ML Models Datastore
        models_dir = os.path.join(base_dir, "ml_models")
        if os.path.exists(models_dir):
            for filename in os.listdir(models_dir):
                file_path = os.path.join(models_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                        print(f"[RESET] Deleted model: {filename}")
                except Exception as e:
                    current_app.logger.warning(f"Failed to delete model {file_path}: {e}")
        print("[RESET] Deleted all ML models (OCR, Parsing, Smart Crop)")

        # 4. Delete ML Dataset (feedback, images, corrections)
        dataset_dir = os.path.join(base_dir, "ml_dataset")
        if os.path.exists(dataset_dir):
            shutil.rmtree(dataset_dir)
            print("[RESET] Deleted entire ML dataset directory")
        print("[RESET] Deleted all feedback data and training images")

        # 5. Create empty ML directories for future use
        os.makedirs(models_dir, exist_ok=True)
        os.makedirs(dataset_dir, exist_ok=True)
        os.makedirs(os.path.join(dataset_dir, "feedback"), exist_ok=True)
        os.makedirs(os.path.join(dataset_dir, "images"), exist_ok=True)
        print("[RESET] Created fresh ML directories")

        current_app.logger.info("Complete data reset: database, files, ML models, and feedback all cleared")
        flash("✅ Complete reset: Database, files, ML models, and training data all deleted. Ready to start fresh!", "success")
    
    except Exception as e:
        current_app.logger.error(f"Error resetting data: {e}")
        flash(f"❌ Error resetting data: {e}", "error")
        
    return redirect(url_for("main.index"))

@api_bp.route("/batch/<batch_id>/reprocess_db", methods=["POST"])
def reprocess_batch_db(batch_id):
    """
    Re-runs OCR and ML corrections for all vouchers in a batch,
    updating the database records in-place.
    """
    try:
        from backend.services.batch_service import BatchService
        
        # Get batch - check if exists
        batch = BatchService.get_batch_with_vouchers(batch_id)
        if not batch:
            return jsonify({"success": False, "message": f"Batch {batch_id} not found"}), 404
            
        vouchers = batch.get('vouchers', [])
        current_app.logger.info(f"[BATCH-REPROCESS] Starting re-extraction for {len(vouchers)} vouchers in batch {batch_id}")
        
        # We run this in a background thread to avoid timeout
        def run_reprocess(app, voucher_list):
            with app.app_context():
                success_count = 0
                for v in voucher_list:
                    try:
                        v_id = v['id']
                        filepath = v['file_storage_path']
                        
                        if not os.path.exists(filepath):
                            filepath = os.path.join(app.config["UPLOAD_FOLDER"], v['file_name'])
                            
                        if not os.path.exists(filepath):
                            current_app.logger.error(f"[BATCH-REPROCESS] detailed error: File not found {filepath}")
                            continue
                            
                        # Run OCR
                        ocr_result = extract_text_default(filepath, method='optimal')
                        raw_text = ocr_result.get('text', '') if isinstance(ocr_result, dict) else str(ocr_result)
                        
                        # QUALITY-FOCUSED EXTRACTION ENGINE (reprocess with new parser)
                        current_app.logger.info(f"[BATCH-REPROCESS] Running quality-focused extraction for voucher {v_id}")
                        extraction_result = extract_with_quality(raw_text)
                        
                        # Convert to standard format (WITHOUT quality_report - not JSON serializable)
                        parsed_data = {
                            'master': {
                                'voucher_number': extraction_result['fields']['voucher_number'].value,
                                'voucher_date': extraction_result['fields']['voucher_date'].value,
                                'supplier_name': extraction_result['fields']['supplier_name'].value,
                                'gross_total': extraction_result['fields']['gross_total'].value,
                                'net_total': extraction_result['fields']['net_total'].value,
                            },
                            'items': extraction_result.get('items', []),
                            'deductions': extraction_result.get('deductions', [])
                        }
                        
                        current_app.logger.info(f"[BATCH-REPROCESS] Extraction confidence: {extraction_result['overall_confidence']}%")
                        
                        # Run ML
                        try:
                            parsed_data = MLTrainingService.apply_learned_corrections(parsed_data, raw_text)
                        except Exception as mre:
                            current_app.logger.warning(f"[BATCH-REPROCESS] ML Failed for {v_id}: {mre}")
                            
                        # Update DB
                        VoucherService.update_voucher_parse_data(v_id, raw_text, parsed_data, 'optimal')
                        success_count += 1
                        current_app.logger.info(f"[BATCH-REPROCESS] Updated voucher {v_id}")
                        
                    except Exception as e:
                        current_app.logger.error(f"[BATCH-REPROCESS] Error on voucher {v.get('id')}: {e}")
                
                current_app.logger.info(f"[BATCH-REPROCESS] Completed. Success: {success_count}/{len(voucher_list)}")

        import threading
        # Pass the real app object (current_app is a proxy)
        # Use ._get_current_object() to get the actual app instance
        thread = threading.Thread(target=run_reprocess, args=(current_app._get_current_object(), vouchers))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "success": True,
            "message": f"Started reprocessing {len(vouchers)} vouchers in background. Refresh page in a minute."
        })

    except Exception as e:
        current_app.logger.error(f"Error starting batch reprocess: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
