import requests
import time
import sys

# The Queue ID from your logs that failed
QUEUE_ID = "9ddfc826-74f6-4d30-9745-b29c319be6dd"
BASE_URL = "http://127.0.0.1:5000/api/queue"

def reprocess():
    print(f"Triggering Reprocess for Queue: {QUEUE_ID}")
    
    # 1. Reset the batch
    try:
        resp = requests.post(f"{BASE_URL}/{QUEUE_ID}/reprocess")
        if resp.status_code == 200:
            print(f"✅ Batch Reset Successful! Files ready: {resp.json().get('reset_count')}")
        else:
            print(f"❌ Reset Failed: {resp.text}")
            return
    except Exception as e:
        print(f"❌ Connection Error (is server running?): {e}")
        return

    # 2. Start Processing Again
    print("Starting Processing...")
    try:
        resp = requests.post(f"{BASE_URL}/{QUEUE_ID}/process_batch")
        if resp.status_code == 202:
            print("✅ Batch Processing Started! Check your terminal for logs.")
        else:
            print(f"⚠️ Processing Start Failed: {resp.text}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    reprocess()
