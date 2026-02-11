"""Custom middlewares for VPN API."""

from app.middleware.auth import APIKeyMiddleware
from app.middleware.rate_limit import RateLimitMiddleware

__all__ = ["APIKeyMiddleware", "RateLimitMiddleware"]
