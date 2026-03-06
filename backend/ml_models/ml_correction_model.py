"""
ML Correction Models for OCR and Parsing Corrections

This module contains:
- OCRCorrectionModel: Learns and applies OCR character/word corrections
- ParsingCorrectionModel: Learns and applies field extraction corrections
"""

import json
import os
from datetime import datetime
import re
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
        Learn a character-level correction pattern from user feedback using Levenshtein distance
        
        Args:
            raw_ocr: Original OCR text
            auto_extracted: Auto-extracted value
            user_corrected: Corrected value by user
            field_name: Optional field context
        """
        if not auto_extracted or not user_corrected or auto_extracted == user_corrected:
            return
            
        import difflib
        matcher = difflib.SequenceMatcher(None, auto_extracted, user_corrected)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                bad_char = auto_extracted[i1:i2]
                good_char = user_corrected[j1:j2]
                
                # We only want to learn small character-level confusions, not entire strings
                if len(bad_char) <= 4 and len(good_char) <= 4:
                    if bad_char not in self.ocr_patterns:
                        self.ocr_patterns[bad_char] = []
                        self.pattern_stats[bad_char] = defaultdict(int)
                    
                    self.ocr_patterns[bad_char].append(good_char)
                    self.pattern_stats[bad_char][good_char] += 1
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
        
    def apply_ocr_corrections(self, text: str) -> str:
        """Globally apply high-confidence learned character swaps to raw text before parsing."""
        if not text or not self.pattern_stats:
            return text
            
        corrected_text = text
        for bad_char, corrections in self.pattern_stats.items():
            total = sum(corrections.values())
            if total == 0: continue
            
            best_correction = max(corrections.items(), key=lambda x: x[1])
            confidence = best_correction[1] / total
            
            # Safely replace known bad OCR hallucinations with high confidence
            if confidence >= 0.8 and total >= 2:
                corrected_text = corrected_text.replace(bad_char, best_correction[0])
                
        return corrected_text
    
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
        
        # New: Anchor Learning
        # {supplier_name: {field_name: {anchor_text: count}}}
        self.learned_anchors = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        
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
    
    def learn_anchor(self, field_name: str, raw_ocr: str, corrected_value: str, supplier_name: str):
        """
        Learn the textual anchor (label) preceding a corrected value.
        Used for adaptive parsing.
        """
        if not all([field_name, raw_ocr, corrected_value, supplier_name]):
            return

        # Find what text comes immediately before the corrected_value
        anchor = self._find_anchor_in_text(raw_ocr, corrected_value)
        if anchor:
            # Store anchor for this supplier & field
            # Use supplier hash or name as key
            supplier_key = supplier_name.strip().upper()
            self.learned_anchors[supplier_key][field_name][anchor] += 1
            self.last_trained = datetime.now()

    def _find_anchor_in_text(self, text: str, target_value: str) -> str:
        """
        Finds the 2-4 words immediately preceding the target_value in text.
        Returns the anchor string or None.
        """
        if not target_value or not text:
            return None
            
        # Generate candidates (handle Date format differences)
        candidates = [target_value]
        # Check if target is ISO date (YYYY-MM-DD)
        if re.match(r'^\d{4}-\d{2}-\d{2}$', target_value):
            try:
                dt_obj = datetime.strptime(target_value, "%Y-%m-%d")
                candidates.extend([
                    dt_obj.strftime("%d/%m/%Y"), # 04/01/2026
                    dt_obj.strftime("%d-%m-%Y"), # 04-01-2026
                    dt_obj.strftime("%d.%m.%Y"), # 04.01.2026
                    dt_obj.strftime("%Y/%m/%d"), # 2026/01/04
                    dt_obj.strftime("%d-%b-%Y"), # 04-Jan-2026
                ])
            except ValueError:
                pass
        
        for val in candidates:
            try:
                # Escape target for regex
                escaped_target = re.escape(val)
                
                # Look for: (Anchor Group) + (Optional Whitespace/Separators) + Target
                # Capture up to 30 chars before the target
                pattern = re.compile(r"(.{2,30}?)\s*[:=-]?\s*" + escaped_target, re.IGNORECASE | re.DOTALL)
                
                matches = list(pattern.finditer(text))
                if matches:
                            # Take the last match (often the most immediate one if duplicates exist)
                    match = matches[-1]
                    anchor_candidate = match.group(1).strip()
                    
                    # Cleanup: Take last 3-4 words max to avoid capturing whole paragraphs
                    words = anchor_candidate.split()
                    if len(words) > 4:
                        anchor_candidate = " ".join(words[-4:])
                    
                    # Cleanup: Remove trailing separators
                    anchor_candidate = re.sub(r"[\s:=-]+$", "", anchor_candidate).strip()
                    
                    if len(anchor_candidate) > 2:
                        return anchor_candidate
            except Exception:
                continue
                
        return None

    def find_value_by_anchor(self, field_name: str, raw_ocr: str, supplier_name: str) -> dict:
        """
        Scan raw OCR for values using learned fuzzy anchors for this supplier.
        """
        if not supplier_name:
            return None
        
        supplier_key = supplier_name.strip().upper()
        if supplier_key not in self.learned_anchors:
            return None
            
        anchors = self.learned_anchors[supplier_key].get(field_name, {})
        if not anchors:
            return None
            
        # Sort anchors by frequency (most common first)
        sorted_anchors = sorted(anchors.items(), key=lambda x: x[1], reverse=True)
        import difflib
        
        lines = [line.strip() for line in raw_ocr.split('\n') if line.strip()]
        
        for anchor_text, count in sorted_anchors:
            if count < 1: continue # Ignore noise
            
            anchor_words = anchor_text.split()
            anchor_len = len(anchor_words)
            
            for line_idx, line in enumerate(lines):
                words = line.split()
                if len(words) < anchor_len:
                    continue
                    
                # Sliding window of words to find the anchor
                for window_idx in range(len(words) - anchor_len + 1):
                    window = " ".join(words[window_idx:window_idx + anchor_len])
                    similarity = difflib.SequenceMatcher(None, anchor_text.lower(), window.lower()).ratio()
                    
                    if similarity > 0.82:  # Fuzzy match threshold to ignore bad OCR!
                        # We found the anchor! The value is what follows it
                        remaining_line = " ".join(words[window_idx + anchor_len:])
                        # Clean leading separators
                        remaining_line = re.sub(r"^[\s:=-]+", "", remaining_line).strip()
                        
                        value = remaining_line
                        
                        if not value and line_idx + 1 < len(lines):
                            # Value is on the next line (Spatial Context)
                            value = lines[line_idx + 1].strip()
                            
                        if value:
                            # Basic cleanup: stop at double space or large gaps
                            value = re.sub(r"\s{2,}.*", "", value)
                            return {
                                'value': value,
                                'confidence': 0.85 + (min(count, 10) / 100.0), # Active high confidence
                                'anchor': anchor_text
                            }
        return None

    def save_model(self, filename: str = 'parsing_corrections_model.json'):
        """Save model to JSON file"""
        try:
            filepath = os.path.join(self._model_dir, filename)
            
            # Convert nested defaultdicts to standard dicts for JSON
            learned_anchors_dict = {}
            for supp, fields in self.learned_anchors.items():
                learned_anchors_dict[supp] = {}
                for fld, anchors in fields.items():
                    learned_anchors_dict[supp][fld] = dict(anchors)

            model_data = {
                'version': self.model_version,
                'trained_at': self.last_trained.isoformat() if self.last_trained else None,
                'total_samples': self.total_samples,
                'parsing_corrections': self.parsing_corrections,
                'learned_anchors': learned_anchors_dict,
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
            
            # Restore learned anchors
            anchors_data = model_data.get('learned_anchors', {})
            self.learned_anchors = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
            for supp, fields in anchors_data.items():
                for fld, anchors in fields.items():
                    for anchor, count in anchors.items():
                        self.learned_anchors[supp][fld][anchor] = count

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
