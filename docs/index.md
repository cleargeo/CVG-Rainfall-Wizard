# CVG Rainfall Wizard — Documentation

> © Clearview Geographic LLC | Author: Alex Zelenski, GISP | v1.0.0

---

## Overview

The CVG Rainfall Wizard builds **rainfall flood depth grids** (GeoTIFF) using:
- NOAA Atlas 14 Precipitation Frequency Estimates (PFDS REST API)
- NRCS Curve Number runoff method (TR-55)
- SCS design storm hyetographs

---

## Module Reference

### `rainfall_wizard.config`
```python
RainfallConfig(lat, lon, duration_hr, return_period_yr, curve_number, dem_path, ...)
CompoundFloodConfig(storm_surge_wse_ft, rainfall_runoff_ft, slr_ft, ...)
```

### `rainfall_wizard.noaa`
NOAA Atlas 14 PFDS client.

| Function | Description |
|---|---|
| `fetch_pfds(lat, lon)` | Fetch all PFEs for a point |
| `fetch_single_pfe(lat, lon, duration_hr, rp)` | Single estimate |
| `get_pfds_cached(lat, lon)` | Cached fetch |
| `PrecipFreqEstimate` | Single depth/intensity dataclass |
| `PFDSResponse.idf_table()` | `{rp: {dur_hr: intensity_in_hr}}` |

**Standard return periods**: 1, 2, 5, 10, 25, 50, 100, 200, 500, 1000 yr
**Standard durations**: 5 min to 30 days

---

### `rainfall_wizard.idf`
IDF curves and design storm hyetographs.

| Function | Description |
|---|---|
| `build_scs_hyetograph(depth, dur, storm_type)` | SCS mass curve hyetograph |
| `build_alternating_block_hyetograph(idf, dur)` | Alternating block method |
| `fit_idf_chen(idf_points)` | Chen (1983) IDF curve fit |

**Storm types**: `SCS_I`, `SCS_IA`, `SCS_II`, `SCS_III`, `alt_block`

---

### `rainfall_wizard.runoff`
NRCS CN runoff calculations.

| Function | Description |
|---|---|
| `cn_runoff_depth(rainfall_in, cn)` | TR-55 CN equation |
| `cn_runoff_series(series, cn)` | Incremental runoff series |
| `composite_cn(land_covers)` | Area-weighted CN |
| `lookup_cn(cover_type, hsg)` | TR-55 table lookup |
| `tc_sheet_flow(...)` | TR-55 sheet flow Tc |
| `tc_shallow_concentrated(...)` | Shallow concentrated flow Tc |
| `peak_discharge_tr55(...)` | TR-55 tabular peak discharge |
| `peak_discharge_rational(C, i, A)` | Rational method Q=CiA |
| `compute_runoff(rainfall_in, cn)` | Full result → `RunoffResult` |

---

### `rainfall_wizard.processing`
```python
result = run_rainfall_analysis(config)   # single return period
results = run_batch(config, [10, 25, 100, 500])  # batch
```
Returns `RainfallDepthResult` with `rainfall_depth_in`, `runoff_depth_in`, `max_depth_ft`, etc.

---

### `rainfall_wizard.report`
```python
from rainfall_wizard.report import write_reports
paths = write_reports(result, config, output_dir="output")
```

---

### `rainfall_wizard.insights`
```python
from rainfall_wizard.insights import search_insights
results = search_insights("curve number")
```

---

## CLI Reference

```
rainfall-wizard run    LAT LON --dem DEM.tif --rp 100 --dur 24 --cn 75
rainfall-wizard batch  LAT LON --dem DEM.tif --dur 24 --cn 75
rainfall-wizard pfds   LAT LON [--dur 24] [--rp 100]
rainfall-wizard web    [--host HOST] [--port PORT]
rainfall-wizard insights [QUERY...]
```

---

## REST API (port 8020)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/pfds?lat=29.65&lon=-82.32&duration_hr=24&return_period_yr=100` | Single PFE |
| GET | `/api/pfds/table?lat=29.65&lon=-82.32` | Full table |
| POST | `/api/run` | Depth grid |
| GET | `/api/runoff?rainfall_in=6.5&cn=80` | CN runoff |
| GET | `/api/insights?q=curve+number` | Knowledge base |

Interactive docs: http://localhost:8020/docs

---

## SCS Storm Type Guide

| Type | Region | Peak Time |
|---|---|---|
| I | Pacific Coast | ~8 hr |
| IA | Pacific NW / Hawaii | ~8 hr (lower peak) |
| **II** | **Most of CONUS, SE US** | **~12 hr** |
| III | Gulf Coast, S. Louisiana | ~12 hr (more volume) |

---

*© Clearview Geographic LLC — Proprietary — All Rights Reserved*
