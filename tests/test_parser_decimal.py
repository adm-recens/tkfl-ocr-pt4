import unittest
from backend import parser_roi

class TestParserDecimals(unittest.TestCase):
    def test_deductions_label_with_inline_percent(self):
        txt = "Comm 4.00 57.20"
        d = parser_roi.parse_deductions_region(txt)
        print('PARSED DEDUCTIONS:', d)
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0]['deduction_type'].lower(), 'comm')
        self.assertAlmostEqual(d[0]['amount'], 57.20, places=2)

    def test_deductions_missing_decimal(self):
        txt = "Unloading 4000"
        d = parser_roi.parse_deductions_region(txt)
        self.assertEqual(len(d), 1)
        # 4000 should be interpreted as 40.00 (heuristic for missing dot)
        self.assertAlmostEqual(d[0]['amount'], 40.00, places=2)
        self.assertEqual(d[0]['deduction_type'].lower(), 'unloading')

    def test_totals_with_comma_decimal(self):
        txt = "Total Deductions 1,234.56"
        t = parser_roi.parse_totals_region(txt)
        self.assertAlmostEqual(t['total_deductions'], 1234.56, places=2)

    def test_items_with_mixed_separators(self):
        txt = "Widget 1 2500 2500"
        items = parser_roi.parse_items_region(txt)
        # last token 2500 -> 25.00 line amount by heuristic
        self.assertEqual(len(items), 1)
        self.assertAlmostEqual(items[0]['line_amount'], 25.00, places=2)

if __name__ == '__main__':
    unittest.main()
