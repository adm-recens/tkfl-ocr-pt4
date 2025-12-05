from backend.parser import parse_receipt_text
import json

# Based on user's screenshot - this is what the receipt should have
mock_ocr_text = """
AHMED SHARIF & BROS
Phone: 0123456789

Voucher Number 202
Voucher Date 07/12/2024
Supp Name None TK

      Qty    Price   Amount
--------------------------------
      13     920.00   11960.00
      4      500.00   2000.00
      6      280.00   1680.00
--------------------------------
Total      23           15640.00

(-)      Comm @ ? 4.00 %     625.60
(-)      Less For Damages    782.00
(-)      UnLoading           167.90
(-)                          156.00
(-)      L/F And Cash        1715.00
--------------------------------
Grand Total                 12193.00
"""

print("--- Testing Parser with User's Receipt Format ---")
print(mock_ocr_text)
print("\n" + "="*50 + "\n")

parsed_data = parse_receipt_text(mock_ocr_text)

print("PARSED RESULTS:")
print(json.dumps(parsed_data, indent=2))

# Save to file
with open("test_parse_output.json", "w") as f:
    json.dump(parsed_data, f, indent=2)

print("\n" + "="*50)
print("Saved to test_parse_output.json")
