"""
Beta Voucher Service - Handles database operations for beta tables
Complete isolation from production voucher_service.py
"""
from backend.db import get_connection
from flask import current_app
import json

class VoucherServiceBeta:
    """Service for beta voucher operations using separate beta tables"""
    
    @staticmethod
    def create_voucher(file_name, file_storage_path, raw_text, parsed_data, ocr_mode='beta_enhanced', 
                      preprocessing_method=None, ocr_confidence=None, processing_time_ms=None):
        """
        Create a new voucher in beta tables
        
        Returns:
            int: master_id of created voucher
        """
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            # Serialize parsed_data to JSON
            parsed_json = json.dumps(parsed_data) if isinstance(parsed_data, dict) else parsed_data
            
            # Extract master fields from parsed_data
            master = parsed_data.get('master', {}) if isinstance(parsed_data, dict) else {}
            
            # Insert into vouchers_master_beta
            cur.execute("""
                INSERT INTO vouchers_master_beta (
                    file_name, file_storage_path, raw_ocr_text, parsed_json, ocr_mode,
                    voucher_number, voucher_date, supplier_name, vendor_details,
                    gross_total, total_deductions, net_total,
                    preprocessing_method, ocr_confidence, processing_time_ms
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                file_name, file_storage_path, raw_text, parsed_json, ocr_mode,
                master.get('voucher_number'), master.get('voucher_date'),
                master.get('supplier_name'), master.get('vendor_details'),
                master.get('gross_total'), master.get('total_deductions'), master.get('net_total'),
                preprocessing_method, ocr_confidence, processing_time_ms
            ))
            
            master_id = cur.fetchone()['id']
            
            # Insert items
            items = parsed_data.get('items', []) if isinstance(parsed_data, dict) else []
            for item in items:
                cur.execute("""
                    INSERT INTO voucher_items_beta (master_id, item_name, quantity, unit_price, line_amount)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    master_id, item.get('item_name'), item.get('quantity'),
                    item.get('unit_price'), item.get('line_amount')
                ))
            
            # Insert deductions
            deductions = parsed_data.get('deductions', []) if isinstance(parsed_data, dict) else []
            for ded in deductions:
                cur.execute("""
                    INSERT INTO voucher_deductions_beta (master_id, deduction_type, amount)
                    VALUES (%s, %s, %s)
                """, (master_id, ded.get('deduction_type'), ded.get('amount')))
            
            conn.commit()
            return master_id
            
        except Exception as e:
            conn.rollback()
            current_app.logger.error(f"Error creating beta voucher: {e}")
            raise e
    
    @staticmethod
    def get_voucher_by_id(voucher_id):
        """Get voucher from beta tables by ID"""
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT * FROM vouchers_master_beta WHERE id = %s
        """, (voucher_id,))
        
        return cur.fetchone()
    
    @staticmethod
    def get_all_vouchers(page=1, per_page=20):
        """Get paginated list of beta vouchers"""
        conn = get_connection()
        cur = conn.cursor()
        
        offset = (page - 1) * per_page
        
        # Get total count
        cur.execute("SELECT COUNT(*) as count FROM vouchers_master_beta")
        total = cur.fetchone()['count']
        
        # Get paginated vouchers
        cur.execute("""
            SELECT * FROM vouchers_master_beta
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (per_page, offset))
        
        vouchers = cur.fetchall()
        
        return {
            'vouchers': vouchers,
            'current_page': page,
            'total_pages': (total + per_page - 1) // per_page,
            'total_vouchers': total
        }
    
    @staticmethod
    def get_voucher_items(voucher_id):
        """Get items for a beta voucher"""
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT * FROM voucher_items_beta WHERE master_id = %s
        """, (voucher_id,))
        
        return cur.fetchall()
    
    @staticmethod
    def get_voucher_deductions(voucher_id):
        """Get deductions for a beta voucher"""
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT * FROM voucher_deductions_beta WHERE master_id = %s
        """, (voucher_id,))
        
        return cur.fetchall()
    
    @staticmethod
    def update_voucher_parse_data(voucher_id, raw_text, parsed_data, ocr_mode, 
                                  preprocessing_method=None, ocr_confidence=None, processing_time_ms=None):
        """Update beta voucher with new OCR/parse results"""
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            parsed_json = json.dumps(parsed_data) if isinstance(parsed_data, dict) else parsed_data
            master = parsed_data.get('master', {}) if isinstance(parsed_data, dict) else {}
            
            # Update master table
            cur.execute("""
                UPDATE vouchers_master_beta SET
                    raw_ocr_text = %s,
                    parsed_json = %s,
                    ocr_mode = %s,
                    voucher_number = %s,
                    voucher_date = %s,
                    supplier_name = %s,
                    vendor_details = %s,
                    gross_total = %s,
                    total_deductions = %s,
                    net_total = %s,
                    preprocessing_method = %s,
                    ocr_confidence = %s,
                    processing_time_ms = %s
                WHERE id = %s
            """, (
                raw_text, parsed_json, ocr_mode,
                master.get('voucher_number'), master.get('voucher_date'),
                master.get('supplier_name'), master.get('vendor_details'),
                master.get('gross_total'), master.get('total_deductions'), master.get('net_total'),
                preprocessing_method, ocr_confidence, processing_time_ms,
                voucher_id
            ))
            
            # Delete and re-insert items
            cur.execute("DELETE FROM voucher_items_beta WHERE master_id = %s", (voucher_id,))
            items = parsed_data.get('items', []) if isinstance(parsed_data, dict) else []
            for item in items:
                cur.execute("""
                    INSERT INTO voucher_items_beta (master_id, item_name, quantity, unit_price, line_amount)
                    VALUES (%s, %s, %s, %s, %s)
                """, (voucher_id, item.get('item_name'), item.get('quantity'),
                     item.get('unit_price'), item.get('line_amount')))
            
            # Delete and re-insert deductions
            cur.execute("DELETE FROM voucher_deductions_beta WHERE master_id = %s", (voucher_id,))
            deductions = parsed_data.get('deductions', []) if isinstance(parsed_data, dict) else []
            for ded in deductions:
                cur.execute("""
                    INSERT INTO voucher_deductions_beta (master_id, deduction_type, amount)
                    VALUES (%s, %s, %s)
                """, (voucher_id, ded.get('deduction_type'), ded.get('amount')))
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            current_app.logger.error(f"Error updating beta voucher: {e}")
            raise e
