from backend.services.voucher_service import VoucherService
from backend.app import create_app

app = create_app()
with app.app_context():
    # get_all_vouchers takes 'page' argument, not 'per_page' based on previous error
    # Let's try with just page=1
    vouchers = VoucherService.get_all_vouchers(page=1)
    print("Recent Vouchers:")
    # It returns a dict with 'vouchers' list
    for v in vouchers['vouchers'][:5]:
        print(f"ID: {v['id']}, File: {v['file_name']}, Mode: {v['ocr_mode']}")
