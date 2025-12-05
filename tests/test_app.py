import unittest
from backend import create_app

class BasicTests(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def test_index_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'VoucherOCR', response.data)

    def test_upload_page(self):
        response = self.client.get('/upload')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Upload Voucher', response.data)

    def test_receipts_page(self):
        response = self.client.get('/receipts')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Receipts History', response.data)

if __name__ == "__main__":
    unittest.main()
