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
    """Run comparison on all beta receipts"""
    try:
        from backend.db import get_connection
        from backend.ocr_service_beta import extract_text_beta
        
        conn = get_connection()
        cur = conn.cursor()
        
        # Get all beta receipts
        current_app.logger.info("Querying vouchers_master_beta for files...")
        cur.execute("SELECT id, file_name, file_storage_path FROM vouchers_master_beta WHERE file_storage_path IS NOT NULL ORDER BY id DESC")
        receipts = cur.fetchall()
        
        current_app.logger.info(f"Found {len(receipts)} receipts in DB.")
        
        results = []
        
        summary = {
            'optimal_wins': 0,
            'adaptive_wins': 0,
            'aggressive_wins': 0,
            'enhanced_wins': 0, 
            'simple_wins': 0,
            'ties': 0,
            'avg_optimal': 0,
            'avg_adaptive': 0,
            'avg_aggressive': 0,
            'avg_enhanced': 0,
            'avg_simple': 0
        }
        
        totals = {
            'optimal': 0, 'adaptive': 0, 'aggressive': 0, 'enhanced': 0, 'simple': 0
        }
        valid_count = 0
        
        for row in receipts:
            r_id = row['id']
            r_name = row['file_name']
            r_path = row['file_storage_path']
            
            current_app.logger.info(f"Checking ID {r_id}: {r_path}")
            if not os.path.exists(r_path):
                current_app.logger.warning(f"File not found: {r_path} - Skipping")
                continue
                
            # Test all 5 modes
            modes = ['optimal', 'adaptive', 'aggressive', 'enhanced', 'simple']
            mode_results = {}
            
            for mode in modes:
                try:
                    ocr_res = extract_text_beta(r_path, method=mode)
                    mode_results[mode] = {
                        'confidence': ocr_res['confidence'],
                        'processing_time': ocr_res['processing_time_ms'],
                        'success': True
                    }
                except Exception as e:
                    mode_results[mode] = {'confidence': 0, 'success': False, 'error': str(e)}
            
            # Determine winner
            successful_modes = {k: v for k, v in mode_results.items() if v['success']}
            
            winner_mode = 'none'
            winner_score = 0
            
            if successful_modes:
                valid_count += 1
                winner = max(successful_modes.items(), key=lambda x: x[1]['confidence'])
                winner_mode = winner[0]
                winner_score = winner[1]['confidence']
                
                # Check for ties (within 0.1%)
                ties = [m for m, res in successful_modes.items() if abs(res['confidence'] - winner_score) < 0.1]
                if len(ties) > 1:
                    winner_mode = 'tie'
                    summary['ties'] += 1
                else:
                    summary[f'{winner_mode}_wins'] += 1
                
                for mode in modes:
                    if mode_results[mode]['success']:
                        totals[mode] += mode_results[mode]['confidence']
            
            # Create result entry regardless of success
            result_entry = {
                'id': r_id,
                'file_name': r_name,
                'optimal': mode_results.get('optimal', {'confidence': 0, 'success': False}),
                'adaptive': mode_results.get('adaptive', {'confidence': 0, 'success': False}),
                'aggressive': mode_results.get('aggressive', {'confidence': 0, 'success': False}),
                'enhanced': mode_results.get('enhanced', {'confidence': 0, 'success': False}),
                'simple': mode_results.get('simple', {'confidence': 0, 'success': False}),
                'winner': winner_mode
            }
            
            results.append(result_entry)
        
        # Calculate averages
        if valid_count > 0:
            summary['avg_optimal'] = round(totals['optimal'] / valid_count, 1)
            summary['avg_adaptive'] = round(totals['adaptive'] / valid_count, 1)
            summary['avg_aggressive'] = round(totals['aggressive'] / valid_count, 1)
            summary['avg_enhanced'] = round(totals['enhanced'] / valid_count, 1)
            summary['avg_simple'] = round(totals['simple'] / valid_count, 1)
            
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'results': results, 'summary': summary})
        
    except Exception as e:
        current_app.logger.error(f"Comparison error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)})
