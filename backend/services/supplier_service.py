from backend.db import get_connection

class SupplierService:
    @staticmethod
    def get_all_suppliers():
        conn = get_connection()
        try:
            cur = conn.cursor()
            # Get suppliers with receipt stats
            cur.execute("""
                SELECT 
                    s.*,
                    COUNT(r.id) as receipt_count,
                    COALESCE(SUM(r.net_total), 0) as total_spend
                FROM suppliers s
                LEFT JOIN receipts r ON s.id = r.supplier_id
                GROUP BY s.id
                ORDER BY total_spend DESC
            """)
            return cur.fetchall()
        finally:
            cur.close()

    @staticmethod
    def get_supplier_by_id(supplier_id):
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM suppliers WHERE id = %s", (supplier_id,))
            return cur.fetchone()
        finally:
            cur.close()

    @staticmethod
    def get_supplier_receipts(supplier_id):
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT * 
                FROM receipts 
                WHERE supplier_id = %s 
                ORDER BY receipt_date DESC NULLS LAST, created_at DESC
            """, (supplier_id,))
            return cur.fetchall()
        finally:
            cur.close()
