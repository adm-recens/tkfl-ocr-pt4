from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory
from backend.services.voucher_service import VoucherService
from backend.services.batch_service import BatchService
from backend.services.supplier_service import SupplierService
from backend.services.ml_feedback_service import MLFeedbackService
import json
import os

main_bp = Blueprint('main', __name__)

@main_bp.route("/")
def index():
    return render_template("index.html")

@main_bp.route("/upload", methods=["GET"])
def upload_page():
    # Redirect legacy single upload to new Queue/Bulk upload
    return redirect(url_for('main.queue_upload_page'))

@main_bp.route("/queue/upload", methods=["GET"])
def queue_upload_page():
    """Bulk upload page"""
    return render_template("queue_upload.html")

@main_bp.route("/queue/<queue_id>/process", methods=["GET"])
def queue_processor_page(queue_id):
    """Queue processor wizard interface"""
    return render_template("queue_processor.html", queue_id=queue_id)

@main_bp.route("/batches", methods=["GET"])
def batch_list_page():
    """Batch List Page"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    result = BatchService.get_all_batches(limit=per_page, offset=offset)
    
    # Calculate pages
    total_pages = (result['total'] + per_page - 1) // per_page
    
    return render_template(
        "batch_list.html", 
        batches=result['batches'],
        page=page,
        total_pages=total_pages,
        total_batches=result['total']
    )

@main_bp.route("/batch/<batch_id>", methods=["GET"])
def batch_summary_page(batch_id):
    """Batch Summary Page"""
    batch = BatchService.get_batch_with_vouchers(batch_id)
    if not batch:
        flash(f"Batch {batch_id} not found", "error")
        return redirect(url_for('main.batch_list_page'))
    
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
        
    return render_template("batch_summary.html", batch=batch)

# Duplicate `review_voucher` removed: consolidated implementation exists later in this file

@main_bp.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)

@main_bp.route("/receipts", methods=["GET"])
def view_receipts():
    try:
        # Get all vouchers without pagination (will be handled by DataTables)
        result = VoucherService.get_all_vouchers(page=1, page_size=10000)
        
        # Format data for display
        for voucher in result['vouchers']:
            voucher['created_at_display'] = voucher['created_at'].strftime('%Y-%m-%d %H:%M:%S') if voucher['created_at'] else 'N/A'
            voucher['grand_total_display'] = f"₹{voucher['net_total']:.2f}" if voucher['net_total'] is not None else 'N/A'
            voucher['voucher_date_display'] = voucher['voucher_date'] if voucher['voucher_date'] else 'N/A'

        return render_template(
            "view_receipts.html",
            vouchers=result['vouchers'],
            page=result['current_page'],
            total_pages=result['total_pages'],
            total_vouchers=result['total_vouchers']
        )
    except Exception as e:
        current_app.logger.error(f"Error fetching receipts: {e}")
        flash(f"Error loading receipts: {e}", "error")
        return render_template("view_receipts.html", vouchers=[], page=1, total_pages=1, total_vouchers=0)

@main_bp.route("/review/<int:voucher_id>", methods=["GET"])
def review_voucher(voucher_id):
    try:
        voucher = VoucherService.get_voucher_by_id(voucher_id)
        if not voucher:
            flash(f"Voucher #{voucher_id} not found.", "error")
            return redirect(url_for('main.view_receipts'))
            
        # Use file_storage_path to get actual filename on disk (which has unique prefix)
        if voucher.get('file_storage_path'):
            real_filename = os.path.basename(voucher['file_storage_path'])
            image_url = url_for('main.uploaded_file', filename=real_filename)
        else:
            filename = voucher['file_name']
            image_url = url_for('main.uploaded_file', filename=filename)
        
        # Get parsed data
        parsed_data = voucher.get('parsed_json', {})
        if isinstance(parsed_data, str):
            parsed_data = json.loads(parsed_data)
        elif parsed_data is None:
            parsed_data = {}
            
        # Fallback: Reconstruct from DB columns if parsed_json is missing
        if not parsed_data or (not parsed_data.get('master') and not parsed_data.get('items')):
            db_items = VoucherService.get_voucher_items(voucher_id)
            db_deductions = VoucherService.get_voucher_deductions(voucher_id)
            
            parsed_data = {
                "master": {
                    "voucher_number": voucher.get('voucher_number'),
                    "voucher_date": str(voucher.get('voucher_date')) if voucher.get('voucher_date') else None,
                    "supplier_name": voucher.get('supplier_name'),
                    "vendor_details": voucher.get('vendor_details'),
                    "gross_total": float(voucher['gross_total']) if voucher.get('gross_total') is not None else None,
                    "total_deductions": float(voucher['total_deductions']) if voucher.get('total_deductions') is not None else None,
                    "net_total": float(voucher['net_total']) if voucher.get('net_total') is not None else None,
                },
                "items": [dict(i) for i in db_items],
                "deductions": [dict(d) for d in db_deductions]
            }

        # Get raw OCR text
        raw_text = voucher.get('raw_ocr_text', '')
        
        # Get current OCR mode
        selected_mode = voucher.get('ocr_mode', 'default')
        
        # Return the review template with all required data
        return render_template(
            'review.html', 
            voucher=voucher, 
            image_url=image_url,
            initial_parsed_data=parsed_data,
            raw_ocr_text=raw_text,
            selected_mode=selected_mode
        )
        
    except Exception as e:
        current_app.logger.error(f"Error loading voucher {voucher_id}: {e}")
        flash(f"Error loading voucher: {e}", "error")
        return redirect(url_for('main.view_receipts'))

@main_bp.route("/validate/<int:voucher_id>", methods=["GET"])
def validate_voucher_page(voucher_id):
    try:
        voucher = VoucherService.get_voucher_by_id(voucher_id)
        if not voucher:
            flash(f"Voucher #{voucher_id} not found.", "error")
            return redirect(url_for('main.view_receipts'))
            
        db_items = VoucherService.get_voucher_items(voucher_id)
        db_deductions = VoucherService.get_voucher_deductions(voucher_id)
        
        parsed_json_data = voucher.get('parsed_json')
        if isinstance(parsed_json_data, str):
            parsed_json_data = json.loads(parsed_json_data)
        elif parsed_json_data is None:
            parsed_json_data = {}
            
        # Fallback: Reconstruct master data if missing
        if not parsed_json_data.get('master'):
            parsed_json_data['master'] = {
                "voucher_number": voucher.get('voucher_number'),
                "voucher_date": str(voucher.get('voucher_date')) if voucher.get('voucher_date') else None,
                "supplier_name": voucher.get('supplier_name'),
                "vendor_details": voucher.get('vendor_details'),
                "gross_total": float(voucher['gross_total']) if voucher.get('gross_total') is not None else None,
                "total_deductions": float(voucher['total_deductions']) if voucher.get('total_deductions') is not None else None,
                "net_total": float(voucher['net_total']) if voucher.get('net_total') is not None else None,
            }
            
        # Prefer parsed_json items (have complete OCR data), fallback to DB items (user corrections)
        if parsed_json_data.get('items') and len(parsed_json_data.get('items', [])) > 0:
            items_data = parsed_json_data.get('items', [])
            # Ensure all numeric fields are properly converted for JSON serialization
            for item in items_data:
                if 'unit_price' in item and item['unit_price'] is not None:
                    item['unit_price'] = float(item['unit_price'])
                if 'quantity' in item and item['quantity'] is not None:
                    item['quantity'] = float(item['quantity'])
                if 'line_amount' in item and item['line_amount'] is not None:
                    item['line_amount'] = float(item['line_amount'])
            current_app.logger.info(f"[VALIDATE] Using {len(items_data)} parsed_json items")
        elif db_items and len(db_items) > 0:
            items_data = [dict(item) for item in db_items]
            # Ensure all numeric fields are properly converted
            for item in items_data:
                if 'unit_price' in item and item['unit_price'] is not None:
                    item['unit_price'] = float(item['unit_price'])
                if 'quantity' in item and item['quantity'] is not None:
                    item['quantity'] = float(item['quantity'])
                if 'line_amount' in item and item['line_amount'] is not None:
                    item['line_amount'] = float(item['line_amount'])
            current_app.logger.info(f"[VALIDATE] Using {len(items_data)} DB items")
        else:
            items_data = []
            current_app.logger.warning(f"[VALIDATE] No items found for voucher {voucher_id}")
            
        if parsed_json_data.get('deductions') and len(parsed_json_data.get('deductions', [])) > 0:
            deductions_data = parsed_json_data.get('deductions', [])
            # Ensure amount is properly converted
            for ded in deductions_data:
                if 'amount' in ded and ded['amount'] is not None:
                    ded['amount'] = float(ded['amount'])
        elif db_deductions and len(db_deductions) > 0:
            deductions_data = [dict(ded) for ded in db_deductions]
            # Ensure amount is properly converted
            for ded in deductions_data:
                if 'amount' in ded and ded['amount'] is not None:
                    ded['amount'] = float(ded['amount'])
        else:
            deductions_data = []

        # Determine image URL based on OCR mode
        if voucher.get('ocr_mode') == 'roi_beta':
            image_url = url_for('main.uploaded_file_beta', filename=voucher['file_name'])
        else:
            # Fix for production bulk upload images (use actual filename from storage path)
            if voucher.get('file_storage_path'):
                real_filename = os.path.basename(voucher['file_storage_path'])
                image_url = url_for('main.uploaded_file', filename=real_filename)
            else:
                image_url = url_for('main.uploaded_file', filename=voucher['file_name'])

        return render_template(
            "validate.html",
            voucher=voucher,
            image_url=image_url,
            save_url=url_for('api.save_validated_data', voucher_id=voucher_id),
            parsed_data=parsed_json_data,
            items_data_json=json.dumps(items_data, ensure_ascii=False, default=str),
            deductions_data_json=json.dumps(deductions_data, ensure_ascii=False, default=str),
            raw_text=voucher.get('raw_ocr_text', '')  # Pass raw text
        )
    except Exception as e:
        current_app.logger.error(f"Error loading validation page for {voucher_id}: {e}")
        flash(f"Error loading validation page: {e}", "error")
        return redirect(url_for('main.view_receipts'))

@main_bp.route("/view_raw_json/<int:voucher_id>")
def view_voucher_json(voucher_id):
    try:
        voucher = VoucherService.get_voucher_by_id(voucher_id)
        if voucher and voucher.get('parsed_json'):
            json_data = voucher['parsed_json']
            if isinstance(json_data, str):
                json_data = json.loads(json_data)
            return render_template("view_json.html", voucher_id=voucher_id, json_data=json.dumps(json_data, indent=4))
    except Exception as e:
        current_app.logger.error(f"Error viewing JSON for {voucher_id}: {e}")
        
    flash(f"Voucher #{voucher_id} JSON not found.", "error")
    return redirect(url_for('main.view_receipts'))

@main_bp.route("/training", methods=["GET"])
def training_page():
    # Fetch real stats from the feedback service
    stats = MLFeedbackService.get_dataset_stats()
    
    # Get ML training status
    from backend.services.ml_training_service import MLTrainingService
    ml_status = MLTrainingService.get_training_status()
    
    return render_template("training.html", stats=stats, ml_status=ml_status)

@main_bp.route("/confirm_delete", methods=["GET"])
def confirm_delete_all():
    return render_template("confirm_delete_all.html")

@main_bp.route("/review_beta/<int:voucher_id>")
def review_voucher_beta(voucher_id):
    """
    Beta Review Page: Displays extracted data for verification/editing.
    Uses 'review_beta.html' template.
    """
    voucher = VoucherService.get_voucher_by_id(voucher_id)
    if not voucher:
        return "Voucher not found", 404
    
    # Ensure we are reviewing a beta voucher
    if voucher.get('ocr_mode') != 'roi_beta':
        return redirect(url_for('main.review_voucher', voucher_id=voucher_id))

    # Handle parsed_json (stored as string or dict)
    parsed_data = voucher.get('parsed_json', {})
    if isinstance(parsed_data, str):
        parsed_data = json.loads(parsed_data)
    elif parsed_data is None:
        parsed_data = {}
    
    # Prepare data for template
    context = {
        "voucher": voucher,
        "parsed_data": parsed_data,
        "items": parsed_data.get('items', []),
        "deductions": parsed_data.get('deductions', []),
        "master": parsed_data.get('master', {}),
        "raw_text": voucher.get('raw_ocr_text', '')
    }
    
    return render_template("review_beta.html", **context)

@main_bp.route("/suppliers", methods=["GET"])
def suppliers_list():
    """List all suppliers with stats"""
    suppliers = SupplierService.get_all_suppliers()
    return render_template("suppliers.html", suppliers=suppliers)

@main_bp.route("/suppliers/<int:supplier_id>", methods=["GET"])
def supplier_detail(supplier_id):
    """View single supplier details and receipts"""
    supplier = SupplierService.get_supplier_by_id(supplier_id)
    if not supplier:
        flash("Supplier not found", "error")
        return redirect(url_for('main.suppliers_list'))
        
    receipts = SupplierService.get_supplier_receipts(supplier_id)
    return render_template("supplier_detail.html", supplier=supplier, receipts=receipts)
