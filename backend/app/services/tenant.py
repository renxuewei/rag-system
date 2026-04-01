"""
Multi-tenant management service
Supports tenant isolation, tenant context management
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
import logging
import threading
from contextvars import ContextVar

from app.config import config

logger = logging.getLogger(__name__)

# Tenant context (thread-safe)
_tenant_context: ContextVar[Optional[str]] = ContextVar('tenant_context', default=None)


class TenantBase:
    """Base class for tenant-related data models"""
    tenant_id = Column(String(100), index=True, nullable=False)


def get_tenant_id() -> Optional[str]:
    """Get current tenant ID"""
    return _tenant_context.get()


def set_tenant_id(tenant_id: str) -> None:
    """Set current tenant ID"""
    _tenant_context.set(tenant_id)
    logger.debug(f"Set tenant context: {tenant_id}")


def clear_tenant_id() -> None:
    """Clear tenant context"""
    _tenant_context.set(None)


class TenantContext:
    """Tenant context manager"""
    
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self._previous_tenant_id = None
    
    def __enter__(self):
        self._previous_tenant_id = get_tenant_id()
        set_tenant_id(self.tenant_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._previous_tenant_id:
            set_tenant_id(self._previous_tenant_id)
        else:
            clear_tenant_id()
        return False


class TenantService:
    """Multi-tenant management service"""

    def __init__(self):
        # Tenant config cache
        self._tenant_cache: Dict[str, Dict[str, Any]] = {}

        # Default tenant config
        self._default_config = {
            "max_documents": 1000,
            "max_storage_mb": 1024,  # 1GB
            "max_queries_per_day": 10000,
            "features": {
                "hybrid_search": True,
                "rerank": True,
                "stream": True,
                "ingestion": False,  # Ingestion feature disabled by default
            }
        }
    
    def create_tenant(
        self,
        tenant_id: str,
        name: str,
        config_override: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create tenant

        Args:
            tenant_id: Tenant ID
            name: Tenant name
            config_override: Custom config

        Returns:
            Tenant info
        """
        if tenant_id in self._tenant_cache:
            raise ValueError(f"Tenant already exists: {tenant_id}")

        tenant_config = self._default_config.copy()
        if config_override:
            tenant_config.update(config_override)

        tenant_info = {
            "tenant_id": tenant_id,
            "name": name,
            "config": tenant_config,
            "created_at": datetime.utcnow().isoformat(),
            "is_active": True,
            "stats": {
                "document_count": 0,
                "storage_used_mb": 0,
                "queries_today": 0,
            }
        }

        self._tenant_cache[tenant_id] = tenant_info
        logger.info(f"Tenant created: {tenant_id} ({name})")

        return tenant_info

    def get_tenant(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant info"""
        return self._tenant_cache.get(tenant_id)

    def get_tenant_config(self, tenant_id: str) -> Dict[str, Any]:
        """Get tenant config"""
        tenant = self.get_tenant(tenant_id)
        if tenant:
            return tenant.get("config", self._default_config)
        return self._default_config
    
    def update_tenant_stats(
        self,
        tenant_id: str,
        document_delta: int = 0,
        storage_delta_mb: float = 0,
        query_delta: int = 0
    ) -> bool:
        """
        Update tenant stats

        Args:
            tenant_id: Tenant ID
            document_delta: Document count change
            storage_delta_mb: Storage change (MB)
            query_delta: Query count change

        Returns:
            Success status
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return False

        stats = tenant.get("stats", {})
        stats["document_count"] = max(0, stats.get("document_count", 0) + document_delta)
        stats["storage_used_mb"] = max(0, stats.get("storage_used_mb", 0) + storage_delta_mb)
        stats["queries_today"] = max(0, stats.get("queries_today", 0) + query_delta)

        tenant["stats"] = stats
        return True

    def check_quota(
        self,
        tenant_id: str,
        document_delta: int = 0,
        storage_delta_mb: float = 0,
        query_delta: int = 0
    ) -> tuple[bool, Optional[str]]:
        """
        Check tenant quota

        Args:
            tenant_id: Tenant ID
            document_delta: Document count change
            storage_delta_mb: Storage change (MB)
            query_delta: Query count change

        Returns:
            (Is allowed, Error message)
        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return False, "Tenant not found"

        if not tenant.get("is_active", True):
            return False, "Tenant is deactivated"

        config = tenant.get("config", self._default_config)
        stats = tenant.get("stats", {})

        # Check document count
        max_docs = config.get("max_documents", 1000)
        current_docs = stats.get("document_count", 0)
        if current_docs + document_delta > max_docs:
            return False, f"Document count exceeded: current {current_docs}/{max_docs}"

        # Check storage space
        max_storage = config.get("max_storage_mb", 1024)
        current_storage = stats.get("storage_used_mb", 0)
        if current_storage + storage_delta_mb > max_storage:
            return False, f"Storage space exceeded: current {current_storage:.1f}MB/{max_storage}MB"

        # Check query count
        max_queries = config.get("max_queries_per_day", 10000)
        current_queries = stats.get("queries_today", 0)
        if current_queries + query_delta > max_queries:
            return False, f"Query count exceeded: today {current_queries}/{max_queries}"

        return True, None
    
    def check_feature(self, tenant_id: str, feature_name: str) -> bool:
        """
        Check if tenant has a feature

        Args:
            tenant_id: Tenant ID
            feature_name: Feature name

        Returns:
            Is available
        """
        config = self.get_tenant_config(tenant_id)
        features = config.get("features", {})
        return features.get(feature_name, False)

    def list_tenants(self) -> List[Dict[str, Any]]:
        """List all tenants"""
        return list(self._tenant_cache.values())

    def deactivate_tenant(self, tenant_id: str) -> bool:
        """Deactivate tenant"""
        tenant = self.get_tenant(tenant_id)
        if tenant:
            tenant["is_active"] = False
            logger.info(f"Tenant deactivated: {tenant_id}")
            return True
        return False

    def activate_tenant(self, tenant_id: str) -> bool:
        """Activate tenant"""
        tenant = self.get_tenant(tenant_id)
        if tenant:
            tenant["is_active"] = True
            logger.info(f"Tenant activated: {tenant_id}")
            return True
        return False

    def get_tenant_partition_name(self, tenant_id: str) -> str:
        """
        Get tenant's Milvus Partition name

        Args:
            tenant_id: Tenant ID

        Returns:
            Partition name
        """
        # Replace special chars to ensure valid partition name
        safe_id = tenant_id.replace("-", "_").replace(".", "_")
        return f"tenant_{safe_id}"


# Singleton
tenant_service = TenantService()

# Initialize default tenant
tenant_service.create_tenant(
    tenant_id="default",
    name="Default tenant",
    config_override={
        "max_documents": 10000,
        "max_storage_mb": 10240,  # 10GB
        "max_queries_per_day": 100000,
        "features": {
            "hybrid_search": True,
            "rerank": True,
            "stream": True,
            "ingestion": True,
        }
    }
)
