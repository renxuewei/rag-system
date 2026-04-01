"""
API rate limiting middleware
Prevents API abuse and protects system resources
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from functools import wraps
from typing import Callable, Optional, Dict
import time
import asyncio
from collections import defaultdict
import hashlib
import ipaddress

from app.utils.metrics import REQUEST_COUNT


class RateLimiter:
    """
    Rate limiter
    Implements rate limiting using sliding window algorithm
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        cleanup_interval: int = 3600
    ):
        """
        Initialize rate limiter

        Args:
            requests_per_minute: Maximum requests per minute
            requests_per_hour: Maximum requests per hour
            cleanup_interval: Interval to clean up expired data (seconds)
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.cleanup_interval = cleanup_interval

        # Store request timestamps for each client
        self.requests: Dict[str, list] = defaultdict(list)

        # Start cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None

    def _get_client_key(self, request: Request) -> str:
        """
        Get unique client identifier

        Priority:
        1. API Key (if exists)
        2. X-Forwarded-For header
        3. X-Real-IP header
        4. Client IP

        Args:
            request: FastAPI request object

        Returns:
            Unique client identifier
        """
        # Try to get API Key from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
            if api_key:
                # Use API Key hash as identifier
                return hashlib.sha256(api_key.encode()).hexdigest()[:16]

        # Try to get real IP from proxy headers
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        if forwarded_for:
            # X-Forwarded-For may contain multiple IPs, take the first
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            real_ip = request.headers.get("X-Real-IP", "")
            if real_ip:
                client_ip = real_ip
            else:
                # Use client IP
                client_ip = request.client.host

        # Validate IP address format
        try:
            ipaddress.ip_address(client_ip)
        except ValueError:
            # Invalid IP address, use default value
            client_ip = "unknown"

        return client_ip

    def _cleanup_expired_requests(self):
        """
        Clean up expired request data
        """
        current_time = time.time()
        cutoff_time = current_time - self.cleanup_interval

        for key in list(self.requests.keys()):
            # Remove all requests earlier than cutoff time
            self.requests[key] = [
                timestamp for timestamp in self.requests[key]
                if timestamp > cutoff_time
            ]

            # If list is empty, remove the client
            if not self.requests[key]:
                del self.requests[key]

    def _is_rate_limited(self, client_key: str) -> tuple[bool, Optional[str]]:
        """
        Check if client is rate limited

        Args:
            client_key: Unique client identifier

        Returns:
            (Whether limited, Limit reason)
        """
        current_time = time.time()

        # Get request timestamps for this client
        request_times = self.requests[client_key]

        # Check per-minute limit
        minute_ago = current_time - 60
        requests_in_last_minute = sum(
            1 for timestamp in request_times
            if timestamp > minute_ago
        )

        if requests_in_last_minute >= self.requests_per_minute:
            return True, f"Rate limit exceeded: {requests_in_last_minute} requests per minute"

        # Check per-hour limit
        hour_ago = current_time - 3600
        requests_in_last_hour = sum(
            1 for timestamp in request_times
            if timestamp > hour_ago
        )

        if requests_in_last_hour >= self.requests_per_hour:
            return True, f"Rate limit exceeded: {requests_in_last_hour} requests per hour"

        # Not limited, record this request
        self.requests[client_key].append(current_time)

        return False, None

    async def check_rate_limit(self, request: Request) -> tuple[bool, Optional[str]]:
        """
        Check if request exceeds rate limit

        Args:
            request: FastAPI request object

        Returns:
            (Whether limited, Limit reason)
        """
        # Get client identifier
        client_key = self._get_client_key(request)

        # Check if limited
        is_limited, reason = self._is_rate_limited(client_key)

        return is_limited, reason


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """
    Get global rate limiter instance

    Returns:
        RateLimiter instance
    """
    global _rate_limiter

    if _rate_limiter is None:
        _rate_limiter = RateLimiter()

    return _rate_limiter


def init_rate_limiter(
    requests_per_minute: int = 60,
    requests_per_hour: int = 1000
):
    """
    Initialize global rate limiter

    Args:
        requests_per_minute: Maximum requests per minute
        requests_per_hour: Maximum requests per hour
    """
    global _rate_limiter
    _rate_limiter = RateLimiter(
        requests_per_minute=requests_per_minute,
        requests_per_hour=requests_per_hour
    )


def rate_limit(
    requests_per_minute: int = 60,
    requests_per_hour: int = 1000
):
    """
    Rate limiting decorator

    Args:
        requests_per_minute: Maximum requests per minute
        requests_per_hour: Maximum requests per hour

    Returns:
        Decorator function
    """
    limiter = RateLimiter(
        requests_per_minute=requests_per_minute,
        requests_per_hour=requests_per_hour
    )

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Check rate limit
            is_limited, reason = await limiter.check_rate_limit(request)

            if is_limited:
                # Log limited request
                REQUEST_COUNT.labels(
                    method=request.method,
                    endpoint=request.url.path,
                    status="429"
                ).inc()

                # Return 429 error
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=reason or "Rate limit exceeded. Please try again later."
                )

            # Execute original function
            return await func(request, *args, **kwargs)

        return wrapper

    return decorator


async def check_rate_limit_middleware(
    request: Request,
    call_next: Callable
):
    """
    Rate limiting middleware

    Args:
        request: FastAPI request object
        call_next: Next middleware or route handler

    Returns:
        Response object
    """
    # Get rate limiter
    limiter = get_rate_limiter()

    # Check rate limit
    is_limited, reason = await limiter.check_rate_limit(request)

    if is_limited:
        # Log limited request
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status="429"
        ).inc()

        # Return 429 error
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": reason or "Rate limit exceeded. Please try again later.",
                "retry_after": 60  # Suggest retry after 60 seconds
            },
            headers={
                "Retry-After": "60",
                "X-RateLimit-Limit": str(limiter.requests_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + 60)
            }
        )

    # Process request
    response = await call_next(request)

    # Add rate limit response headers
    client_key = limiter._get_client_key(request)
    current_time = time.time()
    minute_ago = current_time - 60

    request_times = limiter.requests[client_key]
    requests_in_last_minute = sum(
        1 for timestamp in request_times
        if timestamp > minute_ago
    )

    response.headers["X-RateLimit-Limit"] = str(limiter.requests_per_minute)
    response.headers["X-RateLimit-Remaining"] = str(
        max(0, limiter.requests_per_minute - requests_in_last_minute)
    )
    response.headers["X-RateLimit-Reset"] = str(int(current_time) + 60)

    return response
