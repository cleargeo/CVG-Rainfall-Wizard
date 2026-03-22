# =============================================================================
# (c) Clearview Geographic LLC -- All Rights Reserved | Est. 2018
# CVG Rainfall Wizard — Docker Image
# Author: Alex Zelenski, GISP | azelenski@clearviewgeographic.com
# =============================================================================
FROM python:3.12-slim AS base

LABEL maintainer="Alex Zelenski, GISP <azelenski@clearviewgeographic.com>"
LABEL org.opencontainers.image.title="CVG Rainfall Wizard"
LABEL org.opencontainers.image.description="NOAA Atlas 14 Rainfall Depth Grid Wizard"
LABEL org.opencontainers.image.vendor="Clearview Geographic LLC"
LABEL org.opencontainers.image.licenses="Proprietary"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System dependencies — libgdal-dev for GDAL Python bindings;
# rasterio / fiona use their own bundled manylinux wheels on Python 3.12
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps from lock file.
# • rasterio/fiona/shapely/pyproj use pre-built cp312 manylinux wheels
# • GDAL==3.8.4 is replaced at build time with the system-GDAL version
#   (Debian bookworm ships GDAL 3.6.x; prevents header mismatch failures)
COPY requirements-lock.txt ./
RUN set -e && \
    GDAL_VER=$(gdal-config --version) && \
    grep -v '^GDAL==' requirements-lock.txt > /tmp/reqs_nogdal.txt && \
    pip install --no-cache-dir -r /tmp/reqs_nogdal.txt && \
    pip install --no-cache-dir "GDAL==${GDAL_VER}"

# Install package — skip pyproject dep resolution to avoid attempting to
# install unpublished internal packages (storm-surge-wizard) from PyPI
COPY . .
RUN pip install --no-cache-dir -e ".[web]" --no-deps

RUN useradd -m -u 1001 rfwiz && chown -R rfwiz:rfwiz /app
USER rfwiz

RUN mkdir -p /app/output

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -fsS http://localhost:8002/health | grep -q '"ok"' || exit 1

CMD ["uvicorn", "rainfall_wizard.web_api:create_app", \
     "--factory", "--host", "0.0.0.0", "--port", "8002", \
     "--workers", "2", "--log-level", "info"]
