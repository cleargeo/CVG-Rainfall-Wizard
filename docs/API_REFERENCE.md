# CVG Rainfall Wizard — API Reference

> © Clearview Geographic LLC | Internal Use Only | CVG-ADF

Port: **8020** | Base URL: `http://localhost:8020` (dev) / `https://rainfall.cleargeo.tech` (prod)

---

## Overview

The Rainfall Wizard exposes a FastAPI REST API for NOAA Atlas 14 precipitation frequency
estimation, NRCS TR-55 CN runoff computation, SCS design storm hydrograph generation, and
IDF curve retrieval. All endpoints return JSON. OpenAPI docs at `/docs` (Swagger UI).

---

## Authentication

Internal use only — no API key required on the local network.
Production deployments behind Caddy require network-level access control or mutual TLS.

---

## Endpoints

### `GET /`

Health check.

**Response 200:**
```json
{
  "service": "CVG Rainfall Wizard",
  "version": "1.0.0",
  "status": "ok"
}
```

---

### `POST /pfds`

Fetch NOAA Atlas 14 precipitation frequency data for a point.

**Request body** (`application/json`):

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `lat` | float | ✅ | — | Latitude (decimal degrees, WGS84) |
| `lon` | float | ✅ | — | Longitude (decimal degrees, WGS84) |
| `duration_hr` | float | ❌ | `24.0` | Storm duration in hours |
| `return_period_yr` | int | ❌ | `100` | Return period in years |
| `units` | str | ❌ | `"english"` | `"english"` (inches) or `"metric"` (mm) |

**Example request:**
```json
{
  "lat": 25.7617,
  "lon": -80.1918,
  "duration_hr": 24.0,
  "return_period_yr": 100
}
```

**Response 200:**
```json
{
  "lat": 25.7617,
  "lon": -80.1918,
  "duration_hr": 24.0,
  "return_period_yr": 100,
  "depth_in": 11.42,
  "depth_mm": 290.1,
  "intensity_in_hr": 0.476,
  "lower_ci_in": 10.21,
  "upper_ci_in": 12.84,
  "atlas_volume": "Atlas 14 Vol. 9",
  "source": "NOAA Atlas 14 PFDS",
  "units": "english",
  "run_id": "rfw-20260320-142301-abc123",
  "elapsed_s": 0.41
}
```

---

### `POST /runoff`

Compute NRCS TR-55 CN runoff depth and volume.

**Request body** (`application/json`):

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `lat` | float | ✅ | — | Site latitude |
| `lon` | float | ✅ | — | Site longitude |
| `duration_hr` | float | ❌ | `24.0` | Design storm duration (hours) |
| `return_period_yr` | int | ❌ | `100` | Return period (years) |
| `curve_number` | float | ✅ | — | NRCS CN value (1–100) |
| `drainage_area_sqkm` | float | ❌ | `1.0` | Watershed area (km²) |
| `storm_type` | str | ❌ | `"II"` | SCS storm type (`I`, `IA`, `II`, `III`) |
| `initial_abstraction_ratio` | float | ❌ | `0.2` | Ia/S ratio (default 0.2; use 0.05 for urban) |

**Response 200:**
```json
{
  "lat": 25.7617,
  "lon": -80.1918,
  "duration_hr": 24.0,
  "return_period_yr": 100,
  "curve_number": 82.0,
  "storm_type": "II",
  "rainfall_depth_in": 11.42,
  "initial_abstraction_in": 0.44,
  "potential_retention_in": 2.20,
  "runoff_depth_in": 8.84,
  "runoff_depth_mm": 224.5,
  "runoff_volume_m3": 224536.0,
  "runoff_ratio": 0.774,
  "drainage_area_sqkm": 1.0,
  "source": "NRCS TR-55 (1986)",
  "run_id": "rfw-20260320-142401-def456",
  "elapsed_s": 0.52
}
```

---

### `POST /analysis`

Full combined analysis: PFDS fetch + CN runoff + IDF table.

**Request body:** Same as `/runoff` above.

**Response 200:**
```json
{
  "pfds": { ... },
  "runoff": { ... },
  "idf_table": {
    "2":   {"1.0": 2.54, "2.0": 1.82, "6.0": 1.21, "24.0": 0.67},
    "10":  {"1.0": 3.91, "2.0": 2.71, "6.0": 1.74, "24.0": 0.94},
    "100": {"1.0": 6.12, "2.0": 4.27, "6.0": 2.63, "24.0": 1.41}
  },
  "run_id": "rfw-20260320-142501-ghi789",
  "elapsed_s": 0.63
}
```

---

### `GET /idf`

Retrieve IDF table for a point (all return periods × all standard durations).

**Query parameters:**
- `lat` (float, required)
- `lon` (float, required)

**Response 200:**
```json
{
  "lat": 25.7617,
  "lon": -80.1918,
  "units": "in/hr",
  "return_periods": [2, 5, 10, 25, 50, 100, 200, 500, 1000],
  "durations_hr": [0.0833, 0.1667, 0.25, 0.5, 1.0, 2.0, 3.0, 6.0, 12.0, 24.0],
  "table": {
    "0.0833": {"2": 3.21, "10": 4.87, "100": 8.14, ...},
    "24.0":   {"2": 0.21, "10": 0.34, "100": 0.55, ...}
  }
}
```

---

### `GET /storm-types`

List available SCS design storm types.

**Response 200:**
```json
{
  "storm_types": [
    {"type": "I",   "region": "Pacific Coast (low intensity, long duration)"},
    {"type": "IA",  "region": "Pacific Northwest / Hawaii"},
    {"type": "II",  "region": "Most of CONUS east of Rockies (most severe)"},
    {"type": "III", "region": "Gulf Coast / Atlantic coastal plain (flat topography)"}
  ]
}
```

---

### `GET /insights`

Query the Rainfall Wizard knowledge base.

**Query parameters:**
- `q` (str): Search query (e.g. `"curve number"`, `"idf"`, `"storm type"`)

**Response 200:**
```json
{
  "query": "curve number",
  "results": [
    {
      "topic": "curve_number",
      "title": "NRCS Curve Number (CN) Method",
      "body": "...",
      "tags": ["cn", "runoff", "tr55", "nrcs"],
      "source": "USDA-NRCS TR-55 (1986)"
    }
  ]
}
```

---

### `GET /health`

Liveness check.

**Response 200:** `{"status": "ok", "uptime_s": 5412.7}`

---

## Configuration Classes

### `RainfallConfig`

| Field | Type | Default | Description |
|---|---|---|---|
| `lat` | float | required | Site latitude |
| `lon` | float | required | Site longitude |
| `duration_hr` | float | `24.0` | Design storm duration |
| `return_period_yr` | int | `100` | Return period |
| `curve_number` | float | required | NRCS CN value |
| `drainage_area_sqkm` | float | `1.0` | Watershed area |
| `storm_type` | str | `"II"` | SCS storm distribution |
| `initial_abstraction_ratio` | float | `0.2` | Ia/S ratio |
| `output_dir` | str | `"./output"` | Output directory |

### `VALID_DURATIONS`

Standard Atlas 14 durations (hours): `0.0833, 0.1667, 0.25, 0.5, 1.0, 2.0, 3.0, 6.0, 12.0, 24.0, 48.0, 72.0`

### `VALID_RETURN_PERIODS`

`1, 2, 5, 10, 25, 50, 100, 200, 500, 1000`

### `VALID_STORM_TYPES`

`"I", "IA", "II", "III"`

---

## Error Codes

| HTTP | Meaning |
|---|---|
| 400 | Invalid input (CN out of range, unsupported duration) |
| 422 | Validation error |
| 500 | NOAA PFDS API unreachable or parse failure |
| 503 | Service temporarily unavailable |

---

## CLI Reference

```bash
# PFDS lookup
rainfall-wizard pfds --lat 25.77 --lon -80.19 --duration 24 --return-period 100

# CN runoff analysis
rainfall-wizard runoff --lat 25.77 --lon -80.19 --cn 82 --storm-type II

# Full analysis
rainfall-wizard run --lat 25.77 --lon -80.19 --cn 82 --return-period 100

# IDF table
rainfall-wizard idf --lat 25.77 --lon -80.19

# Knowledge base
rainfall-wizard insights --query "curve number"
```

---

*Reference: NOAA Atlas 14 (Perica et al. 2011–2019); USDA-NRCS TR-55 (1986)*
