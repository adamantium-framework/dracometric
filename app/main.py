# app/main.py
"""FastAPI application with security-first configuration."""

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.middleware import APIKeyMiddleware, RateLimitMiddleware
from app.routers import vpn
from app.services.vpn_service import (
    VPNAPIError,
    VPNServiceError,
    close_http_client,
    create_http_client,
)
from app.settings import settings

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format=(
        '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
        if settings.log_format == "json"
        else "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ),
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan with proper resource cleanup."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    await create_http_client()
    logger.info("Application startup complete")

    yield

    logger.info("Shutting down application")
    await close_http_client()
    logger.info("Application shutdown complete")


# Create FastAPI app with performance optimizations
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="High-performance WireGuard VPN server aggregator API",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    default_response_class=JSONResponse,
)


# --- Middleware Stack (order matters: last added = first executed) ---

# 1. Gzip compression (innermost - compress response)
app.add_middleware(GZipMiddleware, minimum_size=500)

# 2. CORS (before security checks)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["GET", "HEAD", "OPTIONS"],
    allow_headers=["X-API-Key", "Content-Type", "Accept"],
    max_age=86400,  # Cache preflight for 24 hours
)

# 3. API Key authentication
if settings.enable_api_key_auth:
    app.add_middleware(APIKeyMiddleware)
    logger.info("API Key authentication enabled")

# 4. Rate limiting (outermost security layer)
if settings.rate_limit_enabled:
    app.add_middleware(RateLimitMiddleware)
    logger.info(f"Rate limiting: {settings.rate_limit_requests} req/{settings.rate_limit_period}s")


# --- Security Headers (applied via middleware for all responses) ---
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)

    if settings.enable_security_headers:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        if not settings.debug:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"

    # Remove server header for security
    if "server" in response.headers:
        del response.headers["server"]

    return response


# --- Exception Handlers ---
@app.exception_handler(VPNAPIError)
async def vpn_api_error_handler(request: Request, exc: VPNAPIError):
    """Handle external VPN API failures."""
    logger.error(f"VPN API error: {request.url.path} - {exc}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"error": "Service Unavailable", "message": "VPN data temporarily unavailable."},
    )


@app.exception_handler(VPNServiceError)
async def vpn_service_error_handler(request: Request, exc: VPNServiceError):
    """Handle internal VPN service errors."""
    logger.error(f"VPN service error: {request.url.path} - {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal Server Error", "message": "An error occurred."},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with sanitized output."""
    logger.warning(f"Validation error: {request.url.path}")
    # Sanitize error details to prevent information disclosure
    errors = [
        {"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "Validation Error", "details": errors},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all handler - never expose internal details."""
    logger.exception(f"Unhandled exception: {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal Server Error", "message": "An unexpected error occurred."},
    )


# --- Health Check ---
@app.get("/health", tags=["Health"], response_class=JSONResponse)
async def health_check():
    """Lightweight health check for load balancers."""
    return {"status": "healthy", "version": settings.app_version}


# --- API Routes ---
app.include_router(vpn.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",  # Bind to localhost only for security
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=settings.debug,
    )
