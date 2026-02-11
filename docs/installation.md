# Installation

## Requirements

| Requirement | Version | Notes |
|---|---|---|
| Python | >= 3.13 | Required for all features |
| uv | latest | Fast Python package manager |
| fping | any (optional) | For fast bulk latency measurement |

## Install from Source

### 1. Clone the repository

```bash
git clone https://github.com/adamantium/draco-metric.git
cd draco-metric
```

### 2. Install uv (if not installed)

=== "Linux / macOS"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

=== "pip"

    ```bash
    pip install uv
    ```

### 3. Install dependencies

```bash
# Production dependencies only
uv sync --no-dev

# With development dependencies (testing, linting)
uv sync
```

This creates a `.venv/` virtual environment and installs all packages.

### 4. Create configuration file

```bash
cp .env.example .env
```

Edit `.env` to match your environment. See [Configuration](configuration.md) for all options.

### 5. Verify installation

```bash
uv run python -c "from app.main import app; print('OK')"
```

## Install fping (Optional)

fping enables significantly faster bulk latency measurements. Without it, the API falls back to TCP connect (which still works but is slower).

=== "Debian / Ubuntu"

    ```bash
    sudo apt install fping
    ```

=== "Fedora / RHEL"

    ```bash
    sudo dnf install fping
    ```

=== "macOS"

    ```bash
    brew install fping
    ```

=== "Alpine"

    ```bash
    apk add fping
    ```

Verify: `fping --version`

## Project Structure

```
draco-metric/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── settings.py             # Pydantic Settings configuration
│   ├── middleware/
│   │   ├── auth.py             # API key authentication
│   │   └── rate_limit.py       # Rate limiting
│   ├── models/
│   │   └── vpn.py              # VPNServer, CountryInfo schemas
│   ├── routers/
│   │   └── vpn.py              # API endpoint definitions
│   └── services/
│       ├── vpn_service.py      # HTTP client + abstract base class
│       ├── nordvpn_service.py   # NordVPN provider implementation
│       ├── surfshark_service.py # Surfshark provider implementation
│       └── latency_service.py   # Latency measurement (fping/TCP)
├── tests/
│   ├── conftest.py             # Test fixtures
│   ├── test_endpoints.py       # API integration tests
│   └── test_services.py        # Service unit tests
├── docs/                       # This documentation
├── .env.example                # Configuration template
├── Containerfile               # Podman/Docker build
├── pyproject.toml              # Project metadata and dependencies
└── mkdocs.yml                  # Documentation config
```

## Development Tools

### Running tests

```bash
uv run pytest                   # Run all tests with coverage
uv run pytest -v                # Verbose output
uv run pytest tests/test_services.py  # Run specific test file
```

### Linting and formatting

```bash
uv run ruff check app/          # Lint
uv run ruff format app/         # Format
```

### Starting the dev server

```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The `--reload` flag enables hot-reload on code changes.
