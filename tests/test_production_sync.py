from backend import create_app
from backend.services.batch_service import BatchService
from backend.services.production_sync_service import ProductionSyncService
from backend.db import get_connection

def test_sync():
    app = create_app()
    with app.app_context():
        # 1. Get a batch
        result = BatchService.get_all_batches(limit=1)
        if not result['batches']:
            print("No batches found to test.")
            return
            
        batch_id = result['batches'][0]['batch_id']
        print(f"Testing sync for Batch ID: {batch_id}")
        
        # 2. Run Sync
        success = ProductionSyncService.sync_batch_to_production(batch_id)
        
        if success:
            print("Sync reported success.")
            
            # 3. Verify Data
            conn = get_connection()
            cur = conn.cursor()
            
            cur.execute("SELECT COUNT(*) as c FROM suppliers")
            s_count = cur.fetchone()['c']
            
            cur.execute("SELECT COUNT(*) as c FROM receipts")
            r_count = cur.fetchone()['c']
            
            print(f"Verification Results:")
            print(f"Total Suppliers: {s_count}")
            print(f"Total Receipts: {r_count}")
            
            # Show a receipt
            cur.execute("SELECT * FROM receipts LIMIT 1")
            r = cur.fetchone()
            if r:
                print("Sample Receipt:", dict(r))
                
        else:
            print("Sync failed.")

if __name__ == "__main__":
    test_sync()
