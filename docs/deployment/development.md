# Development Setup

Complete guide to setting up a local development environment.

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- Git
- fping (optional, for latency measurements)

## Setup

### 1. Clone and install

```bash
git clone https://github.com/adamantium/draco-metric.git
cd draco-metric
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` for development:

```ini
# Enable interactive API docs
DEBUG=true

# Disable auth for local development
ENABLE_API_KEY_AUTH=false

# Verbose logging
LOG_LEVEL=DEBUG
LOG_FORMAT=text

# Keep rate limiting but with higher threshold
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=1000

# Local CORS origins
CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]
```

### 3. Start the server

```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The `--reload` flag watches for file changes and restarts automatically.

You should see:

```
INFO - Starting DRACO METRIC v1.0.0
INFO - HTTP client initialized with HTTP/2 and connection pooling
INFO - Application startup complete
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 4. Verify

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status": "healthy", "version": "1.0.0"}
```

### 5. Explore the API

With `DEBUG=true`, interactive documentation is available:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Running Tests

```bash
# All tests with coverage report
uv run pytest

# Verbose output
uv run pytest -v

# Specific test file
uv run pytest tests/test_services.py

# Specific test
uv run pytest tests/test_services.py::test_nordvpn_filters_offline_servers
```

Coverage report is written to `htmlcov/` — open `htmlcov/index.html` in a browser.

## Linting

```bash
# Check for issues
uv run ruff check app/ tests/

# Auto-fix issues
uv run ruff check --fix app/ tests/

# Format code
uv run ruff format app/ tests/
```

## Useful Development Requests

```bash
# NordVPN servers (first 5)
curl -s http://localhost:8000/api/nordvpn/servers?page_size=5 | python -m json.tool

# Surfshark servers for US
curl -s http://localhost:8000/api/surfshark/servers/US | python -m json.tool

# Available countries
curl -s http://localhost:8000/api/nordvpn/countries | python -m json.tool

# Top 3 servers by load
curl -s "http://localhost:8000/api/nordvpn/servers/top?limit=3" | python -m json.tool

# Measure latency (TCP, 10 servers)
curl -s "http://localhost:8000/api/nordvpn/servers/latency?limit=10&method=tcp" | python -m json.tool

# Find fastest server
curl -s "http://localhost:8000/api/nordvpn/servers/fastest?limit=1" | python -m json.tool
```

## Testing with API Key Auth

To test authentication locally:

```bash
# Generate a test key
KEY=$(openssl rand -hex 32)
echo "Generated key: $KEY"
```

Update `.env`:

```ini
ENABLE_API_KEY_AUTH=true
API_KEYS=["<paste-your-key-here>"]
```

Restart the server, then:

```bash
# This should fail (401)
curl http://localhost:8000/api/nordvpn/servers

# This should work
curl -H "X-API-Key: $KEY" http://localhost:8000/api/nordvpn/servers
```
