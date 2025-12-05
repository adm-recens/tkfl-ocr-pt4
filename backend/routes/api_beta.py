from flask import Blueprint, request, redirect, url_for, jsonify, flash, current_app
from werkzeug.utils import secure_filename
from backend.utils import allowed_file
from backend.ocr_roi_service import extract_with_roi
from backend.parser_roi import parse_by_regions
from backend.services.voucher_service import VoucherService
from PIL import Image
import os
import json

api_beta_bp = Blueprint('api_beta', __name__)

@api_beta_bp.route("/upload_beta", methods=["POST"])
def upload_file_beta():
    """
    Beta upload route with advanced ROI-based OCR preprocessing.
    """
    if 'file_upload' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('main.upload_beta_page'))
    
    file = request.files['file_upload']
    
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('main.upload_beta_page'))
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        # Save to beta folder
        beta_folder = os.path.join(current_app.config["UPLOAD_FOLDER"], "beta")
        os.makedirs(beta_folder, exist_ok=True)
        filepath = os.path.join(beta_folder, filename)
        
        file.save(filepath)
        
        try:
            # ROI-based OCR Processing
            extracted_text_data = extract_with_roi(filepath)
            
            if 'error' in extracted_text_data:
                flash(f"OCR Error: {extracted_text_data['error']}", "error")
                return redirect(url_for('main.upload_beta_page'))
            
            # Region-based Parsing
            parsed_data = parse_by_regions(extracted_text_data)
            
            if 'error' in parsed_data:
                flash(f"Parsing Error: {parsed_data['error']}", "error")
                return redirect(url_for('main.upload_beta_page'))
            
            # Store raw text
            raw_text = extracted_text_data.get('full_text', '')
            
            # Database Insertion via Service
            master_id = VoucherService.create_voucher(
                file_name=filename,
                file_storage_path=filepath,
                raw_text=raw_text,
                parsed_data=parsed_data,
                ocr_mode='roi_beta'  # Flag as beta
            )

            flash(f'File "{filename}" processed with Beta ROI OCR!', 'success')
            return redirect(url_for('main.review_voucher_beta', voucher_id=master_id))
            
        except Exception as e:
            # Cleanup on error
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
            current_app.logger.error(f"Error during beta processing: {e}")
            flash(f"An error occurred during processing: {e}", "error")
            return redirect(url_for('main.upload_beta_page'))
            
    else:
        flash('Invalid file type. Only JPG, JPEG, and PNG are allowed.', 'error')
        return redirect(url_for('main.upload_beta_page'))

@api_beta_bp.route("/re_extract_beta/<int:voucher_id>", methods=["POST"])
def re_extract_beta(voucher_id):
    """
    Re-run ROI-based OCR on an existing voucher.
    """
    try:
        voucher = VoucherService.get_voucher_by_id(voucher_id)
        if not voucher:
            return jsonify({"success": False, "message": f"Voucher #{voucher_id} not found."}), 404
            
        filepath = voucher['file_storage_path']
        
        # ROI-based extraction
        extracted_text_data = extract_with_roi(filepath)
        
        if 'error' in extracted_text_data:
            return jsonify({"success": False, "message": extracted_text_data['error']}), 500
        
        # Region-based parsing
        parsed_data = parse_by_regions(extracted_text_data)
        
        if 'error' in parsed_data:
            return jsonify({"success": False, "message": parsed_data['error']}), 500
        
        raw_text = extracted_text_data.get('full_text', '')
        
        # Update Database via Service
        VoucherService.update_voucher_parse_data(voucher_id, raw_text, parsed_data, 'roi_beta')
        
        return jsonify({
            "success": True,
            "message": "Re-extraction complete with Beta ROI OCR.",
            "parsed_data": parsed_data,
            "raw_text": raw_text,
            "new_ocr_mode": "roi_beta"
        })
        
    except Exception as e:
        current_app.logger.error(f"Error during beta re-extraction: {e}")
        return jsonify({"success": False, "message": f"Processing Error: {e}"}), 500
