# DRACO METRIC

High-performance WireGuard VPN server aggregator API. Fetches, normalizes, and serves VPN server data from multiple providers through a unified REST API with built-in latency measurement.

## Features

- **Multi-provider support** — NordVPN and Surfshark with a unified data model
- **WireGuard-focused** — Filters for WireGuard-capable servers with online status verification
- **Latency measurement** — Real-time server latency via fping (bulk) or TCP connect (fallback)
- **Performance** — HTTP/2, connection pooling, async caching, orjson serialization, gzip compression
- **Security** — API key auth, rate limiting, CORS allowlist, security headers, input validation

## Quick Start

```bash
git clone https://github.com/adamantium/draco-metric.git
cd draco-metric
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for interactive API documentation (Swagger UI).

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/{provider}/servers` | All servers (paginated) |
| `GET` | `/api/{provider}/servers/paginated` | Servers with pagination metadata |
| `GET` | `/api/{provider}/servers/top` | Top servers by load/latency |
| `GET` | `/api/{provider}/servers/latency` | Measure server latency |
| `GET` | `/api/{provider}/servers/fastest` | Fastest servers by measured latency |
| `GET` | `/api/{provider}/servers/{country_code}` | Servers by country |
| `GET` | `/api/{provider}/countries` | Available countries |
| `GET` | `/health` | Health check |

Where `{provider}` is `nordvpn` or `surfshark`.

## Tech Stack

- **Python 3.13+** with **FastAPI** and **uvicorn**
- **httpx** with HTTP/2 for upstream API calls
- **aiocache** for async in-memory caching
- **pydantic v2** + **pydantic-settings** for data validation and configuration
- **orjson** for fast JSON serialization

## Documentation

Full documentation is available via [MkDocs](https://www.mkdocs.org/):

```bash
uv run mkdocs serve
```

Then open [http://localhost:8001](http://localhost:8001).

Topics covered:

- [Quick Start](docs/quickstart.md)
- [Installation](docs/installation.md)
- [Configuration](docs/configuration.md)
- [Architecture](docs/architecture.md)
- [API Reference](docs/api-reference.md)
- [Security](docs/security.md)
- Deployment: [Development](docs/deployment/development.md) | [Production](docs/deployment/production.md) | [Container](docs/deployment/container.md) | [Reverse Proxy](docs/deployment/reverse-proxy.md)

## License

BSD-3-Clause
