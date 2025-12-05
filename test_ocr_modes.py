from backend.ocr_utils import extract_text as extract_text_adv
import os

# List files in uploads
print("=== FILES IN UPLOADS ===")
files = os.listdir('uploads')
if not files:
    print("No files found!")
    exit()

latest_file = files[-1]
filepath = os.path.join('uploads', latest_file)
print(f"Testing with: {filepath}")

modes = ['contrast', 'threshold', 'resize', 'default']

for mode in modes:
    print(f"\n--- Testing Mode: {mode} ---")
    try:
        text = extract_text_adv(filepath, mode=mode)
        if text.startswith('[OCR ERROR]'):
            print(f"FAILED: {text}")
        else:
            print(f"SUCCESS. Length: {len(text)}")
            print(text[:100].replace('\n', ' '))
    except Exception as e:
        print(f"EXCEPTION: {e}")
