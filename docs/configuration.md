# Configuration

DRACO METRIC is configured via environment variables. Copy `.env.example` to `.env` and adjust the values.

```bash
cp .env.example .env
```

All settings have sensible defaults. The `.env` file is loaded automatically at startup via [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).

---

## Environment Variables Reference

### API URLs

| Variable | Default | Description |
|---|---|---|
| `NORDVPN_API_URL` | `https://api.nordvpn.com/v1/servers` | NordVPN API base URL (without query params) |
| `SURFSHARK_API_URL` | `https://api.surfshark.com/v3/server/clusters` | Surfshark API endpoint |

!!! note
    These are base URLs. The application appends query parameters (WireGuard filter, limit) automatically.

### Cache

| Variable | Default | Range | Description |
|---|---|---|---|
| `CACHE_TTL` | `300` | 60 - 3600 | Cache TTL in seconds. Server data is cached for this duration. |

A TTL of 300 seconds (5 minutes) balances freshness with performance. Lower values increase upstream API calls; higher values serve staler data.

### HTTP Client

| Variable | Default | Range | Description |
|---|---|---|---|
| `HTTP_TIMEOUT` | `30.0` | 5.0 - 120.0 | Read timeout in seconds for upstream API calls |
| `HTTP_MAX_CONNECTIONS` | `100` | 10 - 500 | Max concurrent connections to upstream APIs |
| `HTTP_MAX_KEEPALIVE_CONNECTIONS` | `20` | 5 - 100 | Max keepalive connections in the pool |

The HTTP client uses HTTP/2, connection pooling, and always verifies SSL certificates.

### API Limits

| Variable | Default | Range | Description |
|---|---|---|---|
| `NORDVPN_SERVER_LIMIT` | `0` | 0 - 10000 | Max servers to fetch from NordVPN. `0` = unlimited (fetch all). |
| `DEFAULT_PAGE_SIZE` | `100` | 10 - 500 | Default items per page in paginated responses |
| `MAX_PAGE_SIZE` | `1000` | 100 - 2000 | Maximum allowed page size |

### Security - CORS

| Variable | Default | Description |
|---|---|---|
| `CORS_ORIGINS` | `["http://localhost:3000","http://localhost:8000"]` | Allowed origins (JSON array). Wildcard `*` is **rejected**. |
| `CORS_ALLOW_CREDENTIALS` | `true` | Allow credentials in CORS requests |

### Security - Authentication

| Variable | Default | Description |
|---|---|---|
| `ENABLE_API_KEY_AUTH` | `false` | Enable API key authentication |
| `API_KEYS` | `[]` | API keys (JSON array). Each key must be >= 32 characters. |

### Security - Rate Limiting

| Variable | Default | Range | Description |
|---|---|---|---|
| `RATE_LIMIT_ENABLED` | `true` | — | Enable rate limiting |
| `RATE_LIMIT_REQUESTS` | `100` | 10 - 10000 | Requests allowed per window |
| `RATE_LIMIT_PERIOD` | `60` | 10 - 3600 | Window size in seconds |

### Security - Headers

| Variable | Default | Description |
|---|---|---|
| `ENABLE_SECURITY_HEADERS` | `true` | Add security headers to all responses |

### Logging

| Variable | Default | Options | Description |
|---|---|---|---|
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | Minimum log level |
| `LOG_FORMAT` | `text` | `text`, `json` | Log output format |

Use `json` format in production for structured log parsing (ELK, Datadog, etc.):

```ini
LOG_FORMAT=json
```

Output:
```json
{"time":"2026-01-15 12:00:00,000","level":"INFO","logger":"app.main","message":"Application startup complete"}
```

### Application

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `DRACO METRIC` | Application name (shown in logs and API docs) |
| `APP_VERSION` | `1.0.0` | Application version |
| `DEBUG` | `false` | Enable debug mode. **Never `true` in production.** |

### Trusted Proxies

| Variable | Default | Description |
|---|---|---|
| `TRUSTED_HOSTS` | `["127.0.0.1","::1"]` | IPs trusted for `X-Forwarded-For` header parsing |

---

## Example Configurations

### Development

```ini
DEBUG=true
ENABLE_API_KEY_AUTH=false
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=1000
LOG_LEVEL=DEBUG
LOG_FORMAT=text
CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]
```

### Production

```ini
DEBUG=false
ENABLE_API_KEY_AUTH=true
API_KEYS=["your-64-char-hex-key-generated-with-openssl-rand-hex-32-here"]
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60
LOG_LEVEL=WARNING
LOG_FORMAT=json
ENABLE_SECURITY_HEADERS=true
CORS_ORIGINS=["https://yourdomain.com"]
CORS_ALLOW_CREDENTIALS=false
TRUSTED_HOSTS=["127.0.0.1","::1"]
CACHE_TTL=300
```

### High-Traffic Production

```ini
DEBUG=false
ENABLE_API_KEY_AUTH=true
API_KEYS=["key1-at-least-32-characters-long-here","key2-at-least-32-characters-long-here"]
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=500
RATE_LIMIT_PERIOD=60
LOG_LEVEL=ERROR
LOG_FORMAT=json
ENABLE_SECURITY_HEADERS=true
CORS_ORIGINS=["https://app.example.com","https://api.example.com"]
CACHE_TTL=600
HTTP_MAX_CONNECTIONS=200
HTTP_MAX_KEEPALIVE_CONNECTIONS=50
```

---

## Validation

All settings are validated at startup using Pydantic. If any value is out of range or invalid, the application will refuse to start with a clear error message.

Examples of startup validation failures:

```
CACHE_TTL=10          → Error: value must be >= 60
API_KEYS=["short"]    → Error: API keys must be at least 32 characters
CORS_ORIGINS=["*"]    → Error: Wildcard CORS origin '*' is not allowed
LOG_LEVEL=VERBOSE     → Error: Invalid log level
```
