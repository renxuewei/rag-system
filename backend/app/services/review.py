"""
Review workflow service
Supports document review, review task management
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Index
from sqlalchemy.orm import Session
import logging

from app.services.metadata import Base, metadata_service

logger = logging.getLogger(__name__)


# ==================== Data Models ====================

class Review(Base):
    """Review record table"""
    __tablename__ = "reviews"

    id = Column(String(100), primary_key=True)
    document_id = Column(String(100), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    reviewer_id = Column(String(100), nullable=False)
    status = Column(String(50), default="pending")  # pending/approved/rejected
    comment = Column(Text)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Composite index: tenant + status
    __table_args__ = (
        Index('ix_reviews_tenant_status', 'tenant_id', 'status'),
    )


class ReviewTask(Base):
    """Review task table"""
    __tablename__ = "review_tasks"

    task_id = Column(String(100), primary_key=True)
    document_id = Column(String(100), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    assigned_to = Column(String(100))  # Reviewer
    status = Column(String(50), default="pending")  # pending/in_review/approved/rejected
    deadline = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Composite indexes
    __table_args__ = (
        Index('ix_review_tasks_tenant_status', 'tenant_id', 'status'),
        Index('ix_review_tasks_assigned_status', 'assigned_to', 'status'),
    )


# ==================== Review Service ====================

class ReviewService:
    """Review workflow management service (multi-tenant support)"""

    def __init__(self):
        # Reuse metadata_service's engine — do NOT create new engine
        self.engine = metadata_service.engine
        self.SessionLocal = metadata_service.SessionLocal

    def get_db(self) -> Optional[Session]:
        """Get database session"""
        if not self.SessionLocal:
            return None
        return self.SessionLocal()

    def _get_tenant_id(self, tenant_id: str = None) -> str:
        """Get tenant ID, prefer passed parameter, then use context"""
        if tenant_id:
            return tenant_id

        # Try to get from context
        from app.services.tenant import get_tenant_id
        ctx_tenant_id = get_tenant_id()
        if ctx_tenant_id:
            return ctx_tenant_id

        # Default tenant
        return "default"

    # ==================== Review Record Operations ====================

    def create_review(
        self,
        review_id: str,
        document_id: str,
        reviewer_id: str,
        tenant_id: str = None,
        comment: str = None
    ) -> bool:
        """Create review record"""
        db = self.get_db()
        if not db:
            return False

        # Get tenant ID
        tenant_id = self._get_tenant_id(tenant_id)

        try:
            review = Review(
                id=review_id,
                document_id=document_id,
                tenant_id=tenant_id,
                reviewer_id=reviewer_id,
                comment=comment,
                status="pending"
            )
            db.add(review)
            db.commit()
            logger.info(f"Review record created: {review_id} (tenant: {tenant_id}, document: {document_id})")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create review record: {e}")
            return False
        finally:
            db.close()

    def get_review(self, review_id: str, tenant_id: str = None) -> Optional[Dict[str, Any]]:
        """Get review record"""
        db = self.get_db()
        if not db:
            return None

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            review = db.query(Review).filter(
                Review.id == review_id,
                Review.tenant_id == tenant_id
            ).first()
            if review:
                return {
                    "id": review.id,
                    "document_id": review.document_id,
                    "tenant_id": review.tenant_id,
                    "reviewer_id": review.reviewer_id,
                    "status": review.status,
                    "comment": review.comment,
                    "reviewed_at": review.reviewed_at.isoformat() if review.reviewed_at else None,
                    "created_at": review.created_at.isoformat() if review.created_at else None
                }
            return None
        finally:
            db.close()

    def update_review(
        self,
        review_id: str,
        status: str,
        comment: str = None,
        tenant_id: str = None
    ) -> bool:
        """Update review status"""
        db = self.get_db()
        if not db:
            return False

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            review = db.query(Review).filter(
                Review.id == review_id,
                Review.tenant_id == tenant_id
            ).first()
            if review:
                review.status = status
                if comment is not None:
                    review.comment = comment
                # Set review time
                if status in ["approved", "rejected"]:
                    review.reviewed_at = datetime.utcnow()
                db.commit()
                logger.info(f"Review record updated: {review_id}, status: {status}")
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update review record: {e}")
            return False
        finally:
            db.close()

    def list_reviews(
        self,
        document_id: str = None,
        status: str = None,
        tenant_id: str = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """List review records (multi-tenant and pagination support)"""
        db = self.get_db()
        if not db:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            query = db.query(Review).filter(Review.tenant_id == tenant_id)
            if document_id:
                query = query.filter(Review.document_id == document_id)
            if status:
                query = query.filter(Review.status == status)

            # Get total count
            total = query.count()

            # Calculate pagination
            skip = (page - 1) * page_size

            # Query
            reviews = query.order_by(Review.created_at.desc()).offset(skip).limit(page_size).all()

            total_pages = (total + page_size - 1) // page_size if total > 0 else 0

            return {
                "items": [
                    {
                        "id": review.id,
                        "document_id": review.document_id,
                        "tenant_id": review.tenant_id,
                        "reviewer_id": review.reviewer_id,
                        "status": review.status,
                        "comment": review.comment,
                        "reviewed_at": review.reviewed_at.isoformat() if review.reviewed_at else None,
                        "created_at": review.created_at.isoformat() if review.created_at else None
                    }
                    for review in reviews
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
        finally:
            db.close()

    # ==================== Review Task Operations ====================

    def create_review_task(
        self,
        task_id: str,
        document_id: str,
        assigned_to: str,
        tenant_id: str = None,
        deadline: datetime = None
    ) -> bool:
        """Create review task"""
        db = self.get_db()
        if not db:
            return False

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            task = ReviewTask(
                task_id=task_id,
                document_id=document_id,
                tenant_id=tenant_id,
                assigned_to=assigned_to,
                deadline=deadline,
                status="pending"
            )
            db.add(task)
            db.commit()
            logger.info(f"Review task created: {task_id} (tenant: {tenant_id}, document: {document_id})")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create review task: {e}")
            return False
        finally:
            db.close()

    def get_review_task(self, task_id: str, tenant_id: str = None) -> Optional[Dict[str, Any]]:
        """Get review task"""
        db = self.get_db()
        if not db:
            return None

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            task = db.query(ReviewTask).filter(
                ReviewTask.task_id == task_id,
                ReviewTask.tenant_id == tenant_id
            ).first()
            if task:
                return {
                    "task_id": task.task_id,
                    "document_id": task.document_id,
                    "tenant_id": task.tenant_id,
                    "assigned_to": task.assigned_to,
                    "status": task.status,
                    "deadline": task.deadline.isoformat() if task.deadline else None,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "updated_at": task.updated_at.isoformat() if task.updated_at else None
                }
            return None
        finally:
            db.close()

    def list_review_tasks(
        self,
        status: str = None,
        assigned_to: str = None,
        tenant_id: str = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """List review tasks (multi-tenant and pagination support)"""
        db = self.get_db()
        if not db:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            query = db.query(ReviewTask).filter(ReviewTask.tenant_id == tenant_id)
            if status:
                query = query.filter(ReviewTask.status == status)
            if assigned_to:
                query = query.filter(ReviewTask.assigned_to == assigned_to)

            # Get total count
            total = query.count()

            # Calculate pagination
            skip = (page - 1) * page_size

            # Query
            tasks = query.order_by(ReviewTask.created_at.desc()).offset(skip).limit(page_size).all()

            total_pages = (total + page_size - 1) // page_size if total > 0 else 0

            return {
                "items": [
                    {
                        "task_id": task.task_id,
                        "document_id": task.document_id,
                        "tenant_id": task.tenant_id,
                        "assigned_to": task.assigned_to,
                        "status": task.status,
                        "deadline": task.deadline.isoformat() if task.deadline else None,
                        "created_at": task.created_at.isoformat() if task.created_at else None,
                        "updated_at": task.updated_at.isoformat() if task.updated_at else None
                    }
                    for task in tasks
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
        finally:
            db.close()

    # ==================== Batch Operations ====================

    def batch_review(
        self,
        review_ids: List[str],
        status: str,
        comment: str = None,
        tenant_id: str = None
    ) -> Dict[str, Any]:
        """Batch review"""
        db = self.get_db()
        if not db:
            return {"success_count": 0, "failed_count": len(review_ids)}

        tenant_id = self._get_tenant_id(tenant_id)

        success_count = 0
        failed_count = 0

        try:
            for review_id in review_ids:
                try:
                    review = db.query(Review).filter(
                        Review.id == review_id,
                        Review.tenant_id == tenant_id
                    ).first()
                    if review:
                        review.status = status
                        if comment is not None:
                            review.comment = comment
                        # Set review time
                        if status in ["approved", "rejected"]:
                            review.reviewed_at = datetime.utcnow()
                        success_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Batch review failed (review_id: {review_id}): {e}")
                    failed_count += 1

            db.commit()
            logger.info(f"Batch review completed: success {success_count}, failed {failed_count}")
            return {"success_count": success_count, "failed_count": failed_count}
        except Exception as e:
            db.rollback()
            logger.error(f"Batch review failed: {e}")
            return {"success_count": 0, "failed_count": len(review_ids)}
        finally:
            db.close()


# Singleton
review_service = ReviewService()
