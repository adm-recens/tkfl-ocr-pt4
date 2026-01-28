"""
ML Correction Models for OCR and Parsing Corrections

This module contains:
- OCRCorrectionModel: Learns and applies OCR character/word corrections
- ParsingCorrectionModel: Learns and applies field extraction corrections
"""

import json
import os
from datetime import datetime
from collections import defaultdict
import statistics


class OCRCorrectionModel:
    """
    Model to learn from OCR corrections and suggest corrections for future text
    
    Learns patterns like: "Tl" -> "1", "S" -> "5", "O" -> "0" etc.
    """
    
    MODEL_VERSION = "1.0"
    
    def __init__(self):
        """Initialize OCR correction model"""
        self.model_version = self.MODEL_VERSION
        self.ocr_patterns = {}  # {original_pattern: [corrections]}
        self.pattern_stats = {}  # {original: {corrected: count, confidence}}
        self.last_trained = None
        self.total_samples = 0
        self._model_dir = os.path.normpath(os.path.abspath(os.path.join(os.path.dirname(__file__))))
        
    def learn_from_correction(self, raw_ocr: str, auto_extracted: str, user_corrected: str, field_name: str = None):
        """
        Learn a correction pattern from user feedback
        
        Args:
            raw_ocr: Original OCR text
            auto_extracted: Auto-extracted value
            user_corrected: Corrected value by user
            field_name: Optional field context
        """
        if not auto_extracted or not user_corrected or auto_extracted == user_corrected:
            return
        
        # Store pattern
        if auto_extracted not in self.ocr_patterns:
            self.ocr_patterns[auto_extracted] = []
            self.pattern_stats[auto_extracted] = defaultdict(int)
        
        self.ocr_patterns[auto_extracted].append(user_corrected)
        self.pattern_stats[auto_extracted][user_corrected] += 1
        self.total_samples += 1
        self.last_trained = datetime.now()
    
    def get_correction_suggestion(self, text: str, confidence_threshold: float = 0.7) -> dict:
        """
        Get suggested correction for text based on learned patterns
        
        Args:
            text: Text to correct
            confidence_threshold: Minimum confidence (0-1) for suggestion
            
        Returns:
            {
                'suggestion': corrected_text or None,
                'confidence': float (0-1),
                'pattern_matches': int
            }
        """
        if text not in self.pattern_stats:
            return {
                'suggestion': None,
                'confidence': 0,
                'pattern_matches': 0
            }
        
        corrections = self.pattern_stats[text]
        if not corrections:
            return {
                'suggestion': None,
                'confidence': 0,
                'pattern_matches': 0
            }
        
        # Get most common correction
        total = sum(corrections.values())
        best_correction = max(corrections.items(), key=lambda x: x[1])
        confidence = best_correction[1] / total
        
        if confidence < confidence_threshold:
            return {
                'suggestion': None,
                'confidence': confidence,
                'pattern_matches': len(corrections)
            }
        
        return {
            'suggestion': best_correction[0],
            'confidence': confidence,
            'pattern_matches': len(corrections)
        }
    
    def get_stats(self) -> dict:
        """Get model statistics"""
        return {
            'version': self.model_version,
            'trained_at': self.last_trained.isoformat() if self.last_trained and not isinstance(self.last_trained, str) else self.last_trained,
            'total_samples': self.total_samples,
            'total_ocr_patterns': len(self.ocr_patterns),
            'patterns': self.ocr_patterns
        }
    
    def save_model(self, filename: str = 'ocr_corrections_model.json'):
        """Save model to JSON file"""
        try:
            filepath = os.path.join(self._model_dir, filename)
            model_data = {
                'version': self.model_version,
                'trained_at': self.last_trained.isoformat() if self.last_trained else None,
                'total_samples': self.total_samples,
                'ocr_patterns': self.ocr_patterns,
                'pattern_stats': {k: dict(v) for k, v in self.pattern_stats.items()}
            }
            
            with open(filepath, 'w') as f:
                json.dump(model_data, f, indent=2)
            
            return True
        except Exception as e:
            print(f"[OCRCorrectionModel] Error saving model: {e}")
            return False
    
    def load_model(self, filename: str = 'ocr_corrections_model.json') -> bool:
        """Load model from JSON file"""
        try:
            filepath = os.path.join(self._model_dir, filename)
            
            if not os.path.exists(filepath):
                return False
            
            with open(filepath, 'r') as f:
                model_data = json.load(f)
            
            self.model_version = model_data.get('version', self.MODEL_VERSION)
            trained_at_str = model_data.get('trained_at')
            self.last_trained = trained_at_str  # Store as string
            self.total_samples = model_data.get('total_samples', 0)
            self.ocr_patterns = model_data.get('ocr_patterns', {})
            
            # Restore pattern_stats
            self.pattern_stats = {}
            for pattern, stats_dict in model_data.get('pattern_stats', {}).items():
                self.pattern_stats[pattern] = defaultdict(int, stats_dict)
            
            return True
        except Exception as e:
            print(f"[OCRCorrectionModel] Error loading model: {e}")
            return False


class ParsingCorrectionModel:
    """
    Model to learn from parsing corrections and suggest field extractions
    
    Learns context-aware field extraction rules
    """
    
    MODEL_VERSION = "1.0"
    
    def __init__(self):
        """Initialize parsing correction model"""
        self.model_version = self.MODEL_VERSION
        self.parsing_corrections = {}  # {field: {auto_value: [user_values]}}
        self.field_stats = {}  # {field: {auto: {corrected: count}}}
        self.last_trained = None
        self.total_samples = 0
        self._model_dir = os.path.normpath(os.path.abspath(os.path.join(os.path.dirname(__file__))))
    
    def learn_from_correction(self, field_name: str, raw_ocr: str, auto_extracted: str, user_corrected: str):
        """
        Learn a correction pattern for a field
        
        Args:
            field_name: Name of the field (e.g., 'supplier_name', 'amount')
            raw_ocr: Original OCR text
            auto_extracted: Auto-extracted value
            user_corrected: Corrected value by user
        """
        if not field_name or not auto_extracted or not user_corrected or auto_extracted == user_corrected:
            return
        
        # Initialize field if needed
        if field_name not in self.parsing_corrections:
            self.parsing_corrections[field_name] = {}
            self.field_stats[field_name] = defaultdict(lambda: defaultdict(int))
        
        # Store pattern
        if auto_extracted not in self.parsing_corrections[field_name]:
            self.parsing_corrections[field_name][auto_extracted] = []
        
        self.parsing_corrections[field_name][auto_extracted].append(user_corrected)
        self.field_stats[field_name][auto_extracted][user_corrected] += 1
        self.total_samples += 1
        self.last_trained = datetime.now()
    
    def get_correction_suggestion(self, field_name: str, text: str, confidence_threshold: float = 0.7) -> dict:
        """
        Get suggested correction for a field value
        
        Args:
            field_name: Field name
            text: Value to correct
            confidence_threshold: Minimum confidence for suggestion
            
        Returns:
            {
                'suggestion': corrected_text or None,
                'confidence': float (0-1),
                'pattern_matches': int
            }
        """
        if field_name not in self.field_stats or text not in self.field_stats[field_name]:
            return {
                'suggestion': None,
                'confidence': 0,
                'pattern_matches': 0
            }
        
        corrections = self.field_stats[field_name][text]
        if not corrections:
            return {
                'suggestion': None,
                'confidence': 0,
                'pattern_matches': 0
            }
        
        # Get most common correction
        total = sum(corrections.values())
        best_correction = max(corrections.items(), key=lambda x: x[1])
        confidence = best_correction[1] / total
        
        if confidence < confidence_threshold:
            return {
                'suggestion': None,
                'confidence': confidence,
                'pattern_matches': len(corrections)
            }
        
        return {
            'suggestion': best_correction[0],
            'confidence': confidence,
            'pattern_matches': len(corrections)
        }
    
    def get_stats(self) -> dict:
        """Get model statistics"""
        return {
            'version': self.model_version,
            'trained_at': self.last_trained.isoformat() if self.last_trained and not isinstance(self.last_trained, str) else self.last_trained,
            'total_samples': self.total_samples,
            'total_fields': len(self.parsing_corrections),
            'fields': list(self.parsing_corrections.keys())
        }
    
    def save_model(self, filename: str = 'parsing_corrections_model.json'):
        """Save model to JSON file"""
        try:
            filepath = os.path.join(self._model_dir, filename)
            model_data = {
                'version': self.model_version,
                'trained_at': self.last_trained.isoformat() if self.last_trained else None,
                'total_samples': self.total_samples,
                'parsing_corrections': self.parsing_corrections,
                'field_stats': {
                    field: {auto: dict(corrections) for auto, corrections in stats.items()}
                    for field, stats in self.field_stats.items()
                }
            }
            
            with open(filepath, 'w') as f:
                json.dump(model_data, f, indent=2)
            
            return True
        except Exception as e:
            print(f"[ParsingCorrectionModel] Error saving model: {e}")
            return False
    
    def load_model(self, filename: str = 'parsing_corrections_model.json') -> bool:
        """Load model from JSON file"""
        try:
            filepath = os.path.join(self._model_dir, filename)
            
            if not os.path.exists(filepath):
                return False
            
            with open(filepath, 'r') as f:
                model_data = json.load(f)
            
            self.model_version = model_data.get('version', self.MODEL_VERSION)
            trained_at_str = model_data.get('trained_at')
            self.last_trained = trained_at_str  # Store as string
            self.total_samples = model_data.get('total_samples', 0)
            self.parsing_corrections = model_data.get('parsing_corrections', {})
            
            # Restore field_stats
            self.field_stats = {}
            for field, stats_dict in model_data.get('field_stats', {}).items():
                self.field_stats[field] = {}
                for auto, corrections_dict in stats_dict.items():
                    self.field_stats[field][auto] = defaultdict(int, corrections_dict)
            
            return True
        except Exception as e:
            print(f"[ParsingCorrectionModel] Error loading model: {e}")
            return False
