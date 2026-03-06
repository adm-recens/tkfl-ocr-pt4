from flask import Blueprint, jsonify, request, current_app
import time
import threading
from backend.services.ml_training_service import MLTrainingService
from backend.services.smart_crop_training_service import SmartCropTrainingService

api_training_bp = Blueprint('api_training', __name__)

# Global job tracking (shared between text ML and smart crop jobs)
_training_jobs = {}


# ─────────────────── TEXT PARSING MODELS ───────────────────

@api_training_bp.route('/start', methods=['POST'])
def start_training():
    """
    Trigger a Text Parsing model training run (OCR + Parsing models only).
    Smart Crop is trained independently via /smart-crop/start.
    """
    try:
        feedback_limit = request.json.get('feedback_limit', 5000) if request.is_json else 5000
        job_id = 'job_text_' + str(int(time.time()))

        _training_jobs[job_id] = {
            'type': 'text_parsing',
            'status': 'queued',
            'progress': 0,
            'message': 'Starting text parsing model training...',
            'started_at': time.time()
        }

        app = current_app._get_current_object()

        def train_in_background():
            with app.app_context():
                try:
                    _training_jobs[job_id]['status'] = 'training'
                    _training_jobs[job_id]['progress'] = 10
                    _training_jobs[job_id]['message'] = 'Collecting training data...'

                    result = MLTrainingService.train_models(
                        feedback_limit=feedback_limit,
                        save_models=True
                    )

                    _training_jobs[job_id]['status'] = 'completed'
                    _training_jobs[job_id]['progress'] = 100
                    _training_jobs[job_id]['message'] = 'Text parsing models trained successfully'
                    _training_jobs[job_id]['result'] = result
                    _training_jobs[job_id]['completed_at'] = time.time()

                    current_app.logger.info(f"[ML Training] Job {job_id} completed")

                except Exception as e:
                    _training_jobs[job_id]['status'] = 'failed'
                    _training_jobs[job_id]['error'] = str(e)
                    _training_jobs[job_id]['completed_at'] = time.time()
                    current_app.logger.error(f"[ML Training] Job {job_id} failed: {e}")

        thread = threading.Thread(target=train_in_background, daemon=True)
        thread.start()

        return jsonify({
            'success': True,
            'message': 'Text parsing model training job started',
            'job_id': job_id,
            'feedback_limit': feedback_limit,
            'eta_seconds': 120
        })

    except Exception as e:
        current_app.logger.error(f"[ML Training] Error starting training: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────── SMART CROP MODEL ───────────────────

@api_training_bp.route('/smart-crop/start', methods=['POST'])
def start_smart_crop_training():
    """
    Trigger a Smart Crop model training run (independent of text parsing models).
    """
    try:
        job_id = 'job_crop_' + str(int(time.time()))

        _training_jobs[job_id] = {
            'type': 'smart_crop',
            'status': 'queued',
            'progress': 0,
            'message': 'Starting Smart Crop model training...',
            'started_at': time.time()
        }

        app = current_app._get_current_object()

        def train_crop_in_background():
            with app.app_context():
                try:
                    _training_jobs[job_id]['status'] = 'training'
                    _training_jobs[job_id]['progress'] = 20
                    _training_jobs[job_id]['message'] = 'Collecting crop annotation data...'

                    result = SmartCropTrainingService.train_smart_crop_model()

                    _training_jobs[job_id]['status'] = 'completed' if result.get('status') == 'success' else 'failed'
                    _training_jobs[job_id]['progress'] = 100
                    _training_jobs[job_id]['message'] = result.get('message', 'Done')
                    _training_jobs[job_id]['result'] = result
                    _training_jobs[job_id]['completed_at'] = time.time()

                    current_app.logger.info(f"[Smart Crop Training] Job {job_id} completed: {result.get('status')}")

                except Exception as e:
                    _training_jobs[job_id]['status'] = 'failed'
                    _training_jobs[job_id]['error'] = str(e)
                    _training_jobs[job_id]['completed_at'] = time.time()
                    current_app.logger.error(f"[Smart Crop Training] Job {job_id} failed: {e}")

        thread = threading.Thread(target=train_crop_in_background, daemon=True)
        thread.start()

        return jsonify({
            'success': True,
            'message': 'Smart Crop model training job started',
            'job_id': job_id,
            'eta_seconds': 30
        })

    except Exception as e:
        current_app.logger.error(f"[Smart Crop Training] Error starting training: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_training_bp.route('/smart-crop/status', methods=['GET'])
def get_smart_crop_status():
    """
    Get current Smart Crop model status, stats, and training history.
    """
    try:
        status = SmartCropTrainingService.get_training_status()
        return jsonify({'success': True, 'smart_crop_status': status})
    except Exception as e:
        current_app.logger.error(f"[Smart Crop Training] Error getting status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ─────────────────── SHARED STATUS ───────────────────

@api_training_bp.route('/status/<job_id>', methods=['GET'])
def check_status(job_id):
    """Check any training job status by ID (works for both text and smart crop jobs)."""
    if job_id not in _training_jobs:
        return jsonify({'success': False, 'error': f'Job {job_id} not found'}), 404

    job = _training_jobs[job_id]
    response = {
        'success': True,
        'job_id': job_id,
        'type': job.get('type', 'unknown'),
        'status': job.get('status'),
        'progress': job.get('progress'),
        'message': job.get('message'),
        'started_at': job.get('started_at')
    }

    if job.get('status') == 'completed':
        response['result'] = job.get('result')
        response['completed_at'] = job.get('completed_at')
        response['training_time'] = job.get('completed_at', 0) - job.get('started_at', 0)
    elif job.get('status') == 'failed':
        response['error'] = job.get('error')
        response['completed_at'] = job.get('completed_at')

    return jsonify(response)


@api_training_bp.route('/status', methods=['GET'])
def get_training_status():
    """Get current text parsing model status (OCR + Parsing)."""
    try:
        status = MLTrainingService.get_training_status()
        return jsonify({'success': True, 'training_status': status})
    except Exception as e:
        current_app.logger.error(f"[ML Training] Error getting status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_training_bp.route('/models', methods=['GET'])
def get_model_info():
    """Get information about all trained models (text parsing + smart crop)."""
    try:
        text_status = MLTrainingService.get_training_status()
        crop_status = SmartCropTrainingService.get_training_status()

        return jsonify({
            'success': True,
            'models': {
                'ocr_model': {
                    'available': text_status['ocr_model_available'],
                    'stats': text_status['ocr_stats']
                },
                'parsing_model': {
                    'available': text_status['parsing_model_available'],
                    'fields': text_status['parsing_fields']
                },
                'smart_crop_model': {
                    'available': crop_status.get('model_available', False),
                    'trained_at': crop_status.get('trained_at'),
                    'training_samples': crop_status.get('training_samples', 0),
                    'avg_crop_size': crop_status.get('avg_crop_size', {})
                }
            },
            'last_trained': text_status['last_trained']
        })

    except Exception as e:
        current_app.logger.error(f"[ML Training] Error getting model info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
