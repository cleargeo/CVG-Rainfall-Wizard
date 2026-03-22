# CVG Rainfall Wizard — Master Changelog

> © Clearview Geographic LLC | Author: Alex Zelenski, GISP

Format follows [Keep a Changelog](https://keepachangelog.com/).

---

## [Unreleased]

*(Future changes go here)*

---

## [2026-03-21] – Session 6 – Production Deployment Verification

**ChangeID:** `20260321-AZ-Deploy-Session6`

**Scope:** Deployment verification — no application code changes.

**Verified:**

| Endpoint | Status | Version |
|---|---|---|
| https://rainfall.cleargeo.tech/health | ✅ 200 OK | v1.1.0 |

- `cvg-rainfall` Docker container on VM 451 (cvg-stormsurge-01, 10.10.10.200) confirmed healthy
- Serving correctly through Caddy reverse proxy on `cvg_net` Docker network
- All three CVG wizard applications verified live as part of platform health check

**Author:** Alex Zelenski, GISP  
**Approved by:** Alex Zelenski  
**Status:** ✅ Production

---

## [1.0.0] — 2026-03-19

**ChangeID**: `20260319-AZ-v1.0.0`
**Author**: Alex Zelenski, GISP

### Added
- Initial framework release of CVG Rainfall Wizard
- `rainfall_wizard` Python package with 14 modules
- **NOAA PFDS/Atlas 14 client** (`noaa.py`): live fetch + JSON cache + CSV fallback; `PrecipFreqEstimate`, `PFDSResponse`, `fetch_pfds()`, `fetch_single_pfe()`, `get_pfds_cached()`
- **IDF curves & hyetographs** (`idf.py`): SCS Type I/IA/II/III mass curves (TR-55 App. B); alternating block method; `build_scs_hyetograph()`, `build_alternating_block_hyetograph()`; Chen (1983) IDF curve fitting
- **NRCS CN runoff** (`runoff.py`): TR-55 CN equation; composite CN; TR-55 CN lookup table; TC (sheet, shallow concentrated, channel); TR-55 tabular peak discharge; Rational method
- **Depth grid processing** (`processing.py`): `run_rainfall_analysis()`, `run_batch()`, PFDS fetch → CN runoff → GeoTIFF output; checkpoint/resume integration
- **Configuration** (`config.py`): `RainfallConfig`, `CompoundFloodConfig` dataclasses with full field documentation
- **Checkpoint/resume** (`recovery.py`): 9-stage pipeline
- **JSON + PDF reports** (`report.py`): schema v1.0.0; reportlab PDF
- **Knowledge base** (`insights.py`): 7 topics (Atlas 14, return period, CN, storm types, IDF, climate change, compound floods)
- **CLI** (`cli.py`): `rainfall-wizard run|batch|pfds|web|insights`
- **FastAPI REST API** (`web_api.py`): 6 endpoints including `/api/runoff` calculator
- **Raster I/O** (`io.py`), **Monitoring** (`monitoring.py`), **Paths** (`paths.py`), **Web** (`web.py`)
- Unit test suite: `test_runoff.py` (17 tests), `test_idf.py` (13 tests)
- Docker, docker-compose, .gitignore, pytest.ini, requirements-lock.txt
- README, ROADMAP, CONTRIBUTING, SECURITY, LICENSE

### References
- Perica et al. (2011–2019). NOAA Atlas 14 Precipitation-Frequency Atlas of the United States.
- USDA-NRCS (1986). TR-55 Urban Hydrology for Small Watersheds, 2nd Edition.


---

## [2026-03-20] – v1.1.0 – Docker Hardening + Full Test Parity

**ChangeID:** `20260320-AZ-v1.1.0`

**Modified Files:**

| File | Change Summary |
|---|---|
| `Dockerfile` | Base image `python:3.11-slim` -> `python:3.13-slim` (matches SSW) |
| `pyproject.toml` | FastAPI moved from optional `[web]` extras to mandatory `[project.dependencies]`; added fiona, psutil; version 1.0.0->1.1.0 |
| `rainfall_wizard/__init__.py` | Fixed stale docstring referencing SSW DEM engine; updated to reflect standalone status |
| `rainfall_wizard/web_api.py` | Added `GET /api/wizards/status` endpoint for cross-wizard discovery |
| `tests/test_monitoring.py` | NEW: 34 tests covering ResourceSnapshot, take_snapshot, PerformanceTracker, timed_stage |
| `tests/test_recovery.py` | NEW: 31 tests covering Stage enum, CheckpointManager, build_cache_key |
| `tests/test_report.py` | NEW: 25 tests covering report constants, build_json_report, write_json_report, write_pdf_report |
| `tests/test_web_api.py` | NEW: 25 tests covering GET /, GET /api/pfds, GET /api/runoff, GET /api/insights, GET /api/wizards/status, POST /api/run |
| `05_ChangeLogs/master_changelog.md` | Added v1.1.0 entry |

**Summary:**

- Dockerfile updated to Python 3.13-slim for consistency with Storm Surge Wizard
- FastAPI is now a mandatory dependency (not optional extras)
- 266 total tests passing (was 151 before this release)
- Full header compliance with CVG File Authorship Requirement

**Tests:** 266 passed

**Approved By:** Alex Zelenski, GISP  
**Review Status:** Internal — Production Ready

---

## [2026-03-21] – v1.1.1 – Docker Build Fix + Landing Page Genericization

**ChangeID:** `20260321-AZ-v1.1.1`

**Modified Files:**

| File | Change Summary |
|---|---|
| `Dockerfile` | `requirements-lock.txt` → `requirements-web.txt` — eliminates yanked `numpy==2.0.0rc1` RC build failure via rasterio build dependency; web API requires only `fastapi`, `uvicorn`, `pydantic`, `reportlab`, `numpy>=1.26.0` (no GDAL/rasterio). Applied on VM 451 + locally (G: drive) |
| `requirements-web.txt` | Verified: `fastapi>=0.111.0`, `uvicorn[standard]>=0.29.0`, `pydantic>=2.8.0`, `python-multipart>=0.0.9`, `jinja2>=3.1.0`, `httpx>=0.27.0`, `click>=8.1.0`, `psutil>=5.9.0`, `reportlab>=4.1.0`, `numpy>=1.26.0` |
| `static/landing/rainfall-index.html` | Removed all Monroe County / client-specific content; replaced with generic CVG product-selling copy — hero "Stormwater Precipitation Analysis for Any U.S. Location", NOAA Atlas 14 PFDS feature table (6 return periods × 5 durations), NRCS CN runoff, pricing `$2,500–$10,000`, FEMA BRIC/HMGP grant hook, `services@clearviewgeographic.com` CTA, DeLand FL footer, `cleargeo.tech/products.html` |
| `05_ChangeLogs/master_changelog.md` | Added this entry |
| `05_ChangeLogs/version_manifest.yml` | Bumped `current_version` to 1.1.1; added v1.1.1 release entry |
| `README.md` | Version header + badge bumped to v1.1.1 |

**Deployment:**

- `cvg-rainfall-wizard:latest` Docker image rebuilt on VM 451 (390 MB, Python 3.13-slim)
- `cvg-rainfall` container restarted and verified healthy ✅ (Up 32 min at verification)
- Landing page deployed: `/opt/cvg-platform/static/rainfall/index.html` (31,528 bytes)
- Verified: 0 Monroe County / client-specific references (grep)

**Author:** Alex Zelenski, GISP  
**Approved by:** Alex Zelenski  
**Status:** ✅ Production
