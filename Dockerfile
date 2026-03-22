# =============================================================================
# (c) Clearview Geographic LLC -- All Rights Reserved | Est. 2018
# CVG Rainfall Wizard — Docker Image
# Author: Alex Zelenski, GISP | azelenski@clearviewgeographic.com
# =============================================================================
# ── Stage 1: builder — has C++ compiler to build GDAL Python bindings ────────
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install all Python deps (including GDAL from source) into /wheels
# • rasterio/fiona/shapely/pyproj use pre-built cp312 manylinux wheels
# • GDAL=={GDAL_VER} is compiled here against the system GDAL headers;
#   build-essential provides g++ so the C++ extension sources compile cleanly.
COPY requirements-lock.txt ./
RUN set -e && \
    GDAL_VER=$(gdal-config --version) && \
    grep -v '^GDAL==' requirements-lock.txt > /tmp/reqs_nogdal.txt && \
    pip install --no-cache-dir --prefix=/install -r /tmp/reqs_nogdal.txt && \
    pip install --no-cache-dir --prefix=/install "GDAL==${GDAL_VER}"

# ── Stage 2: runtime — slim image; no build tools, just the compiled libs ─────
FROM python:3.12-slim AS base

LABEL maintainer="Alex Zelenski, GISP <azelenski@clearviewgeographic.com>"
LABEL org.opencontainers.image.title="CVG Rainfall Wizard"
LABEL org.opencontainers.image.description="NOAA Atlas 14 Rainfall Depth Grid Wizard"
LABEL org.opencontainers.image.vendor="Clearview Geographic LLC"
LABEL org.opencontainers.image.licenses="Proprietary"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/usr/local/lib/python3.12/site-packages

# Runtime system libraries — GDAL shared libs required at runtime by osgeo.*
# No build tools (g++, make, etc.) needed in the final image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy compiled Python packages from builder stage
COPY --from=builder /install/lib /usr/local/lib
COPY --from=builder /install/bin /usr/local/bin

WORKDIR /app

# Install package — skip pyproject dep resolution to avoid attempting to
# install unpublished internal packages (storm-surge-wizard) from PyPI
COPY . .
RUN pip install --no-cache-dir -e ".[web]" --no-deps

RUN useradd -m -u 1001 rfwiz && chown -R rfwiz:rfwiz /app
USER rfwiz

RUN mkdir -p /app/output

EXPOSE 8020

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -fsS http://localhost:8020/health | grep -q '"ok"' || exit 1

CMD ["uvicorn", "rainfall_wizard.web_api:create_app", \
     "--factory", "--host", "0.0.0.0", "--port", "8020", \
     "--workers", "2", "--log-level", "info"]
