"""
ML Learning History Tracker

Tracks all corrections used for training to:
1. Show users what the system has learned
2. Avoid retraining on same corrections
3. Provide transparency into ML model improvement
"""

import json
import os
from datetime import datetime
from pathlib import Path

class LearningHistoryTracker:
    """Track and manage ML learning history"""
    
    HISTORY_FILE = Path('backend/data/learning_history.json')
    
    @staticmethod
    def _ensure_history_file():
        """Create history file if it doesn't exist"""
        if not LearningHistoryTracker.HISTORY_FILE.exists():
            LearningHistoryTracker.HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            initial_data = {
                'version': '1.0',
                'created_at': datetime.now().isoformat(),
                'training_sessions': [],
                'total_corrections_learned': 0,
                'patterns_learned': {}
            }
            with open(LearningHistoryTracker.HISTORY_FILE, 'w') as f:
                json.dump(initial_data, f, indent=2)
    
    @staticmethod
    def load_history():
        """Load learning history"""
        LearningHistoryTracker._ensure_history_file()
        with open(LearningHistoryTracker.HISTORY_FILE, 'r') as f:
            return json.load(f)
    
    @staticmethod
    def get_already_trained_corrections():
        """Get set of correction IDs already used for training"""
        history = LearningHistoryTracker.load_history()
        trained_ids = set()
        for session in history.get('training_sessions', []):
            for correction in session.get('corrections_used', []):
                trained_ids.add(correction['id'])
        return trained_ids
    
    @staticmethod
    def record_training_session(corrections_used, training_results):
        """Record a completed training session"""
        history = LearningHistoryTracker.load_history()
        
        session = {
            'timestamp': datetime.now().isoformat(),
            'corrections_count': len(corrections_used),
            'corrections_used': corrections_used,
            'results': training_results,
            'new_patterns': training_results.get('new_patterns', []),
            'patterns_count': len(training_results.get('new_patterns', []))
        }
        
        history['training_sessions'].append(session)
        history['total_corrections_learned'] += len(corrections_used)
        
        # Update patterns learned
        for pattern in training_results.get('new_patterns', []):
            field = pattern.get('field', 'unknown')
            if field not in history['patterns_learned']:
                history['patterns_learned'][field] = []
            history['patterns_learned'][field].append(pattern)
        
        with open(LearningHistoryTracker.HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
        
        return history
    
    @staticmethod
    def get_summary():
        """Get summary of learning history"""
        history = LearningHistoryTracker.load_history()
        
        sessions = history.get('training_sessions', [])
        patterns_by_field = history.get('patterns_learned', {})
        
        # Count corrections per field
        fields_trained = {}
        for field, patterns in patterns_by_field.items():
            fields_trained[field] = len(patterns)
        
        summary = {
            'total_sessions': len(sessions),
            'total_corrections': history.get('total_corrections_learned', 0),
            'total_patterns': sum(len(p) for p in patterns_by_field.values()),
            'fields_trained': fields_trained,
            'last_training': sessions[-1]['timestamp'] if sessions else None,
            'recent_sessions': sessions[-5:] if sessions else []  # Last 5 sessions
        }
        
        return summary
    
    @staticmethod
    def generate_report():
        """Generate human-readable learning report"""
        history = LearningHistoryTracker.load_history()
        sessions = history.get('training_sessions', [])
        patterns = history.get('patterns_learned', {})
        
        report = []
        report.append("=" * 80)
        report.append("ML LEARNING HISTORY REPORT")
        report.append("=" * 80)
        
        report.append(f"\nTotal Training Sessions: {len(sessions)}")
        report.append(f"Total Corrections Used: {history.get('total_corrections_learned', 0)}")
        report.append(f"Total Patterns Learned: {sum(len(p) for p in patterns.values())}")
        
        report.append("\n--- PATTERNS LEARNED BY FIELD ---")
        for field, field_patterns in patterns.items():
            report.append(f"\n{field.upper()}: {len(field_patterns)} patterns")
            for pattern in field_patterns[-3:]:  # Show last 3
                report.append(f"  - {pattern.get('auto', 'empty')} → {pattern.get('corrected', '?')}")
            if len(field_patterns) > 3:
                report.append(f"  ... and {len(field_patterns) - 3} more")
        
        report.append("\n--- RECENT TRAINING SESSIONS ---")
        for i, session in enumerate(sessions[-5:], 1):
            timestamp = session.get('timestamp', '')
            corr_count = session.get('corrections_count', 0)
            patterns_count = session.get('patterns_count', 0)
            report.append(f"\n[{i}] {timestamp}")
            report.append(f"    Corrections: {corr_count} | Patterns learned: {patterns_count}")
        
        report.append("\n" + "=" * 80)
        
        return "\n".join(report)
