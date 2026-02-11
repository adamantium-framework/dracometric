# Reverse Proxy Configuration

DRACO METRIC should run behind a reverse proxy that handles TLS termination, connection management, and optionally rate limiting.

The application binds to `127.0.0.1:8000` by default. The reverse proxy listens on ports 80/443 and forwards requests.

```
Client → [443/TLS] → Reverse Proxy → [8000/HTTP] → DRACO METRIC
```

!!! important
    Configure `TRUSTED_HOSTS` in `.env` to include your reverse proxy's IP so that rate limiting uses the real client IP from `X-Forwarded-For`.

    ```ini
    TRUSTED_HOSTS=["127.0.0.1","::1"]
    ```

---

## Nginx

### Basic Configuration

```nginx
upstream draco_metric {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name api.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    # TLS
    ssl_certificate     /etc/ssl/certs/api.example.com.pem;
    ssl_certificate_key /etc/ssl/private/api.example.com.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1d;

    # Security headers (additional to what DRACO METRIC adds)
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;

    # Proxy settings
    location / {
        proxy_pass http://draco_metric;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";

        # Timeouts
        proxy_connect_timeout 5s;
        proxy_read_timeout 60s;
        proxy_send_timeout 10s;

        # Buffering
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }

    # Block access to debug endpoints in production
    location ~ ^/(docs|redoc|openapi\.json)$ {
        return 404;
    }

    # Health check passthrough
    location /health {
        proxy_pass http://draco_metric;
        access_log off;
    }
}
```

### With Nginx Rate Limiting

If you need rate limiting at the proxy level (e.g., multi-instance deployment):

```nginx
# Define rate limit zone (10 req/s per IP, 10MB shared memory)
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

server {
    # ... TLS config as above ...

    location / {
        limit_req zone=api_limit burst=20 nodelay;
        limit_req_status 429;

        proxy_pass http://draco_metric;
        # ... proxy settings as above ...
    }
}
```

---

## Caddy

Caddy provides automatic HTTPS via Let's Encrypt.

### Caddyfile

```
api.example.com {
    # Reverse proxy to DRACO METRIC
    reverse_proxy 127.0.0.1:8000 {
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}

        # Health checks
        health_uri /health
        health_interval 30s
        health_timeout 5s
    }

    # Block debug endpoints
    @debug path /docs /redoc /openapi.json
    respond @debug 404

    # Compression
    encode gzip

    # Access log
    log {
        output file /var/log/caddy/draco-metric.log
        format json
    }
}
```

### With Rate Limiting

Caddy supports rate limiting via the `rate_limit` directive (requires the rate limit module):

```
api.example.com {
    rate_limit {remote.ip} 100r/m

    reverse_proxy 127.0.0.1:8000 {
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }
}
```

### Running Caddy

```bash
# With Caddyfile in current directory
caddy run

# Or as a systemd service
sudo systemctl enable --now caddy
```

Caddy automatically obtains and renews TLS certificates from Let's Encrypt.

---

## OpenBSD relayd

### relayd.conf

```
# Macros
ext_addr = "egress"
draco_addr = "127.0.0.1"
draco_port = "8000"

# HTTP redirect to HTTPS
http protocol "http_redirect" {
    return code 301 location "https://$HOST$REQUEST_URI"
}

# HTTPS protocol definition
http protocol "https_draco" {
    # TLS configuration
    tls { no tlsv1.0, no tlsv1.1, ciphers "HIGH:!aNULL:!MD5" }

    # Pass headers
    match request header append "X-Forwarded-For" value "$REMOTE_ADDR"
    match request header append "X-Forwarded-Proto" value "https"

    # Block debug endpoints
    match request path "/docs" forward to <blocked>
    match request path "/redoc" forward to <blocked>
    match request path "/openapi.json" forward to <blocked>

    # Health check
    match request path "/health" forward to <draco>
}

# Relay definitions
relay "http_redirect" {
    listen on $ext_addr port 80
    protocol "http_redirect"
    forward to <draco> port $draco_port
}

relay "https_draco" {
    listen on $ext_addr port 443 tls
    protocol "https_draco"
    forward to <draco> port $draco_port check http "/health" code 200
}

# Tables
table <draco> { $draco_addr }
table <blocked> disable
```

### TLS Certificates

Place your certificates:

```bash
# Certificate
/etc/ssl/api.example.com.pem

# Private key
/etc/ssl/private/api.example.com.key
```

Or use `acme-client(1)` for Let's Encrypt:

```bash
# /etc/acme-client.conf
authority letsencrypt {
    api url "https://acme-v02.api.letsencrypt.org/directory"
    account key "/etc/acme/letsencrypt-privkey.pem"
}

domain api.example.com {
    domain key "/etc/ssl/private/api.example.com.key"
    domain full chain certificate "/etc/ssl/api.example.com.pem"
    sign with letsencrypt
}
```

### Enable and start

```bash
rcctl enable relayd
rcctl start relayd
```

### Verify

```bash
rcctl check relayd
relayctl show relays
```

---

## Common Configuration

Regardless of which reverse proxy you use, ensure:

1. **`TRUSTED_HOSTS`** in `.env` includes your proxy's IP
2. **`X-Forwarded-For`** header is set by the proxy
3. **TLS 1.2+** is enforced
4. **uvicorn** binds to `127.0.0.1` (not `0.0.0.0`)
5. **Debug endpoints** (`/docs`, `/redoc`, `/openapi.json`) are blocked at the proxy level as a defense-in-depth measure (they are already disabled when `DEBUG=false`)
6. **`/health`** endpoint is accessible for monitoring without auth
