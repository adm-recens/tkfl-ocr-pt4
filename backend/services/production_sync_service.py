from backend.db import get_connection
from backend.services.voucher_service import VoucherService
import re

class ProductionSyncService:
    @staticmethod
    def sync_batch_to_production(batch_id):
        """
        Syncs all vouchers in a batch to the independent 'receipts' and 'suppliers' tables.
        This is an additive process and does not modify the source vouchers.
        """
        conn = get_connection()
        try:
            cur = conn.cursor()
            vouchers = VoucherService.get_all_vouchers() # Filter by batch ideally, but for now we filter in loop or improved query
            
            # Better: Fetch only for this batch
            cur.execute("SELECT * FROM vouchers_master WHERE batch_id = %s", (batch_id,))
            batch_vouchers = cur.fetchall()
            
            synced_count = 0
            
            for v in batch_vouchers:
                # 1. Resolve Supplier
                supplier_name = v.get('supplier_name') or "Unknown Supplier"
                supplier_name = supplier_name.strip()
                
                # Check if exists
                cur.execute("SELECT id FROM suppliers WHERE name = %s", (supplier_name,))
                supplier_row = cur.fetchone()
                
                if supplier_row:
                    supplier_id = supplier_row['id']
                else:
                    # Create new
                    cur.execute("INSERT INTO suppliers (name) VALUES (%s) RETURNING id", (supplier_name,))
                    supplier_id = cur.fetchone()['id']
                
                # 2. Map Deductions
                # Fetch deductions for this voucher
                cur.execute("SELECT * FROM voucher_deductions WHERE master_id = %s", (v['id'],))
                deductions = cur.fetchall()
                
                d_comm = 0
                d_damage = 0
                d_unloading = 0
                d_lfcash = 0
                d_other = 0
                
                for d in deductions:
                    amount = float(d.get('amount') or 0)
                    dtype = (d.get('deduction_type') or "").lower()
                    
                    if "comm" in dtype:
                        d_comm += amount
                    elif "damage" in dtype:
                        d_damage += amount
                    elif "unloading" in dtype:
                        d_unloading += amount
                    elif "cash" in dtype or "l/f" in dtype:
                        d_lfcash += amount
                    else:
                        d_other += amount
                
                # 3. Create Receipt
                cur.execute("""
                    INSERT INTO receipts (
                        supplier_id, ocr_voucher_id, 
                        receipt_number, receipt_date,
                        gross_total, total_deductions, net_total,
                        deduction_commission, deduction_damage, deduction_unloading, deduction_lf_cash, deduction_other
                    ) VALUES (
                        %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s, %s
                    )
                """, (
                    supplier_id, v['id'],
                    v.get('voucher_number'), v.get('voucher_date'),
                    v.get('gross_total') or 0, v.get('total_deductions') or 0, v.get('net_total') or 0,
                    d_comm, d_damage, d_unloading, d_lfcash, d_other
                ))
                
                synced_count += 1
            
            conn.commit()
            print(f"✅ Synced {synced_count} receipts to production for batch {batch_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error syncing batch {batch_id}: {e}")
            conn.rollback()
            return False
