#!/usr/bin/env python
"""
Display ML Learning Report - Shows what the system has learned
"""

from backend import create_app
from backend.services.learning_history_tracker import LearningHistoryTracker

app = create_app()
with app.app_context():
    report = LearningHistoryTracker.generate_report()
    print(report)
