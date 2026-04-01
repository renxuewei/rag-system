"""
Answer cache service
Supports answer cache with feedback-based weights, similarity search, weight updates
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Float
from sqlalchemy.orm import Session
import logging
import uuid
import json
import hashlib
import math

from app.services.metadata import Base, metadata_service
from app.services.embeddings import embedding_service

logger = logging.getLogger(__name__)


class AnswerCache(Base):
    """Answer cache table"""
    __tablename__ = "answer_cache"

    id = Column(String(100), primary_key=True)
    query_text = Column(String(500), nullable=False)
    answer = Column(Text, nullable=False)
    query_embedding = Column(Text, nullable=False)
    helpful_count = Column(Integer, default=0)
    unhelpful_count = Column(Integer, default=0)
    weight = Column(Float, default=0.0)
    hit_count = Column(Integer, default=0)
    tenant_id = Column(String(100), nullable=False, default="default", index=True)
    source_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AnswerCacheService:
    """Answer cache service (supports multi-tenant)"""

    def __init__(self):
        self.engine = metadata_service.engine
        self.SessionLocal = metadata_service.SessionLocal

    def get_db(self) -> Optional[Session]:
        if not self.SessionLocal:
            return None
        return self.SessionLocal()

    def _get_tenant_id(self, tenant_id: str = None) -> str:
        if tenant_id:
            return tenant_id

        from app.services.tenant import get_tenant_id
        ctx_tenant_id = get_tenant_id()
        if ctx_tenant_id:
            return ctx_tenant_id

        return "default"

    def _cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        if not vec_a or not vec_b:
            return 0.0

        if len(vec_a) != len(vec_b):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def upsert_cache(self, query: str, answer: str, tenant_id: str = None) -> bool:
        db = self.get_db()
        if not db:
            return False

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            query_embedding = embedding_service.embed_query(query)
            embedding_json = json.dumps(query_embedding)
            source_hash_input = query + answer
            source_hash = hashlib.md5(source_hash_input.encode('utf-8')).hexdigest()

            existing = db.query(AnswerCache).filter(
                AnswerCache.source_hash == source_hash,
                AnswerCache.tenant_id == tenant_id
            ).first()

            if existing:
                return True

            cache_entry = AnswerCache(
                id=str(uuid.uuid4()),
                query_text=query,
                answer=answer,
                query_embedding=embedding_json,
                helpful_count=0,
                unhelpful_count=0,
                weight=0.0,
                hit_count=0,
                tenant_id=tenant_id,
                source_hash=source_hash
            )
            db.add(cache_entry)
            db.commit()
            logger.info(f"Created answer cache: {cache_entry.id} (tenant: {tenant_id})")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create answer cache: {e}")
            return False
        finally:
            db.close()

    def update_feedback_weight(self, query: str, answer: str, helpful: bool, tenant_id: str = None) -> bool:
        tenant_id = self._get_tenant_id(tenant_id)

        try:
            cache_entry = db.query(AnswerCache).filter(
                AnswerCache.query_text.ilike(query),
                AnswerCache.answer == answer,
                AnswerCache.tenant_id == tenant_id
            ).first()

            if cache_entry:
                if helpful:
                    cache_entry.helpful_count += 1
                else:
                    cache_entry.unhelpful_count += 1

                cache_entry.weight = cache_entry.helpful_count - cache_entry.unhelpful_count
                db.commit()
                logger.info(f"Updated feedback weight: {cache_entry.id} (weight: {cache_entry.weight})")
                return True
            else:
                return self.upsert_cache(query, answer, tenant_id)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update feedback weight: {e}")
            return False
        finally:
            db.close()

    def search_cache(
        self,
        query: str,
        tenant_id: str = None,
        top_k: int = 3,
        min_weight: int = 1,
        similarity_threshold: float = 0.92
    ) -> Optional[Dict[str, Any]]:
        db = self.get_db()
        if not db:
            return None

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            query_embedding = embedding_service.embed_query(query)

            cache_entries = db.query(AnswerCache).filter(
                AnswerCache.tenant_id == tenant_id,
                AnswerCache.weight >= min_weight
            ).all()

            candidates = []
            for entry in cache_entries:
                embedding_str = str(entry.query_embedding)
                cached_embedding = json.loads(embedding_str)
                similarity = self._cosine_similarity(query_embedding, cached_embedding)

                if similarity >= similarity_threshold:
                    weight_factor = 1 + (entry.weight * 0.1)
                    score = similarity * weight_factor
                    candidates.append((score, entry))

            if not candidates:
                return None

            candidates.sort(key=lambda x: x[0], reverse=True)
            best_entry = candidates[0][1]

            best_entry.hit_count += 1
            db.commit()

            return {
                "answer": best_entry.answer,
                "similarity": candidates[0][0] / (1 + best_entry.weight * 0.1),
                "weight": best_entry.weight,
                "id": best_entry.id
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to search answer cache: {e}")
            return None
        finally:
            db.close()

    def get_top_cached_answers(self, tenant_id: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        db = self.get_db()
        if not db:
            return []

        tenant_id = self._get_tenant_id(tenant_id)

        try:
            entries = db.query(AnswerCache).filter(
                AnswerCache.tenant_id == tenant_id
            ).order_by(AnswerCache.weight.desc()).limit(limit).all()

            return [
                {
                    "id": entry.id,
                    "query_text": entry.query_text,
                    "answer": entry.answer,
                    "helpful_count": entry.helpful_count,
                    "unhelpful_count": entry.unhelpful_count,
                    "weight": entry.weight,
                    "hit_count": entry.hit_count,
                    "created_at": entry.created_at.isoformat() if entry.created_at is not None else None
                }
                for entry in entries
            ]
        finally:
            db.close()


answer_cache_service = AnswerCacheService()
