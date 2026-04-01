"""
User satisfaction feedback service
Supports rating, feedback collection, satisfaction statistics
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, func
from sqlalchemy.orm import Session
import logging
import uuid

from app.services.metadata import Base, metadata_service

logger = logging.getLogger(__name__)


# ==================== Data Models ====================

class Feedback(Base):
    """User feedback table"""
    __tablename__ = "feedbacks"

    id = Column(String(100), primary_key=True)
    query = Column(String(500), nullable=False)
    answer = Column(Text, nullable=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(100), nullable=True)
    rating = Column(Integer, nullable=False)  # 1-5 star rating
    comment = Column(Text, nullable=True)  # User comment
    helpful = Column(Boolean, default=None)  # Whether helpful
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== Feedback Service ====================

class FeedbackService:
    """User feedback service (supports multi-tenant)"""

    def __init__(self):
        """Initialize feedback service, reuse metadata service database connection"""
        self.engine = metadata_service.engine
        self.SessionLocal = metadata_service.SessionLocal

    def get_db(self) -> Optional[Session]:
        """Get database session"""
        if not self.SessionLocal:
            return None
        return self.SessionLocal()

    def _get_tenant_id(self, tenant_id: str = None) -> str:
        """Get tenant ID, prioritize passed parameter, then context"""
        if tenant_id:
            return tenant_id

        # Try to get from context
        from app.services.tenant import get_tenant_id
        ctx_tenant_id = get_tenant_id()
        if ctx_tenant_id:
            return ctx_tenant_id

        # Default tenant
        return "default"

    def create_feedback(
        self,
        feedback_id: str,
        query: str,
        rating: int,
        tenant_id: str = None,
        answer: str = None,
        user_id: str = None,
        comment: str = None,
        helpful: bool = None
    ) -> bool:
        """Create feedback record (supports multi-tenant)"""
        db = self.get_db()
        if not db:
            return False

        # Get tenant ID
        tenant_id = self._get_tenant_id(tenant_id)

        try:
            feedback = Feedback(
                id=feedback_id,
                query=query,
                rating=rating,
                tenant_id=tenant_id,
                answer=answer,
                user_id=user_id,
                comment=comment,
                helpful=helpful
            )
            db.add(feedback)
            db.commit()
            logger.info(f"Created feedback record: {feedback_id} (tenant: {tenant_id}, rating: {rating})")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create feedback record: {e}")
            return False
        finally:
            db.close()

    def get_feedback(self, feedback_id: str, tenant_id: str = None) -> Optional[Dict[str, Any]]:
        """Get feedback information (supports multi-tenant)"""
        db = self.get_db()
        if not db:
            return None

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            feedback = db.query(Feedback).filter(
                Feedback.id == feedback_id,
                Feedback.tenant_id == tenant_id
            ).first()
            if feedback:
                return {
                    "id": feedback.id,
                    "query": feedback.query,
                    "answer": feedback.answer,
                    "tenant_id": feedback.tenant_id,
                    "user_id": feedback.user_id,
                    "rating": feedback.rating,
                    "comment": feedback.comment,
                    "helpful": feedback.helpful,
                    "created_at": feedback.created_at.isoformat() if feedback.created_at else None
                }
            return None
        finally:
            db.close()

    def list_feedback(
        self,
        tenant_id: str = None,
        min_rating: int = None,
        max_rating: int = None,
        user_id: str = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        List feedback (supports multi-tenant, pagination and filtering)

        Args:
            tenant_id: Tenant ID
            min_rating: Minimum rating
            max_rating: Maximum rating
            user_id: User ID
            page: Page number (starting from 1)
            page_size: Items per page

        Returns:
            {
                "items": [...],
                "total": Total count,
                "page": Current page,
                "page_size": Items per page,
                "total_pages": Total pages
            }
        """
        db = self.get_db()
        if not db:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            query = db.query(Feedback).filter(Feedback.tenant_id == tenant_id)

            # Filter conditions
            if min_rating is not None:
                query = query.filter(Feedback.rating >= min_rating)
            if max_rating is not None:
                query = query.filter(Feedback.rating <= max_rating)
            if user_id:
                query = query.filter(Feedback.user_id == user_id)

            # Get total count
            total = query.count()

            # Calculate pagination
            skip = (page - 1) * page_size

            # Query
            feedbacks = query.order_by(Feedback.created_at.desc()).offset(skip).limit(page_size).all()

            total_pages = (total + page_size - 1) // page_size if total > 0 else 0

            return {
                "items": [
                    {
                        "id": fb.id,
                        "query": fb.query,
                        "answer": fb.answer,
                        "user_id": fb.user_id,
                        "rating": fb.rating,
                        "comment": fb.comment,
                        "helpful": fb.helpful,
                        "created_at": fb.created_at.isoformat() if fb.created_at else None
                    }
                    for fb in feedbacks
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
        finally:
            db.close()

    def get_feedback_stats(self, tenant_id: str = None, days: int = 7) -> Dict[str, Any]:
        """
        Get satisfaction statistics

        Args:
            tenant_id: Tenant ID
            days: Statistics days

        Returns:
            {
                "total_feedback": int,
                "avg_rating": float,  # Average satisfaction = Σ(rating * count) / total feedback count
                "satisfaction_rate": float,  # Satisfaction rate = (4 stars and above / total) * 100
                "rating_distribution": {1: N, 2: N, 3: N, 4: N, 5: N},
                "helpful_count": int,
                "not_helpful_count": int
            }
        """
        db = self.get_db()
        if not db:
            return {
                "total_feedback": 0,
                "avg_rating": 0.0,
                "satisfaction_rate": 0.0,
                "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                "helpful_count": 0,
                "not_helpful_count": 0
            }

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Query feedback within specified time range
            feedbacks = db.query(Feedback).filter(
                Feedback.tenant_id == tenant_id,
                Feedback.created_at >= cutoff_date
            ).all()

            if not feedbacks:
                return {
                    "total_feedback": 0,
                    "avg_rating": 0.0,
                    "satisfaction_rate": 0.0,
                    "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
                    "helpful_count": 0,
                    "not_helpful_count": 0
                }

            total_feedback = len(feedbacks)

            # Calculate average rating
            avg_rating = sum(fb.rating for fb in feedbacks) / total_feedback

            # Calculate satisfaction rate (4 stars and above)
            satisfied_count = sum(1 for fb in feedbacks if fb.rating >= 4)
            satisfaction_rate = (satisfied_count / total_feedback) * 100

            # Rating distribution
            rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for fb in feedbacks:
                rating_distribution[fb.rating] = rating_distribution.get(fb.rating, 0) + 1

            # helpful/not_helpful statistics
            helpful_count = sum(1 for fb in feedbacks if fb.helpful is True)
            not_helpful_count = sum(1 for fb in feedbacks if fb.helpful is False)

            return {
                "total_feedback": total_feedback,
                "avg_rating": round(avg_rating, 2),
                "satisfaction_rate": round(satisfaction_rate, 2),
                "rating_distribution": rating_distribution,
                "helpful_count": helpful_count,
                "not_helpful_count": not_helpful_count
            }
        finally:
            db.close()

    def get_low_rating_feedback(
        self,
        tenant_id: str = None,
        max_rating: int = 2,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Get low-rating feedback list

        Args:
            tenant_id: Tenant ID
            max_rating: Maximum rating (default 2, i.e., 1-2 stars)
            page: Page number
            page_size: Items per page

        Returns:
            Paginated feedback list
        """
        return self.list_feedback(
            tenant_id=tenant_id,
            max_rating=max_rating,
            page=page,
            page_size=page_size
        )

    def get_feedback_trend(self, tenant_id: str = None, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get satisfaction trend

        Args:
            tenant_id: Tenant ID
            days: Statistics days

        Returns:
            [{"date": "YYYY-MM-DD", "avg_rating": float, "count": int}, ...]
        """
        db = self.get_db()
        if not db:
            return []

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Group statistics by date
            result = db.query(
                func.date(Feedback.created_at).label('date'),
                func.avg(Feedback.rating).label('avg_rating'),
                func.count(Feedback.id).label('count')
            ).filter(
                Feedback.tenant_id == tenant_id,
                Feedback.created_at >= cutoff_date
            ).group_by(
                func.date(Feedback.created_at)
            ).order_by(
                func.date(Feedback.created_at).asc()
            ).all()

            return [
                {
                    "date": str(row.date),
                    "avg_rating": round(float(row.avg_rating), 2) if row.avg_rating else 0.0,
                    "count": row.count
                }
                for row in result
            ]
        finally:
            db.close()


# Singleton
feedback_service = FeedbackService()
