# CVG Rainfall Wizard — Web Deployment Guide

> © Clearview Geographic LLC | Internal Use Only | CVG-ADF

---

## Overview

This document covers deploying the CVG Rainfall Wizard API (`rainfall-wizard`) as a production
web service on a CVG Ubuntu 22.04 LXC container or VM.

- **Service port:** 8020 (API) | 8040 (Portal dashboard)
- **Target domain:** `rainfall.cleargeo.tech`
- **Reverse proxy:** Caddy 2 (automatic TLS via Let's Encrypt)
- **Process manager:** systemd (`cvg-rainfall-wizard.service`)

---

## Prerequisites

| Requirement | Version |
|---|---|
| Ubuntu | 22.04 LTS |
| Python | 3.10+ |
| pip | 23+ |
| Docker (optional) | 24+ |
| Caddy | 2.7+ |

CGPS share mounted at `/mnt/cgps` with the project files.

---

## 1. Bootstrap Script

Run the automated bootstrap from the project root:

```bash
bash scripts/bootstrap_rainfall_vm.sh
```

This will:
1. Install system dependencies (python3, pip, caddy, git)
2. Mount the CGPS SMB share
3. rsync the project files
4. Create Python virtual environment at `/opt/rainfall-wizard/venv`
5. Install `rainfall-wizard` package (including `scipy`, `numpy`)
6. Install and enable the `cvg-rainfall-wizard.service` systemd unit
7. Start Caddy with the `caddy/Caddyfile` config

---

## 2. Manual Deployment Steps

### 2.1 Create service user

```bash
sudo useradd -r -s /bin/false -d /opt/rainfall-wizard rfwiz
sudo mkdir -p /opt/rainfall-wizard
sudo chown rfwiz:rfwiz /opt/rainfall-wizard
```

### 2.2 Install package

```bash
sudo -u rfwiz python3 -m venv /opt/rainfall-wizard/venv
sudo -u rfwiz /opt/rainfall-wizard/venv/bin/pip install --upgrade pip
sudo -u rfwiz /opt/rainfall-wizard/venv/bin/pip install \
    "rainfall-wizard>=1.0.0" "fastapi>=0.110" "uvicorn[standard]>=0.29" \
    "scipy>=1.12" "numpy>=1.26"
```

### 2.3 Create systemd service

`/etc/systemd/system/cvg-rainfall-wizard.service`:

```ini
[Unit]
Description=CVG Rainfall Wizard API
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=rfwiz
Group=rfwiz
WorkingDirectory=/opt/rainfall-wizard
ExecStart=/opt/rainfall-wizard/venv/bin/uvicorn rainfall_wizard.web_api:app \
    --host 0.0.0.0 --port 8020 --workers 2 --log-level info
Restart=always
RestartSec=5
Environment=RAINFALL_WIZARD_ENV=production
Environment=RAINFALL_WIZARD_CACHE_DIR=/opt/rainfall-wizard/cache
StandardOutput=journal
StandardError=journal
SyslogIdentifier=cvg-rainfall-wizard

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable cvg-rainfall-wizard
sudo systemctl start cvg-rainfall-wizard
sudo systemctl status cvg-rainfall-wizard
```

### 2.4 Caddy reverse proxy

`/etc/caddy/Caddyfile` (or use `caddy/Caddyfile` from the project):

```caddy
rainfall.cleargeo.tech {
    reverse_proxy localhost:8020

    encode gzip

    header {
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
    }

    log {
        output file /var/log/caddy/rainfall-access.log
    }
}
```

```bash
sudo systemctl reload caddy
```

---

## 3. Docker Deployment

### 3.1 Build and run

```bash
# Build the image
docker build -t cvg-rainfall-wizard:latest .

# Run production container
docker compose -f docker-compose.prod.yml up -d
```

### 3.2 `docker-compose.prod.yml` key settings

```yaml
services:
  rainfall-api:
    image: cvg-rainfall-wizard:latest
    ports:
      - "8020:8020"
    environment:
      - RAINFALL_WIZARD_ENV=production
      - RAINFALL_WIZARD_CACHE_DIR=/cache
    volumes:
      - rainfall-cache:/cache
      - /data/dem:/data/dem:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8020/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## 4. PFDS Cache Warm-Up

Pre-populate the Atlas 14 cache for your service area before going live:

```bash
# Warm cache for South Florida (Monroe + Miami-Dade + Broward)
/opt/rainfall-wizard/venv/bin/python tools/cache_pfds_bulk.py \
    --county "Monroe,FL" --spacing 0.05 --delay 0.3 \
    --cache-dir /opt/rainfall-wizard/cache/pfds

/opt/rainfall-wizard/venv/bin/python tools/cache_pfds_bulk.py \
    --county "Miami-Dade,FL" --spacing 0.05 --delay 0.3 \
    --cache-dir /opt/rainfall-wizard/cache/pfds
```

Cached JSON files expire only when manually purged — no TTL by default.
For projects with known geographic scope, this eliminates NOAA PFDS round-trips.

---

## 5. Operations

### Health check

```bash
curl http://localhost:8020/health
# {"status": "ok", "uptime_s": 1234.5}
```

### View logs

```bash
journalctl -u cvg-rainfall-wizard -f
# or Docker:
docker compose logs -f rainfall-api
```

### Restart service

```bash
sudo systemctl restart cvg-rainfall-wizard
```

### Test a PFDS lookup

```bash
curl -s -X POST http://localhost:8020/pfds \
  -H "Content-Type: application/json" \
  -d '{"lat":25.7617,"lon":-80.1918,"duration_hr":24,"return_period_yr":100}' \
  | python3 -m json.tool
```

### Test CN runoff

```bash
curl -s -X POST http://localhost:8020/runoff \
  -H "Content-Type: application/json" \
  -d '{"lat":25.7617,"lon":-80.1918,"curve_number":82,"storm_type":"II","return_period_yr":100}' \
  | python3 -m json.tool
```

---

## 6. Monitoring

The API exposes a `/metrics` endpoint (Prometheus format). Key metrics:

| Metric | Description |
|---|---|
| `rfw_requests_total` | Total API requests |
| `rfw_request_duration_seconds` | Request latency histogram |
| `rfw_pfds_fetch_errors_total` | NOAA PFDS fetch failures |
| `rfw_pfds_cache_hits_total` | PFDS cache hits |
| `rfw_runoff_computations_total` | CN runoff analyses |
| `rfw_idf_requests_total` | IDF table requests |

---

## 7. Security Notes

- Run as unprivileged user (`rfwiz`, UID 1001) — never as root
- PFDS cache contains publicly available NOAA data — no sensitive info
- DEM volumes mounted **read-only** (`ro`)
- Caddy handles TLS — do not expose port 8020 to the public internet directly
- The NOAA PFDS API is a public endpoint; rate-limit outbound requests with `--delay`

---

## 8. File Paths (Production)

| Path | Purpose |
|---|---|
| `/opt/rainfall-wizard/venv/` | Python virtual environment |
| `/opt/rainfall-wizard/cache/pfds/` | NOAA PFDS Atlas 14 cache |
| `/data/dem/` | DEM raster inputs (read-only mount) |
| `/output/` | Analysis output files |
| `/var/log/caddy/rainfall-access.log` | Request access log |
| `/etc/systemd/system/cvg-rainfall-wizard.service` | systemd unit |

---

*See also: `scripts/bootstrap_rainfall_vm.sh`, `Dockerfile`, `docker-compose.prod.yml`*
*Reference: NOAA Atlas 14 (Perica et al. 2011–2019); USDA-NRCS TR-55 (1986)*
