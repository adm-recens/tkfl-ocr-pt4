import cv2
import numpy as np

print(f"OpenCV Version: {cv2.__version__}")
print(f"NumPy Version: {np.__version__}")

try:
    # Test basic functionality
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    print("Basic OpenCV test passed!")
except Exception as e:
    print(f"OpenCV test failed: {e}")
