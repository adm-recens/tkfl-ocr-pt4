from backend.db import get_connection
import json
import math

class VoucherService:
    @staticmethod
    def get_all_vouchers(page=1, page_size=10):
        conn = get_connection()
        cur = conn.cursor()
        
        offset = (page - 1) * page_size
        
        # Get total count
        cur.execute("SELECT COUNT(*) as total FROM vouchers_master")
        total_vouchers = cur.fetchone()['total']
        total_pages = math.ceil(total_vouchers / page_size) if total_vouchers > 0 else 1
        
        # Get paginated data
        cur.execute("""
            SELECT id, file_name, voucher_number, voucher_date, supplier_name, 
                   gross_total, net_total, validation_status, ocr_mode, created_at 
            FROM vouchers_master 
            ORDER BY created_at DESC, id DESC
            LIMIT %s OFFSET %s
        """, (page_size, offset))
        
        vouchers = cur.fetchall()
        
        return {
            'vouchers': vouchers,
            'total_vouchers': total_vouchers,
            'total_pages': total_pages,
            'current_page': page
        }

    @staticmethod
    def get_voucher_by_id(voucher_id):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM vouchers_master WHERE id = %s", (voucher_id,))
        return cur.fetchone()

    @staticmethod
    def get_voucher_items(voucher_id):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM voucher_items WHERE master_id = %s ORDER BY id", (voucher_id,))
        return cur.fetchall()

    @staticmethod
    def get_voucher_deductions(voucher_id):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM voucher_deductions WHERE master_id = %s ORDER BY id", (voucher_id,))
        return cur.fetchall()

    @staticmethod
    def create_voucher(file_name, file_storage_path, raw_text, parsed_data, ocr_mode='default'):
        conn = get_connection()
        cur = conn.cursor()
        
        master = parsed_data.get('master', {})
        
        cur.execute("""
            INSERT INTO vouchers_master (
                file_name, file_storage_path, raw_ocr_text, parsed_json,
                voucher_number, voucher_date, supplier_name, vendor_details,
                gross_total, total_deductions, net_total,
                validation_status, ocr_mode
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'RAW', %s)
            RETURNING id
        """, (
            file_name,
            file_storage_path,
            raw_text,
            json.dumps(parsed_data, ensure_ascii=False),
            master.get('voucher_number'),
            master.get('voucher_date'),
            master.get('supplier_name'),
            master.get('vendor_details'),
            master.get('gross_total'),
            master.get('total_deductions'),
            master.get('net_total'),
            ocr_mode
        ))
        
        voucher_id = cur.fetchone()['id']
        
        # Insert Items and Deductions
        VoucherService._insert_items_deductions(cur, voucher_id, parsed_data.get('items', []), parsed_data.get('deductions', []))
        
        conn.commit()
        return voucher_id

    @staticmethod
    def update_voucher_parse_data(voucher_id, raw_text, parsed_data, ocr_mode='default'):
        conn = get_connection()
        cur = conn.cursor()
        
        master = parsed_data.get('master', {})
        
        cur.execute("""
            UPDATE vouchers_master
            SET raw_ocr_text = %s,
                parsed_json = %s,
                ocr_mode = %s,
                supplier_name = %s,
                vendor_details = %s,
                voucher_number = %s,
                voucher_date = %s,
                gross_total = %s,
                net_total = %s,
                total_deductions = %s,
                validation_status = 'PARSED'
            WHERE id = %s
        """, (
            raw_text,
            json.dumps(parsed_data, ensure_ascii=False),
            ocr_mode,
            master.get('supplier_name'),
            master.get('vendor_details'),
            master.get('voucher_number'),
            master.get('voucher_date'),
            master.get('gross_total'),
            master.get('net_total'),
            master.get('total_deductions'),
            voucher_id
        ))
        
        # Replace items/deductions
        cur.execute("DELETE FROM voucher_items WHERE master_id = %s", (voucher_id,))
        cur.execute("DELETE FROM voucher_deductions WHERE master_id = %s", (voucher_id,))
        
        VoucherService._insert_items_deductions(cur, voucher_id, parsed_data.get('items', []), parsed_data.get('deductions', []))
        
        conn.commit()

    @staticmethod
    def save_validated_voucher(voucher_id, master_data, items, deductions):
        conn = get_connection()
        cur = conn.cursor()
        
        # Get the original parsed_json first (for ML learning)
        cur.execute(
            "SELECT parsed_json, parsed_json_original FROM vouchers_master WHERE id = %s",
            (voucher_id,)
        )
        result = cur.fetchone()
        original_parsed_json = result['parsed_json_original'] if result else None
        current_parsed_json = result['parsed_json'] if result else None
        
        # If we don't have original yet, use current as original (first time saving)
        if not original_parsed_json and current_parsed_json:
            original_parsed_json = current_parsed_json
        
        # Construct final parsed json with corrections
        final_parsed_json = {
            'master': master_data,
            'items': items,
            'deductions': deductions
        }
        
        cur.execute("""
            UPDATE vouchers_master
            SET 
                supplier_name = %s,
                voucher_date = %s,
                voucher_number = %s,
                gross_total = %s,
                total_deductions = %s,
                net_total = %s,
                parsed_json = %s,
                parsed_json_original = %s,
                validation_status = 'VALIDATED'
            WHERE id = %s
        """, (
            master_data.get('supplier_name'),
            master_data.get('voucher_date'),
            master_data.get('voucher_number'),
            master_data.get('gross_total'),
            master_data.get('total_deductions'),
            master_data.get('net_total'),
            json.dumps(final_parsed_json, ensure_ascii=False),
            json.dumps(original_parsed_json, ensure_ascii=False) if original_parsed_json else None,
            voucher_id
        ))
        
        # Replace items/deductions
        cur.execute("DELETE FROM voucher_items WHERE master_id = %s", (voucher_id,))
        cur.execute("DELETE FROM voucher_deductions WHERE master_id = %s", (voucher_id,))
        
        VoucherService._insert_items_deductions(cur, voucher_id, items, deductions)
        
        conn.commit()

    @staticmethod
    def delete_all_vouchers():
        conn = get_connection()
        cur = conn.cursor()
        
        # Delete production data first (to satisfy FK constraints)
        cur.execute("DELETE FROM receipts")
        cur.execute("DELETE FROM suppliers")
        
        # Delete all tables (beta tables were migrated to production)
        cur.execute("DELETE FROM voucher_items")
        cur.execute("DELETE FROM voucher_deductions")
        cur.execute("DELETE FROM ml_bounding_boxes")
        cur.execute("DELETE FROM vouchers_master")
        cur.execute("DELETE FROM batch_uploads")
        cur.execute("DELETE FROM file_lifecycle_meta")
        
        conn.commit()

    @staticmethod
    def _insert_items_deductions(cur, voucher_id, items, deductions):
        from psycopg2.extras import execute_values
        
        if items:
            item_values = [(
                voucher_id,
                item.get('item_name'),
                item.get('quantity'),
                item.get('unit_price'),
                item.get('line_amount')
            ) for item in items]
            
            execute_values(cur, """
                INSERT INTO voucher_items (master_id, item_name, quantity, unit_price, line_amount)
                VALUES %s
            """, item_values)
            
        if deductions:
            ded_values = [(
                voucher_id,
                ded.get('deduction_type'),
                ded.get('amount')
            ) for ded in deductions]
            
            execute_values(cur, """
                INSERT INTO voucher_deductions (master_id, deduction_type, amount)
                VALUES %s
            """, ded_values)
