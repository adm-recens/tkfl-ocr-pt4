
from backend.db import get_connection
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

class BatchService:
    """Service for managing bulk upload batches"""
    
    @staticmethod
    def create_batch(batch_name=None, total_files=0, created_by='user'):
        """
        Create a new batch record
        Returns: batch_id (str)
        """
        conn = get_connection()
        cur = conn.cursor()
        
        batch_id = str(uuid.uuid4())
        if not batch_name:
            batch_name = f"Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
        try:
            cur.execute("""
                INSERT INTO batch_uploads 
                (batch_id, batch_name, total_files, created_by, status)
                VALUES (%s, %s, %s, %s, 'processing')
                RETURNING id
            """, (batch_id, batch_name, total_files, created_by))
            
            conn.commit()
            logger.info(f"Created batch {batch_id}: {batch_name}")
            return batch_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error creating batch: {e}")
            raise e
            
    @staticmethod
    def update_batch_stats(batch_id, success_count=0, failure_count=0, skipped_count=0):
        """
        Update file counts for a batch
        """
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            updates = []
            params = []
            
            # Aggregate the total processed count
            total_processed = success_count + failure_count + skipped_count
            
            if success_count > 0:
                updates.append("validated_files = validated_files + %s")
                params.append(success_count)
                
            if failure_count > 0:
                updates.append("failed_files = failed_files + %s")
                params.append(failure_count)
                
            if skipped_count > 0:
                updates.append("skipped_files = skipped_files + %s")
                params.append(skipped_count)
            
            if total_processed > 0:
                updates.append("processed_files = processed_files + %s")
                params.append(total_processed)
                
            if not updates:
                return
                
            query = f"UPDATE batch_uploads SET {', '.join(updates)} WHERE batch_id = %s"
            params.append(batch_id)
            
            cur.execute(query, tuple(params))
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating batch stats: {e}")
            
    @staticmethod
    def complete_batch(batch_id):
        """
        Mark batch as completed
        """
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                UPDATE batch_uploads 
                SET status = CASE 
                    WHEN failed_files > 0 THEN 'partial_failure'
                    ELSE 'completed'
                END, 
                completed_at = CURRENT_TIMESTAMP
                WHERE batch_id = %s
            """, (batch_id,))
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error completing batch: {e}")
            raise e

        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM batch_uploads WHERE batch_id = %s", (batch_id,))
        return cur.fetchone()

    @staticmethod
    def get_batch_with_vouchers(batch_id):
        """
        Get batch details with all associated vouchers
        """
        conn = get_connection()
        cur = conn.cursor()
        
        # Get batch info
        cur.execute("SELECT * FROM batch_uploads WHERE batch_id = %s", (batch_id,))
        batch = cur.fetchone()
        
        if not batch:
            return None
            
        # Get associated vouchers
        cur.execute("""
            SELECT * FROM vouchers_master 
            WHERE batch_id = %s 
            ORDER BY created_at ASC
        """, (batch_id,))
        
        batch['vouchers'] = cur.fetchall()
        
        return batch

    @staticmethod
    def get_all_batches(limit=20, offset=0):
        """
        Get paginated list of batches
        """
        conn = get_connection()
        cur = conn.cursor()
        
        # Get total count
        cur.execute("SELECT COUNT(*) as count FROM batch_uploads")
        total = cur.fetchone()['count']
        
        # Get batches
        cur.execute("""
            SELECT * FROM batch_uploads 
            ORDER BY created_at DESC 
            LIMIT %s OFFSET %s
        """, (limit, offset))
        
        batches = cur.fetchall()
        
        return {
            'batches': batches,
            'total': total,
            'limit': limit,
            'offset': offset
        }
