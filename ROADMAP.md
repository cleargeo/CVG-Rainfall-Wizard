<!--
  © Clearview Geographic LLC -- All Rights Reserved | Est. 2018
  CVG Rainfall Wizard — ROADMAP
-->

# CVG Rainfall Wizard — Development Roadmap

> Version: v1.1.1 | Author: Alex Zelenski, GISP | Last updated: 2026-03-21 (Session 7) — GeoServer Raster & Vector integration section added

---

## ✅ v1.1.1 — Docker Fix + Landing Page Genericization (2026-03-21)

- [x] `Dockerfile`: `requirements-lock.txt` → `requirements-web.txt` (fixed yanked `numpy==2.0.0rc1` RC via rasterio)
- [x] `static/landing/rainfall-index.html`: removed Monroe County / client-specific content; CVG product-selling copy
- [x] Docker image rebuilt (390 MB, Python 3.13-slim); `cvg-rainfall` container restarted and verified healthy

## ✅ v1.1.0 — Docker Hardening + Test Parity (2026-03-20)

- [x] Base image `python:3.11-slim` → `python:3.13-slim`
- [x] FastAPI moved to mandatory dependencies
- [x] 266 tests passing (monitoring, recovery, report, web_api test suites added)
- [x] CVG File Authorship Requirement headers on all source files

## ✅ v1.0.0 — Initial Framework (2026-03-19)

- [x] Core package: `__init__`, `config`, `paths`, `monitoring`, `io`, `recovery`
- [x] NOAA PFDS/Atlas 14 client (`noaa.py`): live fetch + JSON cache, CSV fallback
- [x] IDF curves and design storm hyetographs (`idf.py`): SCS Type I/IA/II/III, alternating block
- [x] NRCS CN runoff calculations (`runoff.py`): TR-55 CN equation, Tc methods, rational method
- [x] Rainfall depth grid processing engine (`processing.py`): CN bathtub, batch mode
- [x] JSON + PDF report generation (`report.py`)
- [x] Knowledge base (`insights.py`): 7 guidance topics (Atlas 14, CN, IDF, climate)
- [x] CLI (`cli.py`): `run`, `batch`, `pfds`, `web`, `insights`
- [x] FastAPI REST API (`web_api.py`): 6 endpoints
- [x] Jinja2 web rendering (`web.py`)
- [x] Unit test suite: runoff, idf
- [x] Docker / docker-compose, .gitignore, README

---

## 🔜 v1.2.0 — PFDS Coverage & Compound Config

- [ ] Complete `CompoundFloodConfig` implementation in processing engine
- [ ] NOAA Atlas 14 v2 (PFDS upgrade) when published
- [ ] Support for NOAA Atlas 2 (western US legacy regions)
- [ ] Offline pre-cached Atlas 14 tables for Southeast US (FL, GA, SC, NC, VA)
- [ ] More Atlas 14 duration: 5-min, 10-min, 15-min sub-hourly

---

## 🔜 v1.3.0 — Spatial Runoff Routing

- [ ] IDF grid download from NOAA PFDS for AOI bounding box
- [ ] Spatially varying CN raster from NLCD land cover + SSURGO HSG
- [ ] CN to runoff grid: cell-by-cell CN × rainfall → runoff depth grid
- [ ] Simple DEM-based ponding map vs. runoff depth from CN bathtub

---

## 🔜 v1.4.0 — Hydrograph & Peak Discharge

- [ ] SCS unit hydrograph routing on watershed DEM
- [ ] TR-20 multi-reach routing
- [ ] Green-Ampt infiltration alternative to CN method
- [ ] NRCS dimensionless unit hydrograph peak discharge (qp tabular)

---

## 🔜 v1.5.0 — Web UI & Visualization

- [ ] Interactive Leaflet map for depth grid
- [ ] IDF chart widget (Chart.js)
- [ ] CN picker by land cover type and HSG
- [ ] Return period comparison table

---

## 🔜 v2.0.0 — Full Integration

- [ ] ArcGIS toolbox / QGIS Processing plugin
- [ ] Integration with `slr_wizard` for compound rainfall + SLR blocked-outlet scenario
- [ ] Integration with `storm_surge_wizard` for compound surge + rainfall
- [ ] Climate-adjusted Atlas 14 multipliers configurable by region
- [ ] Scheduled daily monitoring (observed vs. design rainfall alert)

---

## 🔜 v2.1.0 — GeoServer Raster & Vector Integration

> **Platform:** CVG GeoServer Raster (VM 454 · **raster.cleargeo.tech**) + GeoServer Vector (VM 455 · **vector.cleargeo.tech**)
> GeoServer 2.28.3 · Caddy 2-alpine TLS · Watchtower daily pull · NAS mounts `/mnt/cgps` + `/mnt/cgdp`

### Raster Integration (raster.cleargeo.tech — WMS/WCS)

- [ ] **COG export**: after each `processing.py` run, convert runoff depth grid to Cloud-Optimized GeoTIFF:
  `gdal_translate -of COG depth_grid.tif /mnt/cgdp/cogs/rainfall/{project}/{event}.tif`
- [ ] Register COG as WCS coverage on `raster.cleargeo.tech` — workspace `cvg`, layer `cvg:rain_{project}_{event}`
- [ ] `GET /api/layers/raster` endpoint in `web_api.py` — returns WCS GetCapabilities URL + available depth grid layers
- [ ] Leaflet map in `web.py`: replace static PNG with `L.tileLayer.wms()` consuming `raster.cleargeo.tech`
- [ ] GeoWebCache WMTS for fast tile delivery at zoom 10–14 (target < 200 ms tile response)

### Vector Integration (vector.cleargeo.tech — WFS)

- [ ] **SSURGO HSG layers**: register Hydrologic Soil Group polygon boundaries from `/mnt/cgps/ssurgo/`
  as WFS layer `cvg:ssurgo_hsg_{state}` — used for CN map overlays
- [ ] **NLCD land cover**: register NLCD classification boundaries (joined to CN lookup table)
  as WFS layer `cvg:nlcd_{year}_{region}`
- [ ] **Drainage basin/catchment**: export delineated basins from `processing.py` to GeoPackage;
  register on Vector GeoServer as `cvg:basin_{project}`
- [ ] `GET /api/layers/vector` endpoint in `web_api.py` — returns WFS GetCapabilities URL + available layers

### Cross-Wizard Layer Registry

- [ ] `GET /api/platform/layers` — lists all active WMS/WCS/WFS layers across SSW, SLR, and Rainfall
  (consumed by future CVG unified map portal)

### Layer Naming Convention

| Layer Type | Pattern | Example |
|---|---|---|
| Runoff depth grid (WCS) | `cvg:rain_{project}_{event}` | `cvg:rain_orlando_100yr` |
| SSURGO HSG boundaries (WFS) | `cvg:ssurgo_hsg_{state}` | `cvg:ssurgo_hsg_fl` |
| NLCD land cover (WFS) | `cvg:nlcd_{year}_{region}` | `cvg:nlcd_2021_se` |
| Drainage basin (WFS) | `cvg:basin_{project}` | `cvg:basin_orlando` |

### Infrastructure Reference

| Service | VM | Hostname | Purpose |
|---|---|---|---|
| GeoServer Raster | VM 454 · 10.10.10.203 | raster.cleargeo.tech | WMS/WCS/WMTS for runoff depth grids |
| GeoServer Vector | VM 455 · 10.10.10.204 | vector.cleargeo.tech | WFS for SSURGO, NLCD, basins |

---

*© Clearview Geographic LLC — Proprietary — All Rights Reserved*
