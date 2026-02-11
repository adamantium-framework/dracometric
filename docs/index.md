# DRACO METRIC

**High-performance WireGuard VPN server aggregator API.**

DRACO METRIC is a security-hardened REST API built with FastAPI that aggregates VPN server data from multiple providers into a unified format. It fetches, normalizes, caches, and serves WireGuard-compatible server information from NordVPN and Surfshark through a single consistent interface.

## What It Does

- Fetches VPN server data from **NordVPN** and **Surfshark** APIs
- Filters for **WireGuard-compatible** servers only
- Returns only **online** servers (verified at both server and technology level)
- Provides **real-time latency measurement** via fping or TCP connect
- Normalizes all provider data into a **canonical format**
- **Caches** results with configurable TTL for performance
- Serves data through a **paginated, filterable REST API**

## Key Features

| Feature | Description |
|---|---|
| Multi-provider | NordVPN and Surfshark with unified schema |
| WireGuard only | Filters servers that support WireGuard UDP |
| Online filtering | Excludes offline servers and offline WireGuard endpoints |
| Latency measurement | Measures real network latency via fping or TCP |
| Pagination | All list endpoints support page/page_size parameters |
| Caching | In-memory async cache with configurable TTL (default: 5 min) |
| Rate limiting | Sliding window per-IP rate limiter with standard headers |
| API key auth | Optional timing-safe API key authentication |
| Security headers | HSTS, CSP, X-Frame-Options, and more |
| HTTP/2 | Upstream requests use HTTP/2 for performance |
| GZip compression | Automatic response compression |
| JSON performance | Uses orjson for fast serialization |

## Supported Providers

| Provider | Server Load | Online Status | WireGuard Filter |
|---|---|---|---|
| NordVPN | Yes (0-100%) | Yes (server + technology level) | API query filter + local validation |
| Surfshark | Yes (0-100%) | Implicit (API only returns online) | Local type filter (wireguard/generic) |

## Tech Stack

- **Python 3.13+** with async/await
- **FastAPI** with Pydantic v2 validation
- **httpx** with HTTP/2 and connection pooling
- **aiocache** for async in-memory caching
- **orjson** for high-performance JSON serialization
- **uvicorn** ASGI server

## License

BSD 3-Clause License. See [LICENSE](https://github.com/adamantium/draco-metric/blob/main/LICENSE).

Copyright (c) 2026, Guilherme Hakme - Adamantium Security.
