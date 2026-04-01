"""
Prometheus monitoring metrics
"""

from prometheus_client import Counter, Histogram, Gauge, Info
import time
from functools import wraps

# ==================== Metric Definitions ====================

# Request counter
REQUEST_COUNT = Counter(
    'rag_request_total',
    'Total number of requests',
    ['method', 'endpoint', 'status']
)

# Request latency histogram
REQUEST_LATENCY = Histogram(
    'rag_request_latency_seconds',
    'Request latency in seconds',
    ['method', 'endpoint'],
    buckets=[0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 10.0]
)

# Query counter
QUERY_COUNT = Counter(
    'rag_query_total',
    'Total number of queries',
    ['cached', 'has_results']
)

# Document operations counter
DOCUMENT_OPS = Counter(
    'rag_document_operations_total',
    'Total number of document operations',
    ['operation', 'status']
)

# Vector store size
VECTOR_STORE_SIZE = Gauge(
    'rag_vector_store_size',
    'Number of vectors in the store'
)

# Cache hit rate
CACHE_HITS = Counter(
    'rag_cache_hits_total',
    'Total number of cache hits'
)
CACHE_MISSES = Counter(
    'rag_cache_misses_total',
    'Total number of cache misses'
)

# Active connections count
ACTIVE_CONNECTIONS = Gauge(
    'rag_active_connections',
    'Number of active connections'
)

# System information
SYSTEM_INFO = Info(
    'rag_system',
    'System information'
)
SYSTEM_INFO.info({
    'version': '1.0.0',
    'model': 'glm-4'
})


# ==================== Decorators ====================

def track_request(method: str, endpoint: str):
    """
    Track request metrics decorator
    Args:
        method: HTTP method
        endpoint: Endpoint name
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "200"
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "500"
                raise
            finally:
                # Record request
                REQUEST_COUNT.labels(
                    method=method,
                    endpoint=endpoint,
                    status=status
                ).inc()
                
                # Record latency
                latency = time.time() - start_time
                REQUEST_LATENCY.labels(
                    method=method,
                    endpoint=endpoint
                ).observe(latency)
        
        return wrapper
    return decorator


def track_query(func):
    """Track query metrics decorator"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        cached = kwargs.get('cached', False)
        has_results = False
        
        try:
            result = await func(*args, **kwargs)
            has_results = len(result) > 0 if result else False
            return result
        finally:
            QUERY_COUNT.labels(
                cached=str(cached).lower(),
                has_results=str(has_results).lower()
            ).inc()
    
    return wrapper


# ==================== Helper Functions ====================

def record_document_upload(success: bool):
    """Record document upload"""
    DOCUMENT_OPS.labels(
        operation='upload',
        status='success' if success else 'failed'
    ).inc()


def record_document_delete(success: bool):
    """Record document deletion"""
    DOCUMENT_OPS.labels(
        operation='delete',
        status='success' if success else 'failed'
    ).inc()


def record_cache_hit():
    """Record cache hit"""
    CACHE_HITS.inc()


def record_cache_miss():
    """Record cache miss"""
    CACHE_MISSES.inc()


def update_vector_store_size(size: int):
    """Update vector store size"""
    VECTOR_STORE_SIZE.set(size)


def increment_active_connections():
    """Increment active connections"""
    ACTIVE_CONNECTIONS.inc()


def decrement_active_connections():
    """Decrement active connections"""
    ACTIVE_CONNECTIONS.dec()
