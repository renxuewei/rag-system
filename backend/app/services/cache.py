"""
Cache service
Uses Redis to cache query results
"""

from typing import Optional, Any, Dict, List
import json
import hashlib
import redis
import logging

from app.config import config

logger = logging.getLogger(__name__)


class CacheService:
    """Cache service"""
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        password: str = None,
        ttl: int = None
    ):
        self.host = host or config.REDIS_HOST
        self.port = port or config.REDIS_PORT
        self.password = password or config.REDIS_PASSWORD
        self.ttl = ttl or config.CACHE_TTL
        
        self.client = None
        self._connect()
    
    def _connect(self):
        """Connect to Redis"""
        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password if self.password else None,
                decode_responses=True
            )
            # Test connection
            self.client.ping()
            logger.info(f"✅ Redis connection successful: {self.host}:{self.port}")
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {e}")
            self.client = None
    
    def _generate_key(self, prefix: str, content: str) -> str:
        """Generate cache key"""
        hash_value = hashlib.md5(content.encode()).hexdigest()
        return f"{prefix}:{hash_value}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get cache"""
        if not self.client:
            return None
        
        try:
            value = self.client.get(key)
            if value:
                logger.debug(f"Cache hit: {key}")
                return json.loads(value)
        except Exception as e:
            logger.error(f"Failed to get cache: {e}")
        
        return None
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set cache"""
        if not self.client:
            return False
        
        try:
            ttl = ttl or self.ttl
            self.client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
            logger.debug(f"Cache set: {key}, TTL: {ttl}s")
            return True
        except Exception as e:
            logger.error(f"Failed to set cache: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete cache"""
        if not self.client:
            return False
        
        try:
            self.client.delete(key)
            logger.debug(f"Cache deleted: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete cache: {e}")
            return False
    
    def get_query_cache(self, query: str, top_k: int = 5) -> Optional[List[Dict]]:
        """
        Get query result cache
        Args:
            query: Query text
            top_k: Retrieval count
        """
        key = self._generate_key("query", f"{query}:{top_k}")
        return self.get(key)
    
    def set_query_cache(
        self,
        query: str,
        top_k: int,
        results: List[Dict],
        ttl: int = None
    ) -> bool:
        """
        Set query result cache
        Args:
            query: Query text
            top_k: Retrieval count
            results: Retrieval results
            ttl: Cache time
        """
        key = self._generate_key("query", f"{query}:{top_k}")
        return self.set(key, results, ttl)
    
    def get_answer_cache(self, query: str, context_hash: str) -> Optional[str]:
        """
        Get answer cache
        Args:
            query: Query text
            context_hash: Context hash
        """
        key = self._generate_key("answer", f"{query}:{context_hash}")
        return self.get(key)
    
    def set_answer_cache(
        self,
        query: str,
        context_hash: str,
        answer: str,
        ttl: int = None
    ) -> bool:
        """
        Set answer cache
        Args:
            query: Query text
            context_hash: Context hash
            answer: Answer content
            ttl: Cache time
        """
        key = self._generate_key("answer", f"{query}:{context_hash}")
        return self.set(key, answer, ttl)
    
    def clear_pattern(self, pattern: str) -> int:
        """
        Clear cache matching pattern
        Args:
            pattern: Matching pattern (e.g., "query:*")
        """
        if not self.client:
            return 0
        
        try:
            keys = self.client.keys(pattern)
            if keys:
                count = self.client.delete(*keys)
                logger.info(f"Cleared cache: {count} entries")
                return count
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
        
        return 0
    
    def is_connected(self) -> bool:
        """Check connection status"""
        return self.client is not None


# Singleton
cache_service = CacheService()
