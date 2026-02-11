"""Rate limiting middleware using in-memory storage with async-safe sliding window."""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Dict, NamedTuple

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.settings import settings

logger = logging.getLogger(__name__)


class RateLimitEntry(NamedTuple):
    """Immutable rate limit entry."""

    count: int
    window_start: float


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Async-safe in-memory rate limiting middleware with sliding window.

    Uses asyncio.Lock to avoid blocking the event loop.
    For production with multiple instances, consider Redis-backed rate limiting.
    """

    EXCLUDED_PATHS = frozenset({"/health", "/docs", "/redoc", "/openapi.json"})

    def __init__(self, app):
        super().__init__(app)
        self._requests: Dict[str, RateLimitEntry] = defaultdict(
            lambda: RateLimitEntry(0, time.time())
        )
        self._lock = asyncio.Lock()
        self._last_cleanup = time.time()

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP with X-Forwarded-For support for reverse proxies.

        Security: Only trust X-Forwarded-For from trusted hosts.
        """
        client_host = request.client.host if request.client else "unknown"

        # Check if request comes from trusted proxy
        if client_host in settings.trusted_hosts:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                # Take the first (original client) IP
                return forwarded.split(",")[0].strip()

        return client_host

    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting based on client IP with sliding window."""
        if not settings.rate_limit_enabled:
            return await call_next(request)

        # Skip rate limiting for excluded paths
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        current_time = time.time()
        client_ip = self._get_client_ip(request)

        # Async-safe rate limit check
        async with self._lock:
            # Periodic cleanup (every 5 minutes)
            if current_time - self._last_cleanup > 300:
                self._cleanup_expired(current_time)
                self._last_cleanup = current_time

            entry = self._requests[client_ip]

            # Reset if window expired (sliding window)
            if current_time - entry.window_start > settings.rate_limit_period:
                entry = RateLimitEntry(1, current_time)
            else:
                entry = RateLimitEntry(entry.count + 1, entry.window_start)

            self._requests[client_ip] = entry
            count = entry.count
            window_start = entry.window_start

        # Check if limit exceeded
        if count > settings.rate_limit_requests:
            retry_after = max(1, int(settings.rate_limit_period - (current_time - window_start)))
            logger.warning(
                f"Rate limit exceeded for {client_ip} on {request.url.path} "
                f"({count}/{settings.rate_limit_requests})"
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded. Try again in {retry_after} seconds.",
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(settings.rate_limit_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(window_start + settings.rate_limit_period)),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_requests)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, settings.rate_limit_requests - count)
        )
        response.headers["X-RateLimit-Reset"] = str(
            int(window_start + settings.rate_limit_period)
        )

        return response

    def _cleanup_expired(self, current_time: float) -> None:
        """Remove expired entries. Must be called with lock held."""
        cutoff = current_time - (settings.rate_limit_period * 2)
        expired = [ip for ip, entry in self._requests.items() if entry.window_start < cutoff]
        for ip in expired:
            del self._requests[ip]
        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired rate limit entries")
