# Security

DRACO METRIC is designed with a security-first approach. This document covers all security features, how they work, and how to configure them.

## Security Layers

The API applies security in layers, from outermost to innermost:

```
Request → Rate Limiting → API Key Auth → CORS → Route Handler → Security Headers → Response
```

Each layer can be independently enabled or disabled via environment variables.

---

## API Key Authentication

When enabled, all `/api/*` endpoints require a valid `X-API-Key` header.

### How It Works

1. Client sends `X-API-Key: <key>` header with every request
2. Middleware extracts the key and compares it against configured keys
3. Comparison uses `secrets.compare_digest()` for **constant-time comparison** (prevents timing attacks)
4. Invalid keys return `403 Forbidden`; missing keys return `401 Unauthorized`

### Configuration

```ini
ENABLE_API_KEY_AUTH=true
API_KEYS=["your-key-here-min-32-chars-long-abcdef"]
```

### Generating Keys

```bash
# Generate a 64-character hex key
openssl rand -hex 32

# Generate multiple keys
for i in 1 2 3; do openssl rand -hex 32; done
```

### Multiple Keys

You can configure multiple keys for key rotation or multi-tenant access:

```ini
API_KEYS=["key-for-service-a-min-32-chars-long","key-for-service-b-min-32-chars-long"]
```

### Key Requirements

- Minimum **32 characters** (enforced at startup)
- Validated on application boot — invalid keys prevent startup

### Excluded Paths

These paths are **never** subject to API key authentication:

| Path | Reason |
|---|---|
| `/health` | Load balancer health checks |
| `/docs` | Swagger UI (debug mode only) |
| `/redoc` | ReDoc (debug mode only) |
| `/openapi.json` | OpenAPI spec (debug mode only) |

### Usage Example

```bash
curl -H "X-API-Key: your-key-here-min-32-chars-long-abcdef" \
     http://localhost:8000/api/nordvpn/servers
```

---

## Rate Limiting

Protects the API from abuse using a per-IP sliding window algorithm.

### How It Works

1. Each client IP gets a request counter with a time window
2. When the counter exceeds the limit, requests are rejected with `429`
3. The window slides: when the period expires, the counter resets
4. Expired entries are cleaned up every 5 minutes

### Configuration

```ini
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100    # requests per window
RATE_LIMIT_PERIOD=60       # window size in seconds
```

### Response Headers

Every response includes rate limit information:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1707580860
```

When rate-limited (`429 Too Many Requests`):

```
Retry-After: 45
X-RateLimit-Remaining: 0
```

### Reverse Proxy Considerations

Behind a reverse proxy, the rate limiter needs to know the real client IP. Configure trusted proxies:

```ini
TRUSTED_HOSTS=["127.0.0.1","::1","10.0.0.1"]
```

The rate limiter only trusts `X-Forwarded-For` from IPs listed in `TRUSTED_HOSTS`. Direct connections from untrusted IPs use the socket IP.

### Excluded Paths

`/health`, `/docs`, `/redoc`, and `/openapi.json` are exempt from rate limiting.

### Scaling Note

The rate limiter uses **in-memory storage**. This works correctly for single-instance deployments. For multi-instance deployments behind a load balancer, consider adding a Redis-backed rate limiter or use rate limiting at the reverse proxy layer (nginx/Caddy).

---

## Security Headers

When enabled, every response includes hardened HTTP headers.

### Configuration

```ini
ENABLE_SECURITY_HEADERS=true
```

### Headers Applied

| Header | Value | Purpose |
|---|---|---|
| `X-Content-Type-Options` | `nosniff` | Prevents MIME type sniffing |
| `X-Frame-Options` | `DENY` | Prevents clickjacking |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Controls referrer leakage |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` | Restricts browser features |

### Production-Only Headers

These are added only when `DEBUG=false`:

| Header | Value | Purpose |
|---|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Forces HTTPS for 1 year |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'` | Restricts resource loading |

### Server Header Removal

The `Server` header is removed from all responses to prevent server software fingerprinting.

---

## CORS (Cross-Origin Resource Sharing)

Controls which origins can make requests to the API.

### Configuration

```ini
CORS_ORIGINS=["https://app.example.com","https://admin.example.com"]
CORS_ALLOW_CREDENTIALS=true
```

### Security Rules

- **Wildcard `*` is rejected** — The application refuses to start with `CORS_ORIGINS=["*"]`
- Only `GET`, `HEAD`, and `OPTIONS` methods are allowed
- Only `X-API-Key`, `Content-Type`, and `Accept` headers are allowed
- Preflight responses are cached for 24 hours (`max_age=86400`)

### Development Config

```ini
CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]
```

### Production Config

```ini
CORS_ORIGINS=["https://yourdomain.com"]
CORS_ALLOW_CREDENTIALS=false
```

---

## Error Handling

All error responses are sanitized to prevent information disclosure.

### Sanitization Rules

| Error Type | What is exposed | What is hidden |
|---|---|---|
| Validation errors | Field name, error type, message | Stack traces, internal paths |
| External API failures | Generic "Service Unavailable" | Provider URLs, response bodies |
| Internal errors | Generic "Internal Server Error" | Exception details, stack traces |

### Exception Hierarchy

```
VPNServiceError (base)
├── VPNAPIError    → 503 Service Unavailable
└── VPNDataError   → 500 Internal Server Error

RequestValidationError → 422 Validation Error
Exception (catch-all)  → 500 Internal Server Error
```

---

## SSL/TLS

### Upstream Connections

All outgoing HTTP requests to VPN provider APIs enforce SSL verification (`verify=True`). This cannot be disabled.

### Client Connections

TLS termination should be handled by your reverse proxy (nginx, Caddy, or relayd). See [Reverse Proxy](deployment/reverse-proxy.md) for configuration templates.

---

## Container Security

The production container (see [Container Deployment](deployment/container.md)) includes:

| Feature | Implementation |
|---|---|
| Non-root user | Runs as `uid:gid 65532:65532` |
| Read-only filesystem | Application code is owned by nonroot |
| No shell access | User has `/usr/sbin/nologin` as shell |
| Minimal image | Python slim base, no build tools |
| Health check | Built-in health check endpoint |
| Request limits | Max 10,000 requests per worker before restart |

### Default Production Settings in Container

```
DEBUG=false
ENABLE_API_KEY_AUTH=true
ENABLE_SECURITY_HEADERS=true
RATE_LIMIT_ENABLED=true
LOG_LEVEL=WARNING
```

---

## Debug Mode

!!! danger "Never enable debug mode in production"
    `DEBUG=true` exposes `/docs`, `/redoc`, `/openapi.json`, enables auto-reload, detailed error messages, and disables HSTS/CSP headers.

### What Debug Mode Changes

| Feature | `DEBUG=false` (production) | `DEBUG=true` (development) |
|---|---|---|
| `/docs` | Disabled | Enabled |
| `/redoc` | Disabled | Enabled |
| `/openapi.json` | Disabled | Enabled |
| HSTS header | Enabled | Disabled |
| CSP header | Enabled | Disabled |
| Access logs | Disabled | Enabled |
| Auto-reload | Disabled | Enabled |

---

## Security Checklist

Before deploying to production:

- [ ] `DEBUG=false`
- [ ] `ENABLE_API_KEY_AUTH=true` with strong keys (>= 32 chars)
- [ ] `ENABLE_SECURITY_HEADERS=true`
- [ ] `RATE_LIMIT_ENABLED=true`
- [ ] `CORS_ORIGINS` set to actual frontend domains (no wildcard)
- [ ] `LOG_LEVEL=WARNING` or `ERROR`
- [ ] TLS termination configured at reverse proxy
- [ ] `TRUSTED_HOSTS` set to reverse proxy IPs only
- [ ] API keys stored securely (not in version control)
- [ ] Container running as non-root user
