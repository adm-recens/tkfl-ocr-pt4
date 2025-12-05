"""
API endpoint for running OCR comparison tests
"""
from flask import Blueprint, jsonify, current_app
from backend.ocr_service_beta import extract_text_beta
from backend.db import get_connection
import os

comparison_bp = Blueprint('comparison', __name__, url_prefix='/api/comparison')

@comparison_bp.route("/run_all", methods=["POST"])
def run_comparison_all():
    """Run both Enhanced and Experimental modes on all beta vouchers"""
    try:
        from backend.services.voucher_service_beta import VoucherServiceBeta
        
        # Get all beta vouchers using the service (returns pagination dict)
        voucher_data = VoucherServiceBeta.get_all_vouchers(page=1, per_page=1000)  # Get up to 1000
        vouchers = voucher_data['vouchers']
        
        results = []
        current_app.logger.info(f"Found {len(vouchers)} vouchers to compare")
        
        for voucher in vouchers:
            voucher_id = voucher['id']
            file_name = voucher['file_name']
            file_path = voucher['file_storage_path']
            
            current_app.logger.info(f"Testing voucher {voucher_id}: {file_name} at {file_path}")
            
            if not os.path.exists(file_path):
                current_app.logger.warning(f"File not found: {file_path}")
                results.append({
                    'id': voucher_id,
                    'file_name': file_name,
                    'enhanced': {'success': False, 'error': 'File not found'},
                    'experimental': {'success': False, 'error': 'File not found'},
                    'winner': None,
                    'diff': 0
                })
                continue
            
            # Test Enhanced mode
            try:
                current_app.logger.info(f"Testing Enhanced mode for {file_name}")
                enhanced_result = extract_text_beta(file_path, method='enhanced')
                enhanced = {
                    'success': True,
                    'confidence': enhanced_result.get('confidence', 0),
                    'processing_time': enhanced_result.get('processing_time_ms', 0),
                    'text_length': len(enhanced_result.get('text', ''))
                }
                current_app.logger.info(f"Enhanced: {enhanced['confidence']}%")
            except Exception as e:
                current_app.logger.error(f"Enhanced mode error for {file_name}: {e}")
                enhanced = {'success': False, 'error': str(e), 'confidence': 0}
            
            # Test Experimental mode
            try:
                current_app.logger.info(f"Testing Experimental mode for {file_name}")
                experimental_result = extract_text_beta(file_path, method='experimental')
                experimental = {
                    'success': True,
                    'confidence': experimental_result.get('confidence', 0),
                    'processing_time': experimental_result.get('processing_time_ms', 0),
                    'text_length': len(experimental_result.get('text', ''))
                }
                current_app.logger.info(f"Experimental: {experimental['confidence']}%")
            except Exception as e:
                current_app.logger.error(f"Experimental mode error for {file_name}: {e}")
                experimental = {'success': False, 'error': str(e), 'confidence': 0}
            
            # Determine winner
            winner = None
            diff = 0
            if enhanced['success'] and experimental['success']:
                diff = experimental['confidence'] - enhanced['confidence']
                if diff > 0:
                    winner = 'experimental'
                elif diff < 0:
                    winner = 'enhanced'
                else:
                    winner = 'tie'
            
            results.append({
                'id': voucher_id,
                'file_name': file_name,
                'enhanced': enhanced,
                'experimental': experimental,
                'winner': winner,
                'diff': abs(diff)
            })
        
        # Calculate summary
        enhanced_wins = sum(1 for r in results if r.get('winner') == 'enhanced')
        experimental_wins = sum(1 for r in results if r.get('winner') == 'experimental')
        ties = sum(1 for r in results if r.get('winner') == 'tie')
        
        successful_tests = [r for r in results if r['enhanced']['success'] and r['experimental']['success']]
        
        avg_enhanced = sum(r['enhanced']['confidence'] for r in successful_tests) / len(successful_tests) if successful_tests else 0
        avg_experimental = sum(r['experimental']['confidence'] for r in successful_tests) / len(successful_tests) if successful_tests else 0
        
        return jsonify({
            'success': True,
            'results': results,
            'summary': {
                'total': len(results),
                'tested': len(successful_tests),
                'enhanced_wins': enhanced_wins,
                'experimental_wins': experimental_wins,
                'ties': ties,
                'avg_enhanced': round(avg_enhanced, 1),
                'avg_experimental': round(avg_experimental, 1),
                'avg_diff': round(avg_experimental - avg_enhanced, 1)
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Comparison error: {e}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return jsonify({'success': False, 'message': str(e)}), 500
