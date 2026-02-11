# Container Deployment

DRACO METRIC includes a multi-stage `Containerfile` compatible with both Podman and Docker.

## Building the Image

=== "Podman"

    ```bash
    podman build -t draco-metric:latest -f Containerfile .
    ```

=== "Docker"

    ```bash
    docker build -t draco-metric:latest -f Containerfile .
    ```

## Running the Container

### Basic

=== "Podman"

    ```bash
    podman run -d \
        --name draco-metric \
        -p 127.0.0.1:8000:8000 \
        --env-file .env \
        draco-metric:latest
    ```

=== "Docker"

    ```bash
    docker run -d \
        --name draco-metric \
        -p 127.0.0.1:8000:8000 \
        --env-file .env \
        draco-metric:latest
    ```

### With custom environment variables

=== "Podman"

    ```bash
    podman run -d \
        --name draco-metric \
        -p 127.0.0.1:8000:8000 \
        -e DEBUG=false \
        -e ENABLE_API_KEY_AUTH=true \
        -e API_KEYS='["your-key-at-least-32-characters-long-here"]' \
        -e LOG_LEVEL=WARNING \
        -e LOG_FORMAT=json \
        -e CORS_ORIGINS='["https://yourdomain.com"]' \
        draco-metric:latest
    ```

=== "Docker"

    ```bash
    docker run -d \
        --name draco-metric \
        -p 127.0.0.1:8000:8000 \
        -e DEBUG=false \
        -e ENABLE_API_KEY_AUTH=true \
        -e API_KEYS='["your-key-at-least-32-characters-long-here"]' \
        -e LOG_LEVEL=WARNING \
        -e LOG_FORMAT=json \
        -e CORS_ORIGINS='["https://yourdomain.com"]' \
        draco-metric:latest
    ```

### With custom worker count

Override the default CMD to change uvicorn options:

```bash
podman run -d \
    --name draco-metric \
    -p 127.0.0.1:8000:8000 \
    --env-file .env \
    draco-metric:latest \
    --host 0.0.0.0 --port 8000 --workers 4 --limit-max-requests 10000 --timeout-keep-alive 30
```

## Container Architecture

The Containerfile uses a **multi-stage build**:

### Stage 1: Builder

- Base: `python:3.13-slim-bookworm`
- Installs `uv` for fast dependency resolution
- Creates a virtual environment at `/opt/venv`
- Installs production dependencies only (no dev packages)

### Stage 2: Production

- Base: `python:3.13-slim-bookworm`
- Copies virtual environment from builder
- Copies application code
- Runs as non-root user (`uid:gid 65532:65532`)

## Security Features

| Feature | Detail |
|---|---|
| Non-root user | `nonroot` user with `uid/gid 65532` |
| No login shell | User shell is `/usr/sbin/nologin` |
| Minimal image | No build tools, compilers, or package managers |
| Production defaults | `DEBUG=false`, auth and security headers enabled |
| Health check | Built-in `HEALTHCHECK` instruction |
| Request limits | Workers restart after 10,000 requests |

## Default Environment

These environment variables are set in the Containerfile (can be overridden at runtime):

```
DEBUG=false
LOG_LEVEL=WARNING
ENABLE_API_KEY_AUTH=true
ENABLE_SECURITY_HEADERS=true
RATE_LIMIT_ENABLED=true
```

## Health Check

The container includes a built-in health check:

```
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3
```

It polls `http://127.0.0.1:8000/health` every 30 seconds.

Check container health:

=== "Podman"

    ```bash
    podman inspect --format='{{.State.Health.Status}}' draco-metric
    ```

=== "Docker"

    ```bash
    docker inspect --format='{{.State.Health.Status}}' draco-metric
    ```

## Container Management

### View logs

```bash
podman logs -f draco-metric
```

### Stop and remove

```bash
podman stop draco-metric
podman rm draco-metric
```

### Restart

```bash
podman restart draco-metric
```

## Compose Example

Create `compose.yml`:

```yaml
services:
  draco-metric:
    build:
      context: .
      dockerfile: Containerfile
    container_name: draco-metric
    ports:
      - "127.0.0.1:8000:8000"
    env_file:
      - .env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```

Run:

=== "Podman"

    ```bash
    podman compose up -d
    ```

=== "Docker"

    ```bash
    docker compose up -d
    ```

## Image Size

The multi-stage build produces a minimal image. Approximate sizes:

| Component | Size |
|---|---|
| Base image (python:3.13-slim) | ~150 MB |
| Virtual environment | ~80 MB |
| Application code | < 1 MB |
| **Total** | **~230 MB** |
