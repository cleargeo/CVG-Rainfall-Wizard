<!--
  © Clearview Geographic LLC -- All Rights Reserved | Est. 2018
  Proprietary Software -- Internal Use Only
  Author      : Alex Zelenski, GISP
  Organization: Clearview Geographic, LLC
  Contact     : azelenski@clearviewgeographic.com | 386-957-2314
  Website     : https://www.clearviewgeographic.com
  License     : Proprietary -- CVG-ADF
  Version     : v1.1.1 | ChangeID: 20260321-AZ-v1.1.1
-->

# CVG Rainfall Wizard

> **© Clearview Geographic LLC** — Proprietary | Author: Alex Zelenski, GISP
> `azelenski@clearviewgeographic.com` | 386-957-2314 | [clearviewgeographic.com](https://www.clearviewgeographic.com)
> **Version:** v1.1.1 | **License:** Proprietary – CVG-ADF | **ChangeID:** `20260321-AZ-v1.1.1`

A Python toolkit for building **rainfall flood depth grids** (GeoTIFF) by combining:
- NOAA Atlas 14 Precipitation Frequency Estimates (PFDS API)
- NRCS Curve Number (CN) runoff calculations (TR-55)
- SCS design storm hyetographs (Type I, IA, II, III)
- A Digital Elevation Model (DEM)

---

## Features

| Feature | Details |
|---|---|
| **NOAA Atlas 14 PFDS** | Live fetch or cached PFEs for any CONUS lat/lon |
| **SCS Hyetographs** | Type I, IA, II, III mass curves; alternating block method |
| **NRCS CN Runoff** | TR-55 CN equation with Ia=0.2S or 0.05S (urban) |
| **IDF Curves** | Chen (1983) three-parameter fit from Atlas 14 data |
| **Composite CN** | Area-weighted composite from land use × HSG |
| **TR-55 Peak Discharge** | Unit peak discharge method (Tc-based) |
| **Batch Mode** | All standard return periods (1–1000 yr) in sequence |
| **JSON + PDF Reports** | Structured reports with full provenance |
| **FastAPI Web UI** | REST API on port 8020 + Swagger docs |
| **Checkpoint/Resume** | Interrupt and resume long runs |
| **Knowledge Base** | 7 built-in guidance topics (Atlas 14, CN, IDF, climate) |

---

## Quick Start

### CLI

```bash
# Single 100-yr / 24-hr run
rainfall-wizard run 29.65 -82.32 \
    --dem my_dem.tif --rp 100 --dur 24 --cn 75

# Fetch NOAA Atlas 14 data for a point
rainfall-wizard pfds 29.65 -82.32 --dur 24

# Run all standard return periods (1–1000 yr)
rainfall-wizard batch 29.65 -82.32 --dem my_dem.tif --dur 24 --cn 75

# Start web server
rainfall-wizard web --port 8020

# Search knowledge base
rainfall-wizard insights curve number
```

### Python API

```python
from rainfall_wizard.config import RainfallConfig
from rainfall_wizard.processing import run_rainfall_analysis

cfg = RainfallConfig(
    lat=29.65, lon=-82.32,
    duration_hr=24.0,
    return_period_yr=100,
    curve_number=75.0,
    dem_path="my_dem.tif",
    dem_unit="m",
    output_path="output/100yr_24hr_depth.tif",
)
result = run_rainfall_analysis(cfg)
print(f"Rainfall: {result.rainfall_depth_in:.2f} in  Runoff: {result.runoff_depth_in:.2f} in")
```

### Direct PFDS Lookup

```python
from rainfall_wizard.noaa import fetch_pfds

resp = fetch_pfds(lat=29.65, lon=-82.32)
pfe = resp.get(duration_hr=24.0, return_period_yr=100)
print(f"100-yr / 24-hr depth: {pfe.depth_in:.2f} in")
```

### NRCS Runoff Calculation

```python
from rainfall_wizard.runoff import compute_runoff

result = compute_runoff(rainfall_in=6.5, cn=80)
print(f"Runoff: {result.runoff_depth_in:.2f} in  ({result.runoff_fraction*100:.0f}%)")
```

### SCS Hyetograph

```python
from rainfall_wizard.idf import build_scs_hyetograph, STORM_TYPE_II

hyet = build_scs_hyetograph(total_depth_in=6.5, duration_hr=24, storm_type=STORM_TYPE_II)
print(f"Peak intensity: {hyet.peak_intensity_in_hr:.3f} in/hr at t={hyet.time_to_peak_hr:.1f} hr")
```

---

## NOAA Atlas 14 Standard Returns / Durations

| Return Period | AEP | Design Use |
|---|---|---|
| 2-yr | 50% | Nuisance flooding; minor drainage |
| 10-yr | 10% | Minor conveyance; street drainage |
| 25-yr | 4% | Storm sewer design |
| **100-yr** | **1%** | **FEMA BFE; floodplain management** |
| 500-yr | 0.2% | Critical facilities; dams |
| 1000-yr | 0.1% | Nuclear / extreme consequence |

---

## NRCS CN Reference (TR-55 Table 2-2, HSG B)

| Land Cover | CN (HSG-B) | CN (HSG-D) |
|---|---|---|
| Dense forest / wetlands | 55 | 77 |
| Open space / parks | 61 | 80 |
| Low-density residential | 70 | 85 |
| Commercial / strip malls | 92 | 95 |
| Parking lots / impervious | 98 | 98 |

---

## Configuration (Python dataclass)

```python
from rainfall_wizard.config import RainfallConfig

cfg = RainfallConfig(
    lat=29.65,              # Site latitude
    lon=-82.32,             # Site longitude
    duration_hr=24.0,       # Storm duration (hr)
    return_period_yr=100,   # Return period (yr)
    curve_number=75.0,      # NRCS CN
    dem_path="dem.tif",
    dem_unit="m",           # "m" or "ft"
    output_path="output/depth.tif",
    output_unit="ft",
    min_depth=0.0,
    pfds_timeout=30.0,
)
```

---

## Docker

```bash
docker compose up --build
# API: http://localhost:8020
# Docs: http://localhost:8020/docs
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Health check |
| GET | `/api/pfds?lat=29.65&lon=-82.32&duration_hr=24&return_period_yr=100` | Single PFE |
| GET | `/api/pfds/table?lat=29.65&lon=-82.32` | Full PFDS table |
| POST | `/api/run` | Run depth grid |
| GET | `/api/runoff?rainfall_in=6.5&cn=80` | CN runoff calc |
| GET | `/api/insights?q=curve+number` | Knowledge base search |

---

## References

> Perica, S. et al. (2011–2019). *NOAA Atlas 14 Precipitation-Frequency Atlas of the United States.* NOAA, National Weather Service. Silver Spring, MD.
> https://hdsc.nws.noaa.gov/pfds/

> USDA-NRCS (1986). *Urban Hydrology for Small Watersheds.* Technical Release 55 (TR-55), 2nd Edition.

---

*© Clearview Geographic LLC — Proprietary Software — All Rights Reserved*
*Unauthorized use, replication, or modification is strictly prohibited.*
