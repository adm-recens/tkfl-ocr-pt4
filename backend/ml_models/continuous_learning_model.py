"""
Enhanced ML Correction Model with Continuous Learning

This module extends the base ML models with:
- Real-time learning from corrections
- Context-aware pattern recognition
- Confidence-based decision making
- Automatic model updates
- Performance tracking and metrics
"""

import json
import os
from datetime import datetime, timedelta
from collections import defaultdict, deque
import re
import statistics
from typing import Dict, List, Optional, Tuple, Any
import hashlib


class ContinuousLearningModel:
    """
    Advanced ML model that continuously learns and improves from corrections
    with confidence tracking and automatic pattern validation.
    """
    
    MODEL_VERSION = "2.0"
    
    def __init__(self, model_name: str = "enhanced_model"):
        self.model_name = model_name
        self.model_version = self.MODEL_VERSION
        
        # Pattern storage with confidence tracking
        self.patterns = defaultdict(lambda: {
            'corrections': defaultdict(int),
            'confidence': 0.0,
            'last_used': None,
            'success_count': 0,
            'failure_count': 0
        })
        
        # Context-aware learning
        self.context_patterns = defaultdict(lambda: defaultdict(lambda: {
            'corrections': defaultdict(int),
            'confidence': 0.0
        }))
        
        # Supplier-specific patterns
        self.supplier_patterns = defaultdict(lambda: defaultdict(lambda: {
            'patterns': defaultdict(int),
            'confidence': 0.0,
            'field_positions': defaultdict(list)
        }))
        
        # Field extraction patterns
        self.field_patterns = defaultdict(lambda: {
            'regex_patterns': [],
            'common_prefixes': defaultdict(int),
            'common_suffixes': defaultdict(int),
            'position_hints': []
        })
        
        # Performance tracking
        self.performance_history = deque(maxlen=1000)
        self.correction_history = deque(maxlen=500)
        
        # Learning statistics
        self.stats = {
            'total_corrections': 0,
            'successful_predictions': 0,
            'failed_predictions': 0,
            'unique_patterns': 0,
            'last_training': None,
            'model_accuracy': 0.0
        }
        
        self._model_dir = os.path.normpath(os.path.abspath(
            os.path.join(os.path.dirname(__file__))
        ))
        
    def learn_from_correction(self, 
                            field_name: str, 
                            raw_ocr: str, 
                            auto_extracted: str, 
                            user_corrected: str,
                            supplier_name: str = None,
                            confidence: float = 1.0) -> bool:
        """
        Learn from a single correction with context awareness
        
        Args:
            field_name: Name of the field being corrected
            raw_ocr: Raw OCR text for context
            auto_extracted: Auto-extracted value
            user_corrected: User-corrected value
            supplier_name: Optional supplier for supplier-specific learning
            confidence: Confidence level of this correction (1.0 = user validated)
        
        Returns:
            bool: True if learning occurred
        """
        if not all([field_name, auto_extracted, user_corrected]):
            return False
            
        if auto_extracted == user_corrected:
            return False
        
        # Create pattern key
        pattern_key = self._create_pattern_key(field_name, auto_extracted, raw_ocr)
        
        # Update pattern statistics
        self.patterns[pattern_key]['corrections'][user_corrected] += 1
        self.patterns[pattern_key]['last_used'] = datetime.now().isoformat()
        
        # Update confidence based on frequency
        total_corrections = sum(self.patterns[pattern_key]['corrections'].values())
        most_common = max(self.patterns[pattern_key]['corrections'].items(), 
                         key=lambda x: x[1])
        
        # Confidence calculation: frequency-based with recency bias
        base_confidence = most_common[1] / total_corrections if total_corrections > 0 else 0
        
        # Boost confidence if multiple users agree
        unique_users = len(self.patterns[pattern_key]['corrections'])
        if unique_users == 1 and total_corrections >= 3:
            base_confidence = min(0.95, base_confidence + 0.1)
        
        self.patterns[pattern_key]['confidence'] = base_confidence
        
        # Context-aware learning
        context_key = self._extract_context(raw_ocr, field_name)
        if context_key:
            self.context_patterns[field_name][context_key]['corrections'][user_corrected] += 1
            
            # Calculate context-specific confidence
            ctx_total = sum(self.context_patterns[field_name][context_key]['corrections'].values())
            ctx_best = max(self.context_patterns[field_name][context_key]['corrections'].items(),
                          key=lambda x: x[1])
            self.context_patterns[field_name][context_key]['confidence'] = ctx_best[1] / ctx_total
        
        # Supplier-specific learning
        if supplier_name:
            supplier_key = supplier_name.strip().upper()
            self.supplier_patterns[supplier_key][field_name]['patterns'][user_corrected] += 1
            
            # Learn position hints for this field
            position = self._find_field_position(raw_ocr, auto_extracted, user_corrected)
            if position:
                self.supplier_patterns[supplier_key][field_name]['field_positions'][position['type']].append(
                    position['value']
                )
        
        # Learn field extraction patterns
        self._learn_extraction_pattern(field_name, raw_ocr, user_corrected)
        
        # Update statistics
        self.stats['total_corrections'] += 1
        self.stats['unique_patterns'] = len(self.patterns)
        
        # Record in history
        self.correction_history.append({
            'timestamp': datetime.now().isoformat(),
            'field': field_name,
            'auto': auto_extracted,
            'corrected': user_corrected,
            'supplier': supplier_name,
            'confidence': confidence
        })
        
        return True
    
    def get_correction_suggestion(self, 
                                 field_name: str, 
                                 raw_ocr: str, 
                                 current_value: str,
                                 supplier_name: str = None) -> Dict[str, Any]:
        """
        Get correction suggestion with confidence scoring
        
        Returns:
            {
                'suggestion': str or None,
                'confidence': float (0-1),
                'source': str ('pattern'|'context'|'supplier'|'combined'),
                'alternatives': List[Tuple[str, float]]
            }
        """
        suggestions = []
        
        # 1. Check general patterns
        pattern_key = self._create_pattern_key(field_name, current_value, raw_ocr)
        if pattern_key in self.patterns:
            pattern_data = self.patterns[pattern_key]
            best_correction = max(pattern_data['corrections'].items(), 
                                key=lambda x: x[1])
            
            if pattern_data['confidence'] >= 0.5:  # Lower threshold for suggestions
                suggestions.append({
                    'value': best_correction[0],
                    'confidence': pattern_data['confidence'],
                    'source': 'pattern',
                    'count': best_correction[1]
                })
        
        # 2. Check context patterns
        context_key = self._extract_context(raw_ocr, field_name)
        if context_key and field_name in self.context_patterns:
            if context_key in self.context_patterns[field_name]:
                ctx_data = self.context_patterns[field_name][context_key]
                if ctx_data['confidence'] >= 0.5:
                    best_ctx = max(ctx_data['corrections'].items(),
                                  key=lambda x: x[1])
                    suggestions.append({
                        'value': best_ctx[0],
                        'confidence': ctx_data['confidence'] * 0.9,  # Slightly lower weight
                        'source': 'context',
                        'count': best_ctx[1]
                    })
        
        # 3. Check supplier-specific patterns
        if supplier_name:
            supplier_key = supplier_name.strip().upper()
            if supplier_key in self.supplier_patterns:
                if field_name in self.supplier_patterns[supplier_key]:
                    supp_data = self.supplier_patterns[supplier_key][field_name]
                    if supp_data['patterns']:
                        best_supp = max(supp_data['patterns'].items(),
                                       key=lambda x: x[1])
                        total_supp = sum(supp_data['patterns'].values())
                        supp_conf = best_supp[1] / total_supp if total_supp > 0 else 0
                        
                        if supp_conf >= 0.4:  # Even lower for supplier-specific
                            suggestions.append({
                                'value': best_supp[0],
                                'confidence': supp_conf * 0.95,
                                'source': 'supplier',
                                'count': best_supp[1]
                            })
        
        # 4. Combine suggestions if multiple sources agree
        if len(suggestions) > 1:
            # Check if multiple sources suggest the same value
            value_votes = defaultdict(list)
            for sugg in suggestions:
                value_votes[sugg['value']].append(sugg)
            
            for value, votes in value_votes.items():
                if len(votes) > 1:
                    # Multiple sources agree - boost confidence
                    combined_conf = min(0.98, max(s['confidence'] for s in votes) + 0.1)
                    suggestions.append({
                        'value': value,
                        'confidence': combined_conf,
                        'source': 'combined',
                        'count': sum(s['count'] for s in votes)
                    })
        
        # Select best suggestion
        if suggestions:
            best = max(suggestions, key=lambda x: x['confidence'])
            alternatives = [(s['value'], s['confidence']) for s in suggestions 
                          if s['value'] != best['value']]
            
            return {
                'suggestion': best['value'] if best['confidence'] >= 0.7 else None,
                'confidence': best['confidence'],
                'source': best['source'],
                'alternatives': alternatives[:3]  # Top 3 alternatives
            }
        
        return {
            'suggestion': None,
            'confidence': 0.0,
            'source': None,
            'alternatives': []
        }
    
    def record_prediction_result(self, 
                               field_name: str,
                               predicted_value: str,
                               actual_value: str,
                               confidence: float,
                               was_correct: bool):
        """
        Record the result of a prediction for performance tracking
        """
        self.performance_history.append({
            'timestamp': datetime.now().isoformat(),
            'field': field_name,
            'predicted': predicted_value,
            'actual': actual_value,
            'confidence': confidence,
            'correct': was_correct
        })
        
        if was_correct:
            self.stats['successful_predictions'] += 1
        else:
            self.stats['failed_predictions'] += 1
        
        # Update model accuracy
        total = self.stats['successful_predictions'] + self.stats['failed_predictions']
        if total > 0:
            self.stats['model_accuracy'] = self.stats['successful_predictions'] / total
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get detailed performance metrics
        """
        recent_predictions = [p for p in self.performance_history 
                            if datetime.fromisoformat(p['timestamp']) > 
                            datetime.now() - timedelta(days=7)]
        
        if recent_predictions:
            recent_correct = sum(1 for p in recent_predictions if p['correct'])
            recent_accuracy = recent_correct / len(recent_predictions)
        else:
            recent_accuracy = 0.0
        
        # Calculate confidence calibration
        confidence_bins = defaultdict(lambda: {'total': 0, 'correct': 0})
        for pred in self.performance_history:
            bin_key = int(pred['confidence'] * 10) / 10  # Round to 0.1
            confidence_bins[bin_key]['total'] += 1
            if pred['correct']:
                confidence_bins[bin_key]['correct'] += 1
        
        calibration = {}
        for bin_key, data in confidence_bins.items():
            if data['total'] > 0:
                calibration[f"{bin_key:.1f}"] = {
                    'predicted_accuracy': bin_key + 0.05,
                    'actual_accuracy': data['correct'] / data['total'],
                    'sample_count': data['total']
                }
        
        # Most reliable patterns
        reliable_patterns = []
        for pattern_key, data in self.patterns.items():
            if data['confidence'] >= 0.8 and sum(data['corrections'].values()) >= 3:
                best = max(data['corrections'].items(), key=lambda x: x[1])
                reliable_patterns.append({
                    'pattern': pattern_key,
                    'suggestion': best[0],
                    'confidence': data['confidence'],
                    'usage_count': sum(data['corrections'].values())
                })
        
        reliable_patterns.sort(key=lambda x: x['confidence'], reverse=True)
        
        return {
            'overall_accuracy': self.stats['model_accuracy'],
            'recent_accuracy_7d': recent_accuracy,
            'total_corrections_learned': self.stats['total_corrections'],
            'unique_patterns': self.stats['unique_patterns'],
            'successful_predictions': self.stats['successful_predictions'],
            'failed_predictions': self.stats['failed_predictions'],
            'confidence_calibration': calibration,
            'most_reliable_patterns': reliable_patterns[:10],
            'last_training': self.stats['last_training']
        }
    
    def _create_pattern_key(self, field_name: str, auto_value: str, raw_ocr: str) -> str:
        """Create a unique pattern key for lookup"""
        # Normalize auto_value
        normalized = str(auto_value).strip().lower()
        return f"{field_name}:{normalized}"
    
    def _extract_context(self, raw_ocr: str, field_name: str) -> Optional[str]:
        """Extract context signature from OCR text"""
        if not raw_ocr:
            return None
        
        # Look for field-specific context
        context_markers = {
            'voucher_number': [r'voucher\s*number', r'vouchernumber', r'nuaber', r'nunber'],
            'voucher_date': [r'voucher\s*date', r'voucherdate', r'date'],
            'supplier_name': [r'supp\s*name', r'suppname', r'name', r'nane', r'supplier'],
            'gross_total': [r'gross', r'total', r'amount'],
            'net_total': [r'net', r'grand', r'final']
        }
        
        markers = context_markers.get(field_name, [])
        found_markers = []
        
        for marker in markers:
            if re.search(marker, raw_ocr, re.IGNORECASE):
                found_markers.append(marker)
        
        if found_markers:
            return "|".join(sorted(found_markers))
        
        return None
    
    def _find_field_position(self, raw_ocr: str, auto_value: str, correct_value: str) -> Optional[Dict]:
        """Find the position of a field in OCR text"""
        if not raw_ocr:
            return None
        
        lines = raw_ocr.split('\n')
        
        for i, line in enumerate(lines):
            if str(auto_value) in line or str(correct_value) in line:
                # Calculate relative position (beginning, middle, end)
                position_ratio = i / len(lines) if len(lines) > 0 else 0
                
                if position_ratio < 0.3:
                    position_type = 'beginning'
                elif position_ratio < 0.7:
                    position_type = 'middle'
                else:
                    position_type = 'end'
                
                return {
                    'type': position_type,
                    'value': i,
                    'line': line.strip()[:50]  # Store sample
                }
        
        return None
    
    def _learn_extraction_pattern(self, field_name: str, raw_ocr: str, correct_value: str):
        """Learn regex patterns for field extraction"""
        if not raw_ocr or not correct_value:
            return
        
        # Find the line containing the correct value
        lines = raw_ocr.split('\n')
        
        for line in lines:
            if str(correct_value) in line:
                # Learn common prefixes and suffixes
                idx = line.find(str(correct_value))
                if idx >= 0:
                    prefix = line[:idx].strip()
                    suffix = line[idx + len(str(correct_value)):].strip()
                    
                    if prefix:
                        # Extract last word or separator
                        words = prefix.split()
                        if words:
                            self.field_patterns[field_name]['common_prefixes'][words[-1]] += 1
                    
                    if suffix:
                        words = suffix.split()
                        if words:
                            self.field_patterns[field_name]['common_suffixes'][words[0]] += 1
                
                break
    
    def save_model(self, filename: str = None) -> bool:
        """Save model to JSON file"""
        if filename is None:
            filename = f'{self.model_name}_v{self.model_version}.json'
        
        try:
            filepath = os.path.join(self._model_dir, filename)
            
            # Convert patterns to serializable format
            patterns_data = {}
            for key, data in self.patterns.items():
                patterns_data[key] = {
                    'corrections': dict(data['corrections']),
                    'confidence': data['confidence'],
                    'last_used': data['last_used'],
                    'success_count': data['success_count'],
                    'failure_count': data['failure_count']
                }
            
            # Convert context patterns
            context_data = {}
            for field, contexts in self.context_patterns.items():
                context_data[field] = {}
                for ctx, data in contexts.items():
                    context_data[field][ctx] = {
                        'corrections': dict(data['corrections']),
                        'confidence': data['confidence']
                    }
            
            # Convert supplier patterns
            supplier_data = {}
            for supp, fields in self.supplier_patterns.items():
                supplier_data[supp] = {}
                for field, data in fields.items():
                    supplier_data[supp][field] = {
                        'patterns': dict(data['patterns']),
                        'confidence': data['confidence'],
                        'field_positions': dict(data['field_positions'])
                    }
            
            model_data = {
                'model_name': self.model_name,
                'version': self.model_version,
                'saved_at': datetime.now().isoformat(),
                'patterns': patterns_data,
                'context_patterns': context_data,
                'supplier_patterns': supplier_data,
                'field_patterns': dict(self.field_patterns),
                'stats': self.stats,
                'performance_history': list(self.performance_history)[-100:],  # Last 100
                'correction_history': list(self.correction_history)[-50:]  # Last 50
            }
            
            with open(filepath, 'w') as f:
                json.dump(model_data, f, indent=2)
            
            return True
        except Exception as e:
            print(f"[ContinuousLearningModel] Error saving model: {e}")
            return False
    
    def load_model(self, filename: str = None) -> bool:
        """Load model from JSON file"""
        if filename is None:
            filename = f'{self.model_name}_v{self.model_version}.json'
        
        try:
            filepath = os.path.join(self._model_dir, filename)
            
            if not os.path.exists(filepath):
                return False
            
            with open(filepath, 'r') as f:
                model_data = json.load(f)
            
            # Restore patterns
            for key, data in model_data.get('patterns', {}).items():
                self.patterns[key] = {
                    'corrections': defaultdict(int, data.get('corrections', {})),
                    'confidence': data.get('confidence', 0.0),
                    'last_used': data.get('last_used'),
                    'success_count': data.get('success_count', 0),
                    'failure_count': data.get('failure_count', 0)
                }
            
            # Restore context patterns
            for field, contexts in model_data.get('context_patterns', {}).items():
                for ctx, data in contexts.items():
                    self.context_patterns[field][ctx] = {
                        'corrections': defaultdict(int, data.get('corrections', {})),
                        'confidence': data.get('confidence', 0.0)
                    }
            
            # Restore supplier patterns
            for supp, fields in model_data.get('supplier_patterns', {}).items():
                for field, data in fields.items():
                    self.supplier_patterns[supp][field] = {
                        'patterns': defaultdict(int, data.get('patterns', {})),
                        'confidence': data.get('confidence', 0.0),
                        'field_positions': defaultdict(list, data.get('field_positions', {}))
                    }
            
            # Restore field patterns
            self.field_patterns = defaultdict(lambda: {
                'regex_patterns': [],
                'common_prefixes': defaultdict(int),
                'common_suffixes': defaultdict(int),
                'position_hints': []
            })
            for field, data in model_data.get('field_patterns', {}).items():
                self.field_patterns[field] = {
                    'regex_patterns': data.get('regex_patterns', []),
                    'common_prefixes': defaultdict(int, data.get('common_prefixes', {})),
                    'common_suffixes': defaultdict(int, data.get('common_suffixes', {})),
                    'position_hints': data.get('position_hints', [])
                }
            
            # Restore stats
            self.stats = model_data.get('stats', self.stats)
            
            return True
        except Exception as e:
            print(f"[ContinuousLearningModel] Error loading model: {e}")
            return False
    
    def cleanup_old_patterns(self, days: int = 90) -> int:
        """
        Remove patterns older than specified days with low confidence
        Returns number of patterns removed
        """
        cutoff = datetime.now() - timedelta(days=days)
        removed = 0
        
        patterns_to_remove = []
        for key, data in self.patterns.items():
            last_used = data.get('last_used')
            if last_used:
                try:
                    last_used_dt = datetime.fromisoformat(last_used)
                    if last_used_dt < cutoff and data['confidence'] < 0.3:
                        patterns_to_remove.append(key)
                except:
                    pass
        
        for key in patterns_to_remove:
            del self.patterns[key]
            removed += 1
        
        return removed


# Global instance for easy access
_enhanced_model = None

def get_enhanced_model() -> ContinuousLearningModel:
    """Get or create the global enhanced model instance"""
    global _enhanced_model
    if _enhanced_model is None:
        _enhanced_model = ContinuousLearningModel()
        _enhanced_model.load_model()
    return _enhanced_model
