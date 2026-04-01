"""
Data ingestion base class
Defines unified data ingestion interface
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncIterator
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class IngestionResult:
    """Ingestion result"""

    def __init__(
        self,
        source: str,
        content: str,
        metadata: Dict[str, Any] = None,
        success: bool = True,
        error: str = None
    ):
        self.source = source
        self.content = content
        self.metadata = metadata or {}
        self.success = success
        self.error = error
        self.ingested_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "content": self.content,
            "metadata": self.metadata,
            "success": self.success,
            "error": self.error,
            "ingested_at": self.ingested_at.isoformat()
        }


class BaseIngestion(ABC):
    """Data ingestion base class"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._is_running = False
        self._last_run: Optional[datetime] = None
        self._stats = {
            "total_ingested": 0,
            "total_failed": 0,
            "last_run": None
        }
    
    @abstractmethod
    def ingest(self, source: str, **kwargs) -> IngestionResult:
        """
        Synchronous data ingestion

        Args:
            source: Data source identifier
            **kwargs: Additional parameters

        Returns:
            Ingestion result
        """
        pass

    @abstractmethod
    async def ingest_async(self, source: str, **kwargs) -> IngestionResult:
        """
        Asynchronous data ingestion

        Args:
            source: Data source identifier
            **kwargs: Additional parameters

        Returns:
            Ingestion result
        """
        pass
    
    def ingest_batch(
        self,
        sources: List[str],
        **kwargs
    ) -> List[IngestionResult]:
        """
        Batch data ingestion (synchronous)

        Args:
            sources: Data source list
            **kwargs: Additional parameters

        Returns:
            Ingestion result list
        """
        results = []
        for source in sources:
            try:
                result = self.ingest(source, **kwargs)
                results.append(result)
                
                if result.success:
                    self._stats["total_ingested"] += 1
                else:
                    self._stats["total_failed"] += 1

            except Exception as e:
                logger.error(f"Ingestion failed: {source} - {e}")
                results.append(IngestionResult(
                    source=source,
                    content="",
                    success=False,
                    error=str(e)
                ))
                self._stats["total_failed"] += 1
        
        self._last_run = datetime.utcnow()
        self._stats["last_run"] = self._last_run.isoformat()
        
        return results
    
    async def ingest_batch_async(
        self,
        sources: List[str],
        **kwargs
    ) -> List[IngestionResult]:
        """
        Batch data ingestion (asynchronous)

        Args:
            sources: Data source list
            **kwargs: Additional parameters

        Returns:
            Ingestion result list
        """
        import asyncio
        
        tasks = [self.ingest_async(source, **kwargs) for source in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(IngestionResult(
                    source=sources[i],
                    content="",
                    success=False,
                    error=str(result)
                ))
                self._stats["total_failed"] += 1
            else:
                processed_results.append(result)
                if result.success:
                    self._stats["total_ingested"] += 1
                else:
                    self._stats["total_failed"] += 1
        
        self._last_run = datetime.utcnow()
        self._stats["last_run"] = self._last_run.isoformat()
        
        return processed_results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics"""
        return self._stats.copy()
    
    def validate_source(self, source: str) -> bool:
        """
        Validate data source

        Args:
            source: Data source identifier

        Returns:
            Whether valid
        """
        return bool(source)

    def normalize_content(self, content: str) -> str:
        """
        Normalize content

        Args:
            content: Original content

        Returns:
            Normalized content
        """
        if not content:
            return ""

        # Remove excess whitespace
        content = " ".join(content.split())

        return content.strip()
