# API Reference

Base URL: `http://localhost:8000` (development) or your production domain.

All API endpoints are prefixed with `/api`. The `{provider}` path parameter accepts `nordvpn` or `surfshark`.

!!! info "Authentication"
    When `ENABLE_API_KEY_AUTH=true`, all `/api/*` endpoints require the `X-API-Key` header. The `/health` endpoint is always public.

---

## Health Check

### `GET /health`

Lightweight health check for load balancers and monitoring. Always public (no auth required, no rate limiting).

**Response** `200 OK`

```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

## Server Discovery

### `GET /api/{provider}/servers`

Retrieves all available VPN servers for a provider with optional pagination.

**Path Parameters**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `provider` | string | Yes | `nordvpn` or `surfshark` |

**Query Parameters**

| Parameter | Type | Default | Range | Description |
|---|---|---|---|---|
| `page` | integer | `1` | >= 1 | Page number (1-indexed) |
| `page_size` | integer | `100` | 1 - 1000 | Results per page |

**Response** `200 OK` — `List[VPNServer]`

```json
[
  {
    "provider": "nordvpn",
    "country": "United States",
    "country_code": "US",
    "identifier": "us1234.nordvpn.com",
    "public_key": "abc123def456...",
    "load": 25,
    "latency": null
  }
]
```

**Notes**

- NordVPN servers are sorted by load (lowest first)
- Surfshark servers are returned in API order
- Only online servers with active WireGuard support are returned

---

### `GET /api/{provider}/servers/paginated`

Same as above but returns pagination metadata alongside the data.

**Query Parameters**

| Parameter | Type | Default | Range | Description |
|---|---|---|---|---|
| `page` | integer | `1` | >= 1 | Page number (1-indexed) |
| `page_size` | integer | `100` | 1 - 1000 | Results per page |

**Response** `200 OK` — `PaginatedResponse`

```json
{
  "total": 5432,
  "page": 1,
  "page_size": 100,
  "total_pages": 55,
  "data": [
    {
      "provider": "nordvpn",
      "country": "United States",
      "country_code": "US",
      "identifier": "us1234.nordvpn.com",
      "public_key": "abc123def456...",
      "load": 25,
      "latency": null
    }
  ]
}
```

**Error** `404 Not Found` — Page number exceeds total pages.

---

### `GET /api/{provider}/servers/{country_code}`

Retrieves servers for a specific country.

**Path Parameters**

| Parameter | Type | Required | Pattern | Description |
|---|---|---|---|---|
| `provider` | string | Yes | `nordvpn\|surfshark` | VPN provider |
| `country_code` | string | Yes | `^[A-Z]{2}$` | ISO 3166-1 alpha-2 code |

**Query Parameters**

| Parameter | Type | Default | Range | Description |
|---|---|---|---|---|
| `page` | integer | `1` | >= 1 | Page number |
| `page_size` | integer | `100` | 1 - 1000 | Results per page |

**Response** `200 OK` — `List[VPNServer]`

**Error** `404 Not Found` — No servers found for the specified country.

**Example**

```bash
curl http://localhost:8000/api/nordvpn/servers/BR
```

---

## Performance

### `GET /api/{provider}/servers/top`

Returns the top-performing servers ranked by latency (if available) then by load.

**Query Parameters**

| Parameter | Type | Default | Range | Description |
|---|---|---|---|---|
| `limit` | integer | `10` | 1 - 50 | Number of servers to return |
| `country_code` | string | null | `^[A-Z]{2}$` | Optional country filter |

**Response** `200 OK` — `List[VPNServer]`

Servers are sorted by:

1. **Latency** (if measured) — lower is better
2. **Load** (fallback) — lower is better

**Error** `404 Not Found` — No servers found for the specified country.

**Example**

```bash
# Top 5 servers globally
curl http://localhost:8000/api/nordvpn/servers/top?limit=5

# Top 10 in Germany
curl http://localhost:8000/api/nordvpn/servers/top?limit=10&country_code=DE
```

---

### `GET /api/{provider}/servers/latency`

Measures actual network latency to VPN servers and returns detailed results.

**Query Parameters**

| Parameter | Type | Default | Range | Description |
|---|---|---|---|---|
| `country_code` | string | null | `^[A-Z]{2}$` | Optional country filter |
| `limit` | integer | `0` | 0 - 5000 | Max servers to measure (0 = all) |
| `method` | string | `auto` | `auto\|fping\|tcp` | Measurement method |

**Measurement Methods**

| Method | Speed | Requirements | How It Works |
|---|---|---|---|
| `auto` | Fastest available | None | Uses fping if installed, else TCP |
| `fping` | ~2-5s / 100 servers | fping binary | ICMP ping via external command |
| `tcp` | ~10-30s / 100 servers | None | TCP connect to port 51820, fallback to 443/80/22 |

**Response** `200 OK` — `LatencyMeasurementResponse`

```json
{
  "total_servers": 150,
  "measured": 150,
  "successful": 142,
  "failed": 8,
  "method": "fping",
  "servers": [
    {
      "provider": "nordvpn",
      "country": "United States",
      "country_code": "US",
      "identifier": "us1234.nordvpn.com",
      "public_key": "abc123def456...",
      "load": 25,
      "latency": 12.45
    }
  ]
}
```

Results are sorted by latency (lowest first). Servers that could not be reached have `latency: null` and appear at the end.

---

### `GET /api/{provider}/servers/fastest`

Measures latency and returns only the fastest servers. This is the recommended endpoint for finding optimal servers.

**Query Parameters**

| Parameter | Type | Default | Range | Description |
|---|---|---|---|---|
| `limit` | integer | `10` | 1 - 50 | Number of fastest servers to return |
| `country_code` | string | null | `^[A-Z]{2}$` | Include only this country |
| `measure_count` | integer | `0` | 0 - 5000 | Servers to measure (0 = all) |
| `exclude` | string | null | e.g. `BR-US-DE` | Exclude countries (hyphen-separated) |

**Response** `200 OK` — `List[VPNServer]`

All returned servers have a non-null `latency` value and are sorted lowest-first.

**Error Responses**

| Status | Condition |
|---|---|
| `404` | No servers found after filtering |
| `503` | Could not reach any servers |

**Examples**

```bash
# 10 fastest servers globally
curl http://localhost:8000/api/nordvpn/servers/fastest

# 5 fastest in Japan
curl http://localhost:8000/api/nordvpn/servers/fastest?limit=5&country_code=JP

# 10 fastest excluding Brazil and US
curl http://localhost:8000/api/nordvpn/servers/fastest?exclude=BR-US

# Measure only 100 servers for faster response
curl http://localhost:8000/api/nordvpn/servers/fastest?measure_count=100
```

---

## Metadata

### `GET /api/{provider}/countries`

Returns a list of all countries that have available servers for the specified provider.

**Response** `200 OK` — `List[CountryInfo]`

```json
[
  {
    "code": "BR",
    "name": "Brazil",
    "display": "BR - Brazil"
  },
  {
    "code": "US",
    "name": "United States",
    "display": "US - United States"
  }
]
```

Results are sorted alphabetically by country code.

---

## Data Models

### VPNServer

| Field | Type | Required | Description |
|---|---|---|---|
| `provider` | `"nordvpn"` \| `"surfshark"` | Yes | VPN provider name |
| `country` | string | Yes | Full country name |
| `country_code` | string (2 chars) | Yes | ISO 3166-1 alpha-2 code |
| `identifier` | string | Yes | Server hostname (e.g., `us1234.nordvpn.com`) |
| `public_key` | string | Yes | WireGuard public key |
| `load` | integer \| null | No | Server load percentage (0-100) |
| `latency` | float \| null | No | Measured latency in milliseconds |

### CountryInfo

| Field | Type | Description |
|---|---|---|
| `code` | string (2 chars) | ISO 3166-1 alpha-2 code |
| `name` | string | Full country name |
| `display` | string | Formatted as `"CODE - Name"` |

### PaginatedResponse

| Field | Type | Description |
|---|---|---|
| `total` | integer | Total number of servers |
| `page` | integer | Current page number |
| `page_size` | integer | Items per page |
| `total_pages` | integer | Total number of pages |
| `data` | List[VPNServer] | Server data for current page |

### LatencyMeasurementResponse

| Field | Type | Description |
|---|---|---|
| `total_servers` | integer | Total servers measured |
| `measured` | integer | Number of servers measured |
| `successful` | integer | Servers that responded |
| `failed` | integer | Servers that did not respond |
| `method` | string | Measurement method used (`fping` or `tcp`) |
| `servers` | List[VPNServer] | Servers with latency data, sorted lowest first |

---

## Error Responses

All errors follow a consistent format:

```json
{
  "error": "Error Type",
  "message": "Human-readable description."
}
```

### Status Codes

| Code | Meaning | When |
|---|---|---|
| `200` | Success | Request completed successfully |
| `401` | Unauthorized | Missing API key (when auth is enabled) |
| `403` | Forbidden | Invalid API key |
| `404` | Not Found | Country/provider not found, page out of range |
| `422` | Validation Error | Invalid query parameters or path values |
| `429` | Too Many Requests | Rate limit exceeded |
| `500` | Internal Server Error | Unexpected server error |
| `503` | Service Unavailable | External VPN API is unreachable |

### Rate Limit Headers

Every response (except `/health`) includes rate limit headers:

| Header | Description |
|---|---|
| `X-RateLimit-Limit` | Maximum requests per window |
| `X-RateLimit-Remaining` | Requests remaining in current window |
| `X-RateLimit-Reset` | Unix epoch timestamp when the window resets |
| `Retry-After` | Seconds to wait (only on 429 responses) |

---

## Interactive Documentation

When `DEBUG=true`, the API serves interactive documentation:

| URL | Interface |
|---|---|
| `/docs` | Swagger UI — interactive, try requests in-browser |
| `/redoc` | ReDoc — clean reference documentation |
| `/openapi.json` | Raw OpenAPI 3.x specification |

!!! warning
    These endpoints are disabled in production (`DEBUG=false`) to prevent information disclosure.
