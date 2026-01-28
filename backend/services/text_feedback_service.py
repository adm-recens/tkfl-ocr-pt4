import os
import json
import uuid
import re
from datetime import datetime

class TextFeedbackService:
    """
    Service to collect text-based feedback for Named Entity Recognition (NER) training.
    Saves raw OCR text + validated entity values to a JSONL dataset.
    """
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATASET_DIR = os.path.join(BASE_DIR, "ml_dataset")
    TEXT_DATASET_FILE = os.path.join(DATASET_DIR, "text_corrections.jsonl")

    @classmethod
    def _ensure_dirs(cls):
        os.makedirs(cls.DATASET_DIR, exist_ok=True)

    @classmethod
    def save_correction(cls, raw_text: str, validated_data: dict, source_file: str = None) -> bool:
        """
        Save a training example: Raw Text -> Corrected Entities.
        
        Args:
            raw_text: The full text content from OCR.
            validated_data: Dict containing 'master' keys (supplier_name, voucher_date, total, etc.)
            source_file: Optional filename for traceability.
        """
        try:
            cls._ensure_dirs()
            
            if not raw_text or not validated_data:
                return False

            # precision alignment (finding where the values occur in the text)
            # This is "weak supervision" - we assume the user's value exists in the text.
            # If it doesn't (user typed something new), we can't label a span, 
            # but we save the record anyway for potential generative approaches.
            
            entities = cls._align_entities(raw_text, validated_data)
            
            record = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat(),
                "source_file": source_file,
                "text": raw_text,
                "labels": entities,  # List of [start, end, LABEL]
                "validated_values": validated_data, # The ground truth values
                "metadata": {
                    "source": "user_correction"
                }
            }

            with open(cls.TEXT_DATASET_FILE, "a", encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                
            print(f"[NER-FEEDBACK] Saved text correction for {source_file}")
            return True
            
        except Exception as e:
            print(f"[NER-FEEDBACK] Error saving text feedback: {e}")
            return False

    @staticmethod
    def _align_entities(text: str, data: dict) -> list:
        """
        Find occurrences of trusted values in the raw text to generate training spans.
        Returns: list of [start, end, label]
        """
        spans = []
        text_lower = text.lower()
        
        # Mapping of Data Keys to NER Labels
        key_map = {
            'supplier_name': 'ORG',      # Merchant/Organization
            'voucher_date': 'DATE',      # Date
            'gross_total': 'MONEY',      # Total Amount
            'net_total': 'MONEY',        # Net Amount (context dependent)
            'total_deductions': 'MONEY'
        }

        for key, value in data.items():
            if not value:
                continue
                
            label = key_map.get(key)
            if not label:
                continue

            # Convert value to string for search
            val_str = str(value)
            
            # Special handling for floats to match currency formats
            if isinstance(value, float):
                # Try explicit format "123.45"
                queries = [f"{value:.2f}", f"{value:.0f}"] # Try 123.45 and 123
            else:
                queries = [val_str]

            for query in queries:
                # Simple exact match search (case insensitive)
                # In a real system, we'd use more robust fuzzy matching
                start = text_lower.find(query.lower())
                if start != -1:
                    end = start + len(query)
                    
                    # Verify no overlap with existing spans (simple greedy approach)
                    is_overlap = False
                    for s, e, l in spans:
                        if (start < e) and (end > s):
                            is_overlap = True
                            break
                    
                    if not is_overlap:
                        # Use the original casing from the text for the span
                        spans.append([start, end, label])
                        break # Found one match for this value, move to next key

        return spans
