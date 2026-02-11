# VPN API - Production Container
#
# Multi-stage build for minimal image size and security
# Uses Python 3.13 slim as base for consistency

# =============================================================================
# Stage 1: Builder
# =============================================================================
FROM docker.io/library/python:3.13-slim-bookworm AS builder

WORKDIR /build

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Create virtual environment and install production dependencies only
RUN uv venv /opt/venv && \
    UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --frozen --no-dev --no-install-project

# =============================================================================
# Stage 2: Production
# =============================================================================
FROM docker.io/library/python:3.13-slim-bookworm

# Labels for container metadata (OCI spec)
LABEL org.opencontainers.image.title="VPN API" \
      org.opencontainers.image.description="High-performance WireGuard VPN server aggregator" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.vendor="Adamantium Security" \
      org.opencontainers.image.licenses="BSD-3-Clause" \
      org.opencontainers.image.source="https://github.com/adamantium/vpn-api"

# Create non-root user for security
RUN groupadd --gid 65532 nonroot && \
    useradd --uid 65532 --gid 65532 --shell /usr/sbin/nologin --create-home nonroot

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=nonroot:nonroot app/ ./app/

# Environment configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV=/opt/venv \
    HOST=0.0.0.0 \
    PORT=8000 \
    # Production defaults
    DEBUG=false \
    LOG_LEVEL=WARNING \
    ENABLE_API_KEY_AUTH=true \
    ENABLE_SECURITY_HEADERS=true \
    RATE_LIMIT_ENABLED=true

# Expose port (documentation only)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]

# Run as non-root user
USER nonroot

# Start application with optimal settings
ENTRYPOINT ["python", "-m", "uvicorn", "app.main:app"]
CMD ["--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--limit-max-requests", "10000", "--timeout-keep-alive", "30"]
