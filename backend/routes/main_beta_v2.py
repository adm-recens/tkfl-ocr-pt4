"""
Beta Main Routes (V2) - Page rendering for beta environment
"""
from flask import Blueprint, render_template, redirect, url_for, flash, current_app, request
from backend.services.voucher_service_beta import VoucherServiceBeta
import json

main_beta_v2_bp = Blueprint('main_beta_v2', __name__, url_prefix='/beta_v2')

@main_beta_v2_bp.route("/upload", methods=["GET"])
def upload_page_beta():
    """Beta upload page"""
    return render_template("upload_beta_v2.html")

@main_beta_v2_bp.route("/comparison", methods=["GET"])
def comparison_page():
    """OCR mode comparison page"""
    return render_template("comparison.html")

@main_beta_v2_bp.route("/review/<int:voucher_id>", methods=["GET"])
def review_voucher_beta(voucher_id):
    """Beta review page with confidence scores and preprocessing info"""
    try:
        voucher = VoucherServiceBeta.get_voucher_by_id(voucher_id)
        if not voucher:
            flash(f"Beta Voucher #{voucher_id} not found.", "error")
            return redirect(url_for('main_beta_v2.list_vouchers_beta'))
        
        # Image URL (beta_v2 folder)
        filename = voucher['file_name']
        # Create custom route for beta_v2 images
        image_url = f"/uploads/beta_v2/{filename}"
        
        # Get parsed data
        parsed_data = voucher.get('parsed_json', {})
        if isinstance(parsed_data, str):
            parsed_data = json.loads(parsed_data)
        elif parsed_data is None:
            parsed_data = {}
            
        # Get raw OCR text
        raw_text = voucher.get('raw_ocr_text', '')
        
        # Beta-specific metrics
        ocr_confidence = voucher.get('ocr_confidence', 0)
        preprocessing_method = voucher.get('preprocessing_method', 'unknown')
        processing_time_ms = voucher.get('processing_time_ms', 0)
        
        return render_template(
            'review_beta_v2.html',
            voucher=voucher,
            image_url=image_url,
            initial_parsed_data=parsed_data,
            raw_ocr_text=raw_text,
            ocr_confidence=ocr_confidence,
            preprocessing_method=preprocessing_method,
            processing_time_ms=processing_time_ms
        )
        
    except Exception as e:
        current_app.logger.error(f"Error loading beta voucher {voucher_id}: {e}")
        flash(f"Error: {e}", "error")
        return redirect(url_for('main_beta_v2.list_vouchers_beta'))

@main_beta_v2_bp.route("/vouchers", methods=["GET"])
def list_vouchers_beta():
    """List all beta vouchers"""
    try:
        page = request.args.get('page', 1, type=int)
        result = VoucherServiceBeta.get_all_vouchers(page=page)
        
        # Format vouchers for display
        vouchers_display = []
        for v in result['vouchers']:
            vouchers_display.append({
                'id': v['id'],
                'voucher_date': v.get('voucher_date'),
                'voucher_date_display': v.get('voucher_date').strftime('%d-%m-%Y') if v.get('voucher_date') else None,
                'voucher_number': v.get('voucher_number'),
                'supplier_name': v.get('supplier_name'),
                'grand_total_display': f"₹{v.get('net_total'):.2f}" if v.get('net_total') else None,
                'ocr_confidence': v.get('ocr_confidence'),
                'preprocessing_method': v.get('preprocessing_method')
            })
        
        return render_template(
            "view_receipts_beta_v2.html",
            vouchers=vouchers_display,
            page=result['current_page'],
            total_pages=result['total_pages'],
            total_vouchers=result['total_vouchers']
        )
    except Exception as e:
        current_app.logger.error(f"Error listing beta vouchers: {e}")
        flash(f"Error: {e}", "error")
        return render_template("view_receipts_beta_v2.html", vouchers=[], page=1, total_pages=1, total_vouchers=0)

@main_beta_v2_bp.route("/bulk_upload", methods=["GET"])
def bulk_upload_page():
    """Bulk upload page"""
    return render_template("bulk_upload_beta.html")

@main_beta_v2_bp.route("/bulk_review/<batch_id>", methods=["GET"])
def bulk_review_page(batch_id):
    """Bulk review/validation dashboard"""
    return render_template("bulk_review_beta.html", batch_id=batch_id)

@main_beta_v2_bp.route("/queue/upload", methods=["GET"])
def queue_upload_page():
    """Queue-based workflow upload page"""
    return render_template("queue_upload_beta.html")

@main_beta_v2_bp.route("/queue/<queue_id>/process", methods=["GET"])
def queue_processor_page(queue_id):
    """Queue processor wizard interface"""
    return render_template("queue_processor_beta.html", queue_id=queue_id)

@main_beta_v2_bp.route("/batch/<batch_id>", methods=["GET"])
def batch_summary_page(batch_id):
    """Batch Summary Page"""
    from backend.services.batch_service import BatchService
    
    batch = BatchService.get_batch_with_vouchers(batch_id)
    if not batch:
        flash(f"Batch {batch_id} not found", "error")
        return redirect(url_for('main_beta_v2.batch_list_page'))
    
    # Format dates for display (handles both date objects and strings)
    for voucher in batch.get('vouchers', []):
        voucher_date = voucher.get('voucher_date')
        if voucher_date:
            # If it's already a string, keep it; if it's a date object, format it
            if hasattr(voucher_date, 'strftime'):
                voucher['voucher_date_display'] = voucher_date.strftime('%Y-%m-%d')
            else:
                voucher['voucher_date_display'] = str(voucher_date)
        else:
            voucher['voucher_date_display'] = 'N/A'
        
    return render_template("batch_summary_beta.html", batch=batch)

@main_beta_v2_bp.route("/batches", methods=["GET"])
def batch_list_page():
    """Batch List Page"""
    from backend.services.batch_service import BatchService
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    result = BatchService.get_all_batches(limit=per_page, offset=offset)
    
    # Calculate pages
    total_pages = (result['total'] + per_page - 1) // per_page
    
    return render_template(
        "batch_list_beta.html", 
        batches=result['batches'],
        page=page,
        total_pages=total_pages,
        total_batches=result['total']
    )

