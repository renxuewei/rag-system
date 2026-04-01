"""
Cache warmup module
Preloads frequently used queries into cache during system startup
"""

import logging
from typing import List, Optional
import asyncio
from datetime import datetime

from app.services.cache import cache_service
from app.services.vector_store import milvus_service
from app.config import config

logger = logging.getLogger(__name__)


class CacheWarmupService:
    """
    Cache warmup service
    Preloads frequently used queries into cache during system startup
    """

    # Common queries list (can be loaded from config or database)
    COMMON_QUERIES: List[str] = [
        "What is RAG?",
        "How to use the RAG system?",
        "What are the advantages of RAG?",
        "What are the application scenarios of RAG?",
        "How to upload documents to the RAG system?",
    ]

    def __init__(self):
        """Initialize cache warmup service"""
        self.enabled = config.CACHE_WARMUP_ENABLED
        self.queries = self.COMMON_QUERIES

    async def warmup_cache(self) -> dict:
        """
        Warm up cache

        Returns:
            Warmup result statistics
        """
        if not self.enabled:
            logger.info("Cache warmup disabled, skipping")
            return {"enabled": False, "queries_count": 0, "success_count": 0}

        logger.info("Starting cache warmup...")
        start_time = datetime.now()

        success_count = 0
        failed_count = 0
        results = []

        for query in self.queries:
            try:
                # Simulate query and cache result
                await self._warmup_query(query)
                success_count += 1
                results.append({"query": query, "status": "success"})
                logger.debug(f"Query warmup successful: {query}")
            except Exception as e:
                failed_count += 1
                results.append({"query": query, "status": "failed", "error": str(e)})
                logger.warning(f"Query warmup failed: {query}, error: {e}")

        elapsed_time = (datetime.now() - start_time).total_seconds()

        summary = {
            "enabled": True,
            "queries_count": len(self.queries),
            "success_count": success_count,
            "failed_count": failed_count,
            "elapsed_time": elapsed_time,
            "results": results
        }

        logger.info(
            f"Cache warmup complete: {success_count}/{len(self.queries)} successful, "
            f"took {elapsed_time:.2f} seconds"
        )

        return summary

    async def _warmup_query(self, query: str):
        """
        Warm up a single query

        Args:
            query: Query string
        """
        # Here should call actual query service
        # To avoid circular imports, this is just an example
        # from app.services.rag_service import rag_service
        # await rag_service.query(query, top_k=5)

        # Simulate cache operation
        cache_key = f"query:{hash(query)}"
        cache_service.set(cache_key, {"answer": "cached", "query": query}, ttl=3600)

    def add_query(self, query: str):
        """
        Add common query

        Args:
            query: Query string
        """
        if query not in self.queries:
            self.queries.append(query)
            logger.info(f"Added common query: {query}")


# Global cache warmup service instance
_cache_warmup_service: Optional[CacheWarmupService] = None


def get_cache_warmup_service() -> CacheWarmupService:
    """
    Get global cache warmup service instance

    Returns:
        CacheWarmupService instance
    """
    global _cache_warmup_service

    if _cache_warmup_service is None:
        _cache_warmup_service = CacheWarmupService()

    return _cache_warmup_service


async def warmup_cache_on_startup():
    """
    Warm up cache during system startup
    Usually called in FastAPI's startup event
    """
    service = get_cache_warmup_service()
    summary = await service.warmup_cache()

    # Log warmup statistics
    if summary["enabled"]:
        logger.info(
            f"Cache warmup statistics: "
            f"total_queries={summary['queries_count']}, "
            f"success={summary['success_count']}, "
            f"failed={summary['failed_count']}, "
            f"duration={summary['elapsed_time']:.2f}s"
        )
