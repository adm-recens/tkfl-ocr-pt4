try:
    import easyocr
    import numpy as np
    from PIL import Image
except ImportError:
    easyocr = None

def extract_text_easyocr(image_path):
    if easyocr is None:
        return "[OCR ERROR] EasyOCR not installed. Please install 'easyocr' and 'torch'."
        
    try:
        reader = easyocr.Reader(['en'])
        img = Image.open(image_path)
        img_np = np.array(img)
        result = reader.readtext(img_np, detail=0)
        return '\n'.join(result)
    except Exception as e:
        return f"[OCR ERROR] EasyOCR failed: {str(e)}"
