# Production Deployment

Complete guide to deploying DRACO METRIC in production.

## Overview

A production deployment consists of:

```
Internet → Reverse Proxy (TLS) → DRACO METRIC (uvicorn) → Upstream APIs
```

The reverse proxy handles TLS termination, static file serving, and connection management. DRACO METRIC handles the application logic.

## Option 1: Direct Python Deployment

### 1. Install dependencies

```bash
git clone https://github.com/adamantium/draco-metric.git
cd draco-metric
uv sync --no-dev
```

### 2. Create production configuration

```bash
cp .env.example .env
chmod 600 .env
```

Edit `.env`:

```ini
DEBUG=false
ENABLE_API_KEY_AUTH=true
API_KEYS=["<generate-with-openssl-rand-hex-32>"]
ENABLE_SECURITY_HEADERS=true
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60
LOG_LEVEL=WARNING
LOG_FORMAT=json
CORS_ORIGINS=["https://yourdomain.com"]
CORS_ALLOW_CREDENTIALS=false
TRUSTED_HOSTS=["127.0.0.1","::1"]
```

### 3. Start with uvicorn

```bash
uv run uvicorn app.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 2 \
    --limit-max-requests 10000 \
    --timeout-keep-alive 30 \
    --log-level warning
```

| Flag | Purpose |
|---|---|
| `--host 127.0.0.1` | Bind to localhost only (reverse proxy handles external traffic) |
| `--workers 2` | Number of worker processes (adjust per CPU cores) |
| `--limit-max-requests 10000` | Restart workers after 10K requests (prevents memory leaks) |
| `--timeout-keep-alive 30` | Keepalive timeout in seconds |

### 4. Systemd service (Linux)

Create `/etc/systemd/system/draco-metric.service`:

```ini
[Unit]
Description=DRACO METRIC API
After=network.target

[Service]
Type=exec
User=dracometric
Group=dracometric
WorkingDirectory=/opt/draco-metric
EnvironmentFile=/opt/draco-metric/.env
ExecStart=/opt/draco-metric/.venv/bin/uvicorn app.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 2 \
    --limit-max-requests 10000 \
    --timeout-keep-alive 30 \
    --log-level warning
Restart=always
RestartSec=5

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/draco-metric
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo useradd --system --shell /usr/sbin/nologin dracometric
sudo systemctl daemon-reload
sudo systemctl enable --now draco-metric
sudo systemctl status draco-metric
```

## Option 2: Container Deployment

See [Container Deployment](container.md) for Podman/Docker deployment.

## Reverse Proxy

See [Reverse Proxy](reverse-proxy.md) for nginx, Caddy, and OpenBSD relayd templates.

## Workers

The number of workers depends on your use case:

| Workload | Recommended Workers | Reasoning |
|---|---|---|
| Low traffic | 2 | Minimal resource usage |
| Moderate traffic | 4 | Good balance |
| High traffic | CPU cores * 2 + 1 | Uvicorn recommendation |

Since DRACO METRIC is I/O-bound (waiting on upstream APIs and network latency), more workers help with concurrent requests.

## Health Checks

The `/health` endpoint returns `200 OK` with:

```json
{"status": "healthy", "version": "1.0.0"}
```

Use this for:

- Load balancer health checks
- Container orchestration (built into the Containerfile)
- Monitoring systems (uptime checks)

## Logging

### JSON logs (recommended for production)

```ini
LOG_FORMAT=json
LOG_LEVEL=WARNING
```

Output:
```json
{"time":"2026-01-15 12:00:00","level":"WARNING","logger":"app.middleware.rate_limit","message":"Rate limit exceeded for 1.2.3.4 on /api/nordvpn/servers (101/100)"}
```

### Log levels for production

| Level | Use Case |
|---|---|
| `WARNING` | Default — logs rate limits, auth failures, parse errors |
| `ERROR` | Minimal — only errors and exceptions |
| `INFO` | Verbose — includes startup, API calls, cache hits |

## Monitoring

Key metrics to monitor:

| What | How |
|---|---|
| Application health | Poll `/health` every 30s |
| Response times | Reverse proxy access logs |
| Error rate | Count `5xx` responses in logs |
| Rate limit hits | Count `429` responses or `WARNING` logs |
| Auth failures | Count `401`/`403` responses |
| Upstream availability | Count `503` responses (VPN API unreachable) |

## Security Checklist

Before going live:

- [ ] `DEBUG=false`
- [ ] `ENABLE_API_KEY_AUTH=true` with keys >= 32 characters
- [ ] `ENABLE_SECURITY_HEADERS=true`
- [ ] `RATE_LIMIT_ENABLED=true`
- [ ] `CORS_ORIGINS` restricted to your domains
- [ ] `TRUSTED_HOSTS` set to proxy IPs
- [ ] `.env` file has `chmod 600` (owner-only read)
- [ ] TLS configured at reverse proxy
- [ ] Running as non-root user
- [ ] `LOG_FORMAT=json` for structured logging
- [ ] Firewall: only port 443 exposed externally
- [ ] uvicorn binds to `127.0.0.1` (not `0.0.0.0`)
