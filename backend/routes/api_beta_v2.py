"""
Beta API Routes (V2) - Isolated OCR Experimentation Environment
Uses beta OCR service and beta database tables
Complete isolation from production
"""
from flask import Blueprint, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from backend.utils import allowed_file
from backend.ocr_service_beta import extract_text_beta
from backend.parser_beta import parse_receipt_text
from backend.services.voucher_service_beta import VoucherServiceBeta
from PIL import Image
import os
import json

api_beta_v2_bp = Blueprint('api_beta_v2', __name__, url_prefix='/api/beta_v2')

@api_beta_v2_bp.route("/upload", methods=["POST"])
def upload_file_beta():
    """
    Beta upload endpoint - uses enhanced OCR service
    Stores in separate beta tables
    """
    if 'file_upload' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('main.index'))
    
    file = request.files['file_upload']
    
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('main.index'))
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        # Store in beta directory
        beta_folder = os.path.join(current_app.config["UPLOAD_FOLDER"], "beta_v2")
        os.makedirs(beta_folder, exist_ok=True)
        filepath = os.path.join(beta_folder, filename)
        
        # Check for duplicate file
        if os.path.exists(filepath):
            flash(f'File "{filename}" already exists in beta. Please rename the file or delete the existing one first.', 'error')
            return redirect(url_for('main_beta_v2.upload_page_beta'))
        
        file.save(filepath)
        
        try:
            # AUTO-SELECTION: Run both Enhanced and Experimental modes
            current_app.logger.info(f"[AUTO-SELECT] Testing both modes for {filename}")
            
            # Test Enhanced mode
            current_app.logger.info(f"[AUTO-SELECT] Running Enhanced mode...")
            enhanced_result = extract_text_beta(filepath, method='enhanced')
            enhanced_confidence = enhanced_result['confidence']
            current_app.logger.info(f"[AUTO-SELECT] Enhanced: {enhanced_confidence}%")
            
            # Test Experimental mode
            current_app.logger.info(f"[AUTO-SELECT] Running Experimental mode...")
            experimental_result = extract_text_beta(filepath, method='experimental')
            experimental_confidence = experimental_result['confidence']
            current_app.logger.info(f"[AUTO-SELECT] Experimental: {experimental_confidence}%")
            
            # Auto-select the better mode
            if experimental_confidence > enhanced_confidence:
                selected_mode = 'experimental'
                ocr_result = experimental_result
                winner_margin = experimental_confidence - enhanced_confidence
                current_app.logger.info(f"[AUTO-SELECT] Winner: Experimental (+{winner_margin:.1f}%)")
            else:
                selected_mode = 'enhanced'
                ocr_result = enhanced_result
                winner_margin = enhanced_confidence - experimental_confidence
                current_app.logger.info(f"[AUTO-SELECT] Winner: Enhanced (+{winner_margin:.1f}%)")
            
            # Extract results from winning mode
            raw_text = ocr_result['text']
            ocr_confidence = ocr_result['confidence']
            preprocessing_method = ocr_result['preprocessing_method']
            processing_time_ms = ocr_result['processing_time_ms']
            
            # Beta OCR Processing with enhanced service
            image_obj = Image.open(filepath)
            image_obj.close()
            
            # Parsing (using beta parser)
            parsed_data = parse_receipt_text(raw_text)
            
            # Add auto-selection metadata to parsed_data
            if 'metadata' not in parsed_data:
                parsed_data['metadata'] = {}
            parsed_data['metadata']['auto_selected_mode'] = selected_mode
            parsed_data['metadata']['enhanced_confidence'] = enhanced_confidence
            parsed_data['metadata']['experimental_confidence'] = experimental_confidence
            parsed_data['metadata']['winner_margin'] = round(winner_margin, 1)
            
            # Database Insertion via Beta Service
            master_id = VoucherServiceBeta.create_voucher(
                file_name=filename,
                file_storage_path=filepath,
                raw_text=raw_text,
                parsed_data=parsed_data,
                ocr_mode=f'beta_{selected_mode}',
                preprocessing_method=preprocessing_method,
                ocr_confidence=ocr_confidence,
                processing_time_ms=processing_time_ms
            )

            flash(f'Auto-selected: {selected_mode.title()} ({ocr_confidence:.1f}%) | Enhanced: {enhanced_confidence:.1f}% vs Experimental: {experimental_confidence:.1f}%', 'success')
            return redirect(url_for('main_beta_v2.review_voucher_beta', voucher_id=master_id))
            
        except Exception as e:
            # Cleanup on error
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
            current_app.logger.error(f"Beta OCR error: {e}")
            flash(f"Beta OCR error: {e}", "error")
            return redirect(url_for('main_beta_v2.upload_page_beta'))
            
    else:
        flash('Invalid file type. Only JPG, JPEG, and PNG are allowed.', 'error')
        return redirect(url_for('main_beta_v2.upload_page_beta'))

@api_beta_v2_bp.route("/re_extract/<int:voucher_id>", methods=["POST"])
def re_extract_beta(voucher_id):
    """Re-run beta OCR with different preprocessing method"""
    data = request.get_json() if request.is_json else request.form
    method = data.get('method', 'enhanced')  # enhanced, simple, or experimental
    
    try:
        voucher = VoucherServiceBeta.get_voucher_by_id(voucher_id)
        if not voucher:
            return {"success": False, "message": f"Voucher #{voucher_id} not found."}, 404
            
        filepath = voucher['file_storage_path']
        
        # Re-run OCR with specified method
        ocr_result = extract_text_beta(filepath, method=method)
        raw_text = ocr_result['text']
        
        if raw_text.startswith('[OCR ERROR]'):
            return {"success": False, "message": f"OCR Failed: {raw_text}"}, 500

        # Re-parse
        parsed_data = parse_receipt_text(raw_text)
        
        # Update database
        VoucherServiceBeta.update_voucher_parse_data(
            voucher_id, raw_text, parsed_data, 'beta_enhanced',
            preprocessing_method=ocr_result['preprocessing_method'],
            ocr_confidence=ocr_result['confidence'],
            processing_time_ms=ocr_result['processing_time_ms']
        )
        
        return {
            "success": True,
            "message": f"Re-extraction complete with {method} method.",
            "parsed_data": parsed_data,
            "raw_text": raw_text,
            "confidence": ocr_result['confidence'],
            "processing_time_ms": ocr_result['processing_time_ms'],
            "preprocessing_method": ocr_result['preprocessing_method']
        }
        
    except Exception as e:
        current_app.logger.error(f"Beta re-extraction error: {e}")
        return {"success": False, "message": f"Error: {e}"}, 500
