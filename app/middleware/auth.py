"""API Key authentication middleware."""

import logging
import secrets
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.settings import settings

logger = logging.getLogger(__name__)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware to validate API keys for protected endpoints."""

    EXCLUDED_PATHS = {"/docs", "/redoc", "/openapi.json", "/health"}

    async def dispatch(self, request: Request, call_next):
        """Check API key for all requests except excluded paths."""
        # Skip authentication for excluded paths
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        # Skip if authentication is disabled
        if not settings.enable_api_key_auth:
            return await call_next(request)

        # Extract API key from header
        api_key = request.headers.get("X-API-Key")

        if not api_key:
            logger.warning(f"Missing API key for request to {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Unauthorized", "message": "API key is required"},
            )

        # Validate API key using constant-time comparison to prevent timing attacks
        key_valid = any(
            secrets.compare_digest(api_key.encode(), valid_key.encode())
            for valid_key in settings.api_keys
        )
        if not key_valid:
            client_host = request.client.host if request.client else "unknown"
            logger.warning(
                f"Invalid API key attempt from {client_host} to {request.url.path}"
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"error": "Forbidden", "message": "Invalid API key"},
            )

        # API key is valid, proceed
        return await call_next(request)
