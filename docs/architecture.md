# Architecture

Technical architecture of DRACO METRIC, covering the application layers, data flow, and design decisions.

---

## High-Level Overview

```
                          ┌─────────────────────────────────────────────┐
                          │              Reverse Proxy                  │
                          │        (TLS termination, nginx/Caddy)       │
                          └──────────────────┬──────────────────────────┘
                                             │ HTTP :8000
                          ┌──────────────────▼──────────────────────────┐
                          │              DRACO METRIC                   │
                          │                                             │
                          │  ┌───────────┐  ┌──────────┐  ┌─────────┐  │
                          │  │Rate Limit │→ │ API Key  │→ │  CORS   │  │
                          │  │Middleware │  │  Auth    │  │Middleware│  │
                          │  └───────────┘  └──────────┘  └─────────┘  │
                          │                      │                      │
                          │  ┌───────────────────▼──────────────────┐   │
                          │  │           Router Layer               │   │
                          │  │        (FastAPI endpoints)           │   │
                          │  └───────────────────┬──────────────────┘   │
                          │                      │                      │
                          │  ┌───────────────────▼──────────────────┐   │
                          │  │          Service Layer               │   │
                          │  │  ┌──────────┐  ┌──────────────────┐  │   │
                          │  │  │ NordVPN  │  │    Surfshark     │  │   │
                          │  │  │ Service  │  │    Service       │  │   │
                          │  │  └──────────┘  └──────────────────┘  │   │
                          │  │  ┌──────────────────────────────┐    │   │
                          │  │  │      Latency Service         │    │   │
                          │  │  │  (fping / TCP connect)       │    │   │
                          │  │  └──────────────────────────────┘    │   │
                          │  └──────────────────────────────────────┘   │
                          │                      │                      │
                          │  ┌───────────────────▼──────────────────┐   │
                          │  │          Infrastructure              │   │
                          │  │  ┌──────────┐  ┌──────────────────┐  │   │
                          │  │  │  Cache   │  │   HTTP Client    │  │   │
                          │  │  │(aiocache)│  │  (httpx/HTTP2)   │  │   │
                          │  │  └──────────┘  └──────────────────┘  │   │
                          │  └──────────────────────────────────────┘   │
                          └─────────────────────────────────────────────┘
                                             │
                          ┌──────────────────▼──────────────────────────┐
                          │           Upstream VPN APIs                 │
                          │  ┌──────────────┐  ┌────────────────────┐   │
                          │  │ NordVPN API  │  │  Surfshark API     │   │
                          │  │  /v1/servers │  │ /v3/server/clusters│   │
                          │  └──────────────┘  └────────────────────┘   │
                          └─────────────────────────────────────────────┘
```

---

## Project Structure

```
app/
├── main.py                     # Application entry point, middleware stack, exception handlers
├── settings.py                 # Pydantic-based configuration (env vars)
├── models/
│   └── vpn.py                  # Canonical data models (VPNServer, CountryInfo)
├── routers/
│   └── vpn.py                  # API endpoints with dependency injection
├── middleware/
│   ├── __init__.py             # Middleware exports
│   ├── auth.py                 # API key authentication middleware
│   └── rate_limit.py           # Sliding window rate limiter
└── services/
    ├── vpn_service.py          # Abstract base class + HTTP client management
    ├── nordvpn_service.py      # NordVPN API integration
    ├── surfshark_service.py    # Surfshark API integration
    └── latency_service.py      # Network latency measurement (fping/TCP)
```

---

## Application Layers

### 1. Middleware Stack

Middleware executes in a specific order. In FastAPI, the **last middleware added is the first to execute** on incoming requests:

```
Request → Rate Limit → API Key Auth → CORS → Security Headers → GZip → Router
                                                                          │
Response ← Rate Limit ← API Key Auth ← CORS ← Security Headers ← GZip ←─┘
```

| Order | Middleware | Purpose |
|---|---|---|
| 1st (outermost) | **Rate Limiter** | Reject excessive requests before any processing |
| 2nd | **API Key Auth** | Authenticate requests via `X-API-Key` header |
| 3rd | **CORS** | Handle cross-origin preflight and response headers |
| 4th | **Security Headers** | Add `X-Frame-Options`, `HSTS`, `CSP`, etc. |
| 5th (innermost) | **GZip** | Compress responses larger than 500 bytes |

Each middleware can short-circuit the request (e.g., rate limiter returns `429` without reaching the router).

### 2. Router Layer

A single router (`/api`) handles all VPN endpoints using FastAPI's dependency injection:

```python
# The provider is resolved via path parameter dependency
@router.get("/{provider}/servers")
async def get_servers(service = Depends(get_vpn_service)):
    return await service.get_servers()
```

The `get_vpn_service` dependency resolves `{provider}` ("nordvpn" or "surfshark") to the appropriate service singleton. This pattern allows adding new providers without modifying existing endpoints.

**Route ordering matters** — specific routes (`/servers/top`, `/servers/latency`, `/servers/fastest`) are registered before the parameterized route (`/servers/{country_code}`) to avoid path conflicts.

### 3. Service Layer

Services follow the **Abstract Factory** pattern:

```
AbstractVPNService (ABC)
├── get_servers() → List[VPNServer]
└── get_servers_by_country(code) → List[VPNServer]

NordVPNService(AbstractVPNService)
├── Fetches from NordVPN API
├── Filters: status == "online", WireGuard pivot.status == "online"
├── Extracts WireGuard public key from technology metadata
└── Sorts by load (lowest first)

SurfsharkService(AbstractVPNService)
├── Fetches from Surfshark API
├── Filters: type in ["wireguard", "generic"] with pubKey
├── No explicit status field (API only returns available servers)
└── Returns in API order

LatencyService
├── measure_servers_latency() → List[VPNServer] (with latency populated)
├── fping: Bulk ICMP via external command (fastest, batched in groups of 500)
└── TCP: Async connection to port 51820 with fallback to 443/80/22
```

All service instances are **singletons** managed by the router's dependency factory.

### 4. Data Model

The canonical `VPNServer` model normalizes data from all providers into a single schema:

```python
class VPNServer(BaseModel):
    provider: Literal["nordvpn", "surfshark"]
    country: str              # Full country name
    country_code: str         # ISO 3166-1 alpha-2 (e.g., "US")
    identifier: str           # Hostname or connection name
    public_key: str           # WireGuard public key
    load: Optional[int]       # Server load 0-100% (if available)
    latency: Optional[float]  # Measured latency in ms (if measured)
```

This normalization allows all endpoints to work identically regardless of the upstream provider.

---

## Data Flow

### Server Fetch (Cache Miss)

```
1. Client → GET /api/nordvpn/servers
2. Router → NordVPNService.get_servers()
3. aiocache: cache miss
4. Service → httpx.AsyncClient.get(nordvpn_api_url + filters)
5. NordVPN API → JSON response (~6000 servers)
6. Service → _parse_nordvpn_servers():
   - Filter: status == "online"
   - Filter: WireGuard pivot.status == "online"
   - Extract: hostname, public_key, load, country
   - Sort by load (ascending)
7. aiocache: store result (TTL from CACHE_TTL setting)
8. Router → Apply pagination → Return JSON
```

### Server Fetch (Cache Hit)

```
1. Client → GET /api/nordvpn/servers
2. Router → NordVPNService.get_servers()
3. aiocache: cache hit → return cached List[VPNServer]
4. Router → Apply pagination → Return JSON
```

### Latency Measurement

```
1. Client → GET /api/nordvpn/servers/latency?method=auto&limit=100
2. Router → Fetch servers (cached) → Take first 100
3. LatencyService.measure_servers_latency():
   a. Extract unique hostnames
   b. If fping available:
      - Batch hosts (500 per batch)
      - Execute: fping -c 1 -t 1000 -q -e <hosts>
      - Parse stderr for avg latency per host
      - Fallback to TCP if 0 successes
   c. If TCP fallback:
      - Semaphore(50) for concurrency control
      - For each host: asyncio.open_connection(host, 51820)
      - Fallback ports: 443, 80, 22
      - Measure connection establishment time
   d. Update VPNServer objects with latency values
4. Router → Sort by latency → Return JSON
```

---

## Caching Strategy

DRACO METRIC uses `aiocache` for in-memory async caching:

| What | Cache Key | TTL | Invalidation |
|---|---|---|---|
| All servers (per provider) | Method-level (automatic) | `CACHE_TTL` (default 300s) | TTL expiry |
| Servers by country | `get_servers_by_country:{country_code}` | `CACHE_TTL` | TTL expiry |

Cache is purely in-memory with no external dependencies. Each worker process maintains its own cache.

**Trade-offs:**

- Simple, zero-dependency caching
- No shared state between workers (each worker caches independently)
- Memory scales linearly with number of workers
- For multi-instance deployments, consider adding a Redis backend

---

## HTTP Client

A single `httpx.AsyncClient` instance is shared across the application:

| Setting | Value | Purpose |
|---|---|---|
| HTTP/2 | Enabled | Multiplexed requests, header compression |
| Connection pool | Up to 100 connections | Reuse connections to upstream APIs |
| Keepalive | 20 connections, 30s expiry | Reduce connection overhead |
| SSL verification | Always enabled | Never disabled, even in debug |
| Timeouts | Connect: 5s, Read: 30s, Write: 10s | Fast failure on connection issues |

The client is created during application startup (`lifespan` context manager) and closed during shutdown.

---

## Security Architecture

### Defense in Depth

```
Layer 1: Reverse Proxy    → TLS termination, connection limits
Layer 2: Rate Limiter     → Per-IP sliding window, async-safe
Layer 3: Authentication   → API key with timing-safe comparison
Layer 4: CORS             → Explicit origin allowlist, no wildcards
Layer 5: Input Validation → Pydantic models, path parameter regex
Layer 6: Error Handling   → Sanitized responses, no stack traces
Layer 7: Response Headers → HSTS, CSP, X-Frame-Options, etc.
```

### Rate Limiter Design

The rate limiter uses a **sliding window** algorithm with `asyncio.Lock`:

- Per-IP tracking using `X-Forwarded-For` (from trusted proxies only)
- Window resets after `RATE_LIMIT_PERIOD` seconds of inactivity
- Expired entries cleaned up every 5 minutes
- Headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`) on every response

### Authentication

- API keys validated with `secrets.compare_digest()` (constant-time comparison)
- Keys must be at least 32 characters
- `/health`, `/docs`, `/redoc`, `/openapi.json` paths are excluded from auth

---

## Configuration

All configuration flows through `pydantic-settings`:

```
.env file → Environment Variables → Settings(BaseSettings) → Frozen Instance
```

- Settings are **immutable** (`frozen=True`) after initialization
- Validated at startup with clear error messages
- Cached via `@lru_cache` (single instance per process)
- Accessed throughout the application via `from app.settings import settings`

---

## Container Architecture

The Containerfile uses a **multi-stage build**:

```
Stage 1: Builder
  python:3.13-slim-bookworm
  + uv (from ghcr.io/astral-sh/uv)
  + pyproject.toml + uv.lock
  → /opt/venv (production deps only)

Stage 2: Production
  python:3.13-slim-bookworm
  + /opt/venv (from builder)
  + app/ (application code)
  + nonroot user (uid:gid 65532:65532)
  → ENTRYPOINT: uvicorn app.main:app
```

Security features:

- **Non-root user** with no login shell
- **No build tools** in production image (no pip, no uv, no compilers)
- **Production defaults** baked in (`DEBUG=false`, auth enabled)
- **Built-in health check** polling `/health` every 30s
- **~230 MB** final image size

---

## Error Handling

Exceptions are organized in a hierarchy:

```
Exception
└── VPNServiceError (base)
    ├── VPNAPIError    → 503 Service Unavailable
    └── VPNDataError   → 500 Internal Server Error

RequestValidationError → 422 Unprocessable Entity (sanitized)
Exception (catch-all)  → 500 Internal Server Error (generic message)
```

All error responses follow a consistent format:

```json
{
  "error": "Error Type",
  "message": "User-safe description"
}
```

Internal details (stack traces, upstream error bodies) are logged but never exposed to clients.

---

## Performance Characteristics

| Aspect | Detail |
|---|---|
| JSON serialization | `orjson` via `ORJSONResponse` (2-3x faster than stdlib) |
| Response compression | GZip for responses > 500 bytes |
| Connection reuse | HTTP/2 multiplexing + keepalive pool |
| Cache TTL | 5 minutes (configurable 60s - 3600s) |
| Worker restart | Every 10,000 requests (prevents memory leaks) |
| Latency measurement | fping: ~2-5s for 100 servers, TCP: ~10-30s for 100 servers |
