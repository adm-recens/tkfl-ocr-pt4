# Test the actual OCR text to see what patterns we need
test_text = """
Phone raaon244i2i39. 9949333786
jess For Damages 180.00
cher Date 2671172024   
UnLoading 58.40        
36.00
pp Name
L/F And Cash 440.00    
srend Total 2742.00    
2 150.00 300.00        
ASal = sen0.00
AHMED SHARIF & BROS    
Comm @ ? 4.00 % 144.00 
"""

print("Looking for patterns:")
print("Voucher Number patterns:")
import re
vn = re.search(r"(?:Voucher\s*No|Invoice\s*No|Bill\s*No)\s*[:\-]?\s*(\w+)", test_text, re.IGNORECASE)
print(f"  Found: {vn}")

print("\nDate patterns:")
dt = re.search(r"(?:Date|DATED|Dt)\s*[:\-]?\s*([\d/\.\-]+)", test_text, re.IGNORECASE)
print(f"  Found: {dt}")

print("\nTrying looser date pattern:")
dt2 = re.search(r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", test_text)
print(f"  Found: {dt2}")

print("\nLooking for numbers:")
nums = re.findall(r"\d+\.?\d*", test_text)
print(f"  Numbers found: {nums}")
