"""
Learning history API endpoints for displaying ML learning to users
"""

from flask import Blueprint, jsonify, render_template_string
from backend.services.learning_history_tracker import LearningHistoryTracker

learning_bp = Blueprint('learning', __name__, url_prefix='/api/learning')

@learning_bp.route('/page', methods=['GET'])
def learning_history_page():
    """Display detailed learning history page"""
    try:
        from flask import render_template
        history = LearningHistoryTracker.load_history()
        summary = LearningHistoryTracker.get_summary()
        
        # Calculate total patterns
        total_patterns = sum(len(p) for p in history.get('patterns_learned', {}).values())
        
        # Prepare patterns by field
        patterns_by_field = history.get('patterns_learned', {})
        
        return render_template('learning_history.html',
            summary=summary,
            total_patterns=total_patterns,
            patterns_by_field=patterns_by_field
        )
    except Exception as e:
        return f"Error loading learning history: {str(e)}", 500

@learning_bp.route('/history', methods=['GET'])
def get_learning_history():
    """Get full learning history"""
    try:
        history = LearningHistoryTracker.load_history()
        return jsonify({
            'status': 'success',
            'history': history
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@learning_bp.route('/summary', methods=['GET'])
def get_learning_summary():
    """Get summary of learning progress"""
    try:
        summary = LearningHistoryTracker.get_summary()
        return jsonify({
            'status': 'success',
            'summary': summary
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@learning_bp.route('/report', methods=['GET'])
def get_learning_report():
    """Get human-readable learning report"""
    try:
        report = LearningHistoryTracker.generate_report()
        return jsonify({
            'status': 'success',
            'report': report
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@learning_bp.route('/stats', methods=['GET'])
def get_learning_stats():
    """Get detailed learning statistics"""
    try:
        history = LearningHistoryTracker.load_history()
        
        stats = {
            'total_sessions': len(history.get('training_sessions', [])),
            'total_corrections': history.get('total_corrections_learned', 0),
            'fields_trained': list(history.get('patterns_learned', {}).keys()),
            'patterns_by_field': {}
        }
        
        # Count patterns per field
        for field, patterns in history.get('patterns_learned', {}).items():
            stats['patterns_by_field'][field] = len(patterns)
        
        return jsonify({
            'status': 'success',
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500
