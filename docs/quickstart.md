# Quick Start

Get DRACO METRIC running locally in under 2 minutes with Swagger UI and ReDoc enabled.

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager

## Steps

### 1. Clone and install

```bash
git clone https://github.com/adamantium/draco-metric.git
cd draco-metric
uv sync
```

### 2. Create development config

```bash
cp .env.example .env
```

Edit `.env` and set:

```ini
DEBUG=true
ENABLE_API_KEY_AUTH=false
RATE_LIMIT_ENABLED=true
LOG_LEVEL=DEBUG
```

!!! tip
    Setting `DEBUG=true` enables `/docs` (Swagger UI), `/redoc` (ReDoc), and `/openapi.json`.

### 3. Start the server

```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 4. Explore the API

Open your browser:

| URL | Description |
|---|---|
| [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger UI (interactive) |
| [http://localhost:8000/redoc](http://localhost:8000/redoc) | ReDoc (reference) |
| [http://localhost:8000/health](http://localhost:8000/health) | Health check |

### 5. Make your first request

```bash
# Get NordVPN servers (first page)
curl http://localhost:8000/api/nordvpn/servers?page_size=5

# Get Surfshark servers for Brazil
curl http://localhost:8000/api/surfshark/servers/BR

# List available countries
curl http://localhost:8000/api/nordvpn/countries

# Get top 5 lowest-load servers
curl http://localhost:8000/api/nordvpn/servers/top?limit=5
```

### 6. Run tests

```bash
uv run pytest
```

## Next Steps

- [Configuration Reference](configuration.md) - All environment variables explained
- [API Reference](api-reference.md) - Complete endpoint documentation
- [Production Deployment](deployment/production.md) - Deploy securely
