from backend.parser import parse_receipt_text
import json

# Mock text based on User's Image
mock_ocr_text = """
Phone : 0123456789

Voucher Number 202
Voucher Date 07/12/2024
Supp Name TK

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
Grand Total                 12193.50
"""

print("--- Mock OCR Text (User Image) ---")
print(mock_ocr_text)
print("---------------------")

parsed_data = parse_receipt_text(mock_ocr_text)

with open("reproduction_result.json", "w") as f:
    json.dump(parsed_data, f, indent=4)

print("Result saved to reproduction_result.json")
