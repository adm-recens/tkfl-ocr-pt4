"""
Quick test script for bulk upload API
"""
import requests

url = "http://localhost:5000/api/bulk/upload"

# Test if route is registered
try:
    response = requests.get("http://localhost:5000/api/bulk/status/test123")
    print(f"Status check response: {response.status_code}")
    print(f"Response: {response.text[:200]}")
except Exception as e:
    print(f"Error: {e}")
