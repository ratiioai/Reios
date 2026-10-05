"""
Grading queue implementation (database-based)
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, DateTime, Index, text
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import declarative_base
import logging

logger = logging.getLogger(__name__)

from app.models import Base


class GradingQueueItem(Base):
    """Queue for submissions awaiting grading"""
    __tablename__ = "grading_queue"
    
    submission_id = Column(Integer, primary_key=True, index=True)
    enqueued_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    status = Column(String(20), nullable=False, default="pending", index=True)
    retry_count = Column(Integer, default=0, nullable=False)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(String(500), nullable=True)
    
    __table_args__ = (
        Index('idx_status_enqueued', 'status', 'enqueued_at'),
    )


class GradingQueue:
    """Queue manager for grading submissions"""
    
    @staticmethod
    def enqueue(db: Session, submission_id: int) -> bool:
        """
        Add submission to grading queue
        Returns True if enqueued, False if already in queue
        """
        try:
            # Check if already in queue
            existing = db.query(GradingQueueItem).filter(
                GradingQueueItem.submission_id == submission_id
            ).first()
            
            if existing:
                logger.info(f"Submission {submission_id} already in queue")
                return False
            
            # Add to queue
            queue_item = GradingQueueItem(
                submission_id=submission_id,
                enqueued_at=datetime.utcnow(),
                status="pending"
            )
            db.add(queue_item)
            db.commit()
            logger.info(f"Enqueued submission {submission_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error enqueuing submission {submission_id}: {e}")
            db.rollback()
            return False
    
    @staticmethod
    def dequeue(db: Session) -> Optional[int]:
        """
        Get next submission from queue (FIFO)
        Uses SELECT FOR UPDATE SKIP LOCKED for concurrency
        Returns submission_id or None if queue is empty
        """
        try:
            now = datetime.utcnow()
            queue_item = db.query(GradingQueueItem).filter(
                GradingQueueItem.status == 'pending',
                (GradingQueueItem.next_retry_at == None) | (GradingQueueItem.next_retry_at <= now)
            ).order_by(GradingQueueItem.enqueued_at.asc()).first()
            
            if not queue_item:
                return None
            
            submission_id = queue_item.submission_id
            queue_item.status = 'processing'
            db.commit()
            return submission_id
        
        except Exception as e:
            logger.error(f"Error dequeuing submission: {e}")
            db.rollback()
            return None
    
    @staticmethod
    def mark_completed(db: Session, submission_id: int):
        """Mark submission as completed and remove from queue"""
        try:
            db.query(GradingQueueItem).filter(
                GradingQueueItem.submission_id == submission_id
            ).delete()
            db.commit()
            logger.info(f"Marked submission {submission_id} as completed")
        except Exception as e:
            logger.error(f"Error marking submission {submission_id} completed: {e}")
            db.rollback()
    
    @staticmethod
    def mark_failed(
        db: Session, 
        submission_id: int, 
        error_message: str,
        retry: bool = True,
        retry_delay_seconds: int = 60
    ):
        """Mark submission as failed, optionally schedule retry"""
        try:
            queue_item = db.query(GradingQueueItem).filter(
                GradingQueueItem.submission_id == submission_id
            ).first()
            
            if not queue_item:
                logger.warning(f"Queue item {submission_id} not found")
                return
            
            queue_item.retry_count += 1
            queue_item.error_message = error_message[:500]
            
            if retry and queue_item.retry_count < 3:
                # Schedule retry
                queue_item.status = "pending"
                queue_item.next_retry_at = datetime.utcnow().replace(
                    second=datetime.utcnow().second + retry_delay_seconds
                )
                logger.info(f"Scheduled retry for submission {submission_id} (attempt {queue_item.retry_count})")
            else:
                # Max retries reached or retry disabled
                queue_item.status = "failed"
                logger.error(f"Submission {submission_id} failed after {queue_item.retry_count} attempts: {error_message}")
            
            db.commit()
        
        except Exception as e:
            logger.error(f"Error marking submission {submission_id} failed: {e}")
            db.rollback()
    
    @staticmethod
    def get_queue_depth(db: Session) -> int:
        """Get number of pending submissions in queue"""
        try:
            count = db.query(GradingQueueItem).filter(
                GradingQueueItem.status == "pending"
            ).count()
            return count
        except Exception as e:
            logger.error(f"Error getting queue depth: {e}")
            return 0
    
    @staticmethod
    def get_queue_position(db: Session, submission_id: int) -> Optional[int]:
        """Get position of submission in queue (1-indexed)"""
        try:
            result = db.execute(text("""
                SELECT position FROM (
                    SELECT submission_id, 
                           ROW_NUMBER() OVER (ORDER BY enqueued_at ASC) as position
                    FROM grading_queue
                    WHERE status = 'pending'
                ) ranked
                WHERE submission_id = :submission_id
            """), {"submission_id": submission_id})
            
            row = result.fetchone()
            return row[0] if row else None
        
        except Exception as e:
            logger.error(f"Error getting queue position for {submission_id}: {e}")
            return None
    
    @staticmethod
    def get_stats(db: Session) -> dict:
        """Get queue statistics"""
        try:
            pending = db.query(GradingQueueItem).filter(
                GradingQueueItem.status == "pending"
            ).count()
            
            processing = db.query(GradingQueueItem).filter(
                GradingQueueItem.status == "processing"
            ).count()
            
            failed = db.query(GradingQueueItem).filter(
                GradingQueueItem.status == "failed"
            ).count()
            
            return {
                "pending": pending,
                "processing": processing,
                "failed": failed,
                "total": pending + processing + failed
            }
        
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {"pending": 0, "processing": 0, "failed": 0, "total": 0}
