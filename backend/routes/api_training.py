from flask import Blueprint, jsonify, request, current_app
import time
import threading
from backend.services.ml_training_service import MLTrainingService

api_training_bp = Blueprint('api_training', __name__)

# Global job tracking
_training_jobs = {}

@api_training_bp.route('/start', methods=['POST'])
def start_training():
    """
    Trigger a model training run from user feedback
    """
    try:
        # Get optional parameters
        feedback_limit = request.json.get('feedback_limit', 5000) if request.is_json else 5000
        
        # Generate job ID
        job_id = 'job_' + str(int(time.time()))
        
        # Track job status
        _training_jobs[job_id] = {
            'status': 'queued',
            'progress': 0,
            'message': 'Starting training...',
            'started_at': time.time()
        }
        
        # Run training in background thread
        app = current_app._get_current_object()  # Capture app reference for thread
        
        def train_in_background():
            with app.app_context():  # Restore application context in thread
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
                    _training_jobs[job_id]['message'] = 'Training completed successfully'
                    _training_jobs[job_id]['result'] = result
                    _training_jobs[job_id]['completed_at'] = time.time()
                    
                    current_app.logger.info(f"[ML Training] Job {job_id} completed: {result}")
                    
                except Exception as e:
                    _training_jobs[job_id]['status'] = 'failed'
                    _training_jobs[job_id]['error'] = str(e)
                    _training_jobs[job_id]['completed_at'] = time.time()
                    
                    current_app.logger.error(f"[ML Training] Job {job_id} failed: {e}")
        
        # Start training in background
        thread = threading.Thread(target=train_in_background, daemon=True)
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Training job started',
            'job_id': job_id,
            'feedback_limit': feedback_limit,
            'eta_seconds': 600  # Rough estimate
        })
        
    except Exception as e:
        current_app.logger.error(f"[ML Training] Error starting training: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_training_bp.route('/status/<job_id>', methods=['GET'])
def check_status(job_id):
    """
    Check training status and progress
    """
    if job_id not in _training_jobs:
        return jsonify({
            'success': False,
            'error': f'Job {job_id} not found'
        }), 404
    
    job = _training_jobs[job_id]
    
    response = {
        'success': True,
        'job_id': job_id,
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
    """
    Get current training status (models available, last trained, etc.)
    """
    try:
        status = MLTrainingService.get_training_status()
        return jsonify({
            'success': True,
            'training_status': status
        })
    except Exception as e:
        current_app.logger.error(f"[ML Training] Error getting status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_training_bp.route('/models', methods=['GET'])
def get_model_info():
    """
    Get information about trained models
    """
    try:
        status = MLTrainingService.get_training_status()
        
        response = {
            'success': True,
            'models': {
                'ocr_model': {
                    'available': status['ocr_model_available'],
                    'stats': status['ocr_stats']
                },
                'parsing_model': {
                    'available': status['parsing_model_available'],
                    'fields': status['parsing_fields']
                }
            },
            'last_trained': status['last_trained']
        }
        
        return jsonify(response)
        
    except Exception as e:
        current_app.logger.error(f"[ML Training] Error getting model info: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
