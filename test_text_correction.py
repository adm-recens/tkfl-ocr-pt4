#!/usr/bin/env python3
"""Test the text correction flow to verify the issue."""

from backend.text_correction import apply_text_corrections

# Test various OCR errors for "Supp Name"
test_cases = [
    "SuppNanm3 TK",      # OCR error -> corrected to SuppName (wrong path)
    "SuppNam3 TK",       # OCR error -> corrected to SuppName (wrong path)
    "SuppName TK",       # Already corrected once -> might stay as SuppName
    "Supp Name TK",      # Correct form
]

print("=" * 70)
print("TEXT CORRECTION TEST - SUPPLIER NAME")
print("=" * 70)

for test_input in test_cases:
    corrected = apply_text_corrections(test_input)
    print(f"Input:     '{test_input}'")
    print(f"Output:    '{corrected}'")
    print(f"Has space: {'Yes' if 'Supp Name' in corrected else 'No'}")
    print()
