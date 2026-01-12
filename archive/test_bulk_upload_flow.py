
import json
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import get_connection

def test_bulk_workflow():
    print("Testing Bulk Upload Workflow API...")
    
    # 1. Simulate Batch Creation
    from backend.services.batch_service import BatchService
    
    print("\n1. creating batch...")
    batch_id = BatchService.create_batch("Test Batch Automated", 3, "tester")
    print(f"Batch created: {batch_id}")
    
    # Verify DB
    batch = BatchService.get_batch(batch_id)
    print(f"Batch from DB: {batch['batch_name']} (Total: {batch['total_files']})")
    assert batch['total_files'] == 3
    assert batch['status'] == 'processing'
    
    # 2. Simulate Save Batch (which updates stats)
    print("\n2. Updating batch stats...")
    BatchService.update_batch_stats(batch_id, success=True)
    BatchService.update_batch_stats(batch_id, success=True)
    BatchService.update_batch_stats(batch_id, failure=True)
    
    batch = BatchService.get_batch(batch_id)
    print(f"Stats: Processed={batch['processed_files']}, Validated={batch['validated_files']}, Failed={batch['failed_files']}")
    assert batch['processed_files'] == 3
    assert batch['validated_files'] == 2
    assert batch['failed_files'] == 1
    
    # 3. Complete Batch
    print("\n3. Completing batch...")
    BatchService.complete_batch(batch_id)
    
    batch = BatchService.get_batch(batch_id)
    print(f"Status: {batch['status']}")
    assert batch['status'] == 'completed'
    assert batch['completed_at'] is not None
    
    print("\n✅ Bulk Upload Workflow Test Passed!")

if __name__ == "__main__":
    try:
        test_bulk_workflow()
    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()
