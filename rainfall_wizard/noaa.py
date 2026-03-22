# -*- coding: utf-8 -*-
# =============================================================================
# (c) Clearview Geographic LLC -- All Rights Reserved | Est. 2018
# Proprietary Software -- Internal Use Only
# Protected under US and International copyright, trade secret,
# trademark, cybersecurity, and intellectual property law.
# This Product is developed under CVG's Agentic Development Framework (ADF).
# Unauthorized use, replication, or modification is strictly prohibited.
# -----------------------------------------------------------------------------
# Author      : Alex Zelenski, GISP
# Organization: Clearview Geographic, LLC
# Contact     : azelenski@clearviewgeographic.com  |  386-957-2314
# License     : Proprietary -- CVG-ADF
# =============================================================================
"""
noaa.py — NOAA Precipitation Frequency Data Server (PFDS) / Atlas 14 client.

Fetches precipitation frequency estimates (PFEs) from the NOAA PFDS REST API
at https://hdsc.nws.noaa.gov/pfds/

Reference:
  Perica, S. et al. (2011–2019). NOAA Atlas 14 Precipitation-Frequency Atlas
  of the United States. NOAA, National Weather Service. Silver Spring, MD.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

PFDS_BASE_URL = "https://hdsc.nws.noaa.gov/cgi-bin/hdsc/new/fe_text_mean.csv"
PFDS_JSON_URL = "https://hdsc.nws.noaa.gov/pfds/pfds_json.php"

# NOAA Atlas 14 standard durations (hours)
STANDARD_DURATIONS_HR = [
    0.0833,   # 5 min
    0.1667,   # 10 min
    0.25,     # 15 min
    0.5,      # 30 min
    1.0,      # 60 min
    2.0,
    3.0,
    6.0,
    12.0,
    24.0,
    48.0,
    72.0,
    96.0,
    120.0,
    168.0,    # 7 days
    240.0,    # 10 days
    360.0,    # 15 days
    720.0,    # 30 days
]

# NOAA Atlas 14 standard return periods (years)
STANDARD_RETURN_PERIODS_YR = [1, 2, 5, 10, 25, 50, 100, 200, 500, 1000]


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class PrecipFreqEstimate:
    """A single NOAA Atlas 14 precipitation frequency estimate."""
    lat: float
    lon: float
    duration_hr: float
    return_period_yr: int
    depth_in: float              # precipitation depth in inches
    depth_mm: float              # precipitation depth in mm
    lower_ci_in: float = 0.0     # 90% confidence interval lower bound (in)
    upper_ci_in: float = 0.0     # 90% confidence interval upper bound (in)
    source: str = "noaa_pfds"
    atlas_volume: str = ""       # e.g. "Atlas 14 Vol. 9"

    @property
    def intensity_in_hr(self) -> float:
        """Rainfall intensity (in/hr)."""
        if self.duration_hr == 0:
            return 0.0
        return self.depth_in / self.duration_hr

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lat": self.lat,
            "lon": self.lon,
            "duration_hr": self.duration_hr,
            "return_period_yr": self.return_period_yr,
            "depth_in": round(self.depth_in, 3),
            "depth_mm": round(self.depth_mm, 2),
            "intensity_in_hr": round(self.intensity_in_hr, 4),
            "lower_ci_in": round(self.lower_ci_in, 3),
            "upper_ci_in": round(self.upper_ci_in, 3),
            "source": self.source,
        }


@dataclass
class PFDSResponse:
    """Full PFDS response for one lat/lon point."""
    lat: float
    lon: float
    state: str = ""
    county: str = ""
    atlas_series: str = ""
    estimates: List[PrecipFreqEstimate] = field(default_factory=list)

    def get(self, duration_hr: float, return_period_yr: int) -> Optional[PrecipFreqEstimate]:
        """Look up a specific duration/return period estimate."""
        for e in self.estimates:
            if abs(e.duration_hr - duration_hr) < 0.001 and e.return_period_yr == return_period_yr:
                return e
        return None

    def idf_table(self) -> Dict[int, Dict[float, float]]:
        """Return {return_period: {duration_hr: intensity_in_hr}} lookup."""
        table: Dict[int, Dict[float, float]] = {}
        for e in self.estimates:
            table.setdefault(e.return_period_yr, {})[e.duration_hr] = e.intensity_in_hr
        return table


# ---------------------------------------------------------------------------
# NOAA PFDS API client
# ---------------------------------------------------------------------------

def fetch_pfds(
    lat: float,
    lon: float,
    duration_hr: Optional[float] = None,
    return_period_yr: Optional[int] = None,
    units: str = "english",
    timeout: int = 30,
) -> PFDSResponse:
    """Fetch precipitation frequency estimates from the NOAA PFDS API.

    Parameters
    ----------
    lat : float
        Latitude in decimal degrees (WGS84).
    lon : float
        Longitude in decimal degrees (WGS84).
    duration_hr : float, optional
        If provided, filter to this duration only.
    return_period_yr : int, optional
        If provided, filter to this return period only.
    units : str
        ``"english"`` for inches or ``"metric"`` for mm.
    timeout : int
        HTTP request timeout in seconds.

    Returns
    -------
    PFDSResponse
        All estimates for the given point.
    """
    params = {
        "lat": f"{lat:.6f}",
        "lon": f"{lon:.6f}",
        "type": "pf",
        "data": "depth",
        "units": units,
        "series": "pds",
    }
    url = f"{PFDS_JSON_URL}?" + urllib.parse.urlencode(params)
    log.debug("PFDS request: %s", url)

    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
        return _parse_pfds_response(raw, lat, lon)
    except Exception as exc:
        log.error("PFDS fetch failed for (%.4f, %.4f): %s", lat, lon, exc)
        raise


def fetch_single_pfe(
    lat: float,
    lon: float,
    duration_hr: float,
    return_period_yr: int,
    timeout: int = 30,
) -> Optional[PrecipFreqEstimate]:
    """Convenience: fetch a single PFE value."""
    try:
        resp = fetch_pfds(lat, lon, duration_hr, return_period_yr, timeout=timeout)
        return resp.get(duration_hr, return_period_yr)
    except Exception as exc:
        log.warning("fetch_single_pfe failed: %s", exc)
        return None


def _parse_pfds_response(raw: str, lat: float, lon: float) -> PFDSResponse:
    """Parse the NOAA PFDS JSON payload into a :class:`PFDSResponse`."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to handle CSV-style fallback
        return _parse_pfds_csv(raw, lat, lon)

    response = PFDSResponse(lat=lat, lon=lon)
    response.state = data.get("state", "")
    response.county = data.get("county", "")
    response.atlas_series = data.get("series", "")

    # Parse the nested data structure
    # Expected keys: "quantiles", "upper", "lower", "duration", "freq"
    quantiles = data.get("quantiles", [])
    upper = data.get("upper", [])
    lower = data.get("lower", [])
    durations_raw = data.get("duration", STANDARD_DURATIONS_HR)
    return_periods_raw = data.get("freq", STANDARD_RETURN_PERIODS_YR)

    # Convert duration strings like "5-min" to hours
    dur_hr = [_dur_to_hours(d) for d in durations_raw]
    rp = [int(r) for r in return_periods_raw]

    for i, dur in enumerate(dur_hr):
        if i >= len(quantiles):
            break
        row = quantiles[i]
        for j, period in enumerate(rp):
            if j >= len(row):
                break
            depth_in = float(row[j]) if row[j] not in (None, "", "NaN") else 0.0
            lo = float(lower[i][j]) if lower and i < len(lower) and j < len(lower[i]) else 0.0
            hi = float(upper[i][j]) if upper and i < len(upper) and j < len(upper[i]) else 0.0
            response.estimates.append(PrecipFreqEstimate(
                lat=lat, lon=lon,
                duration_hr=dur,
                return_period_yr=period,
                depth_in=depth_in,
                depth_mm=depth_in * 25.4,
                lower_ci_in=lo,
                upper_ci_in=hi,
                source="noaa_pfds",
                atlas_series=response.atlas_series,
            ))

    log.info("PFDS: parsed %d estimates for (%.4f, %.4f)", len(response.estimates), lat, lon)
    return response


def _parse_pfds_csv(raw: str, lat: float, lon: float) -> PFDSResponse:
    """Fallback CSV parser for NOAA PFDS text output."""
    response = PFDSResponse(lat=lat, lon=lon)
    lines = raw.strip().split("\n")
    for line in lines:
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        parts = line.split(",")
        if len(parts) < 3:
            continue
        try:
            dur_hr = _dur_to_hours(parts[0].strip())
            rp = int(parts[1].strip())
            depth = float(parts[2].strip())
            response.estimates.append(PrecipFreqEstimate(
                lat=lat, lon=lon,
                duration_hr=dur_hr,
                return_period_yr=rp,
                depth_in=depth,
                depth_mm=depth * 25.4,
                source="noaa_pfds_csv",
            ))
        except (ValueError, IndexError):
            continue
    return response


def _dur_to_hours(dur) -> float:
    """Convert a duration string or number to hours."""
    if isinstance(dur, (int, float)):
        return float(dur)
    s = str(dur).strip().lower()
    if s.endswith("-min") or s.endswith("min"):
        mins = float(s.replace("-min", "").replace("min", ""))
        return mins / 60.0
    if s.endswith("-hr") or s.endswith("hr"):
        return float(s.replace("-hr", "").replace("hr", ""))
    if s.endswith("-day") or s.endswith("day"):
        return float(s.replace("-day", "").replace("day", "")) * 24.0
    try:
        return float(s)
    except ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# Offline / cached fallback
# ---------------------------------------------------------------------------

def get_pfds_cached(
    lat: float,
    lon: float,
    cache_dir: Optional[str] = None,
    duration_hr: Optional[float] = None,
    return_period_yr: Optional[int] = None,
    timeout: int = 30,
) -> PFDSResponse:
    """Return PFDS data from cache if available, otherwise fetch and cache."""
    import os, hashlib
    from pathlib import Path

    if cache_dir is None:
        from .paths import get_cache_dir
        cache_dir = get_cache_dir()
    cache_path = Path(cache_dir) / f"pfds_{lat:.4f}_{lon:.4f}.json"

    if cache_path.exists():
        try:
            with cache_path.open("r") as fh:
                raw = fh.read()
            log.debug("PFDS cache hit: %s", cache_path)
            return _parse_pfds_response(raw, lat, lon)
        except Exception:
            pass

    resp = fetch_pfds(lat, lon, timeout=timeout)

    # Cache the raw JSON
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        # Re-serialize for caching
        export = {
            "state": resp.state, "county": resp.county,
            "series": resp.atlas_series,
            "estimates": [e.to_dict() for e in resp.estimates],
        }
        with cache_path.open("w") as fh:
            json.dump(export, fh, indent=2)
    except Exception as exc:
        log.warning("Could not cache PFDS data: %s", exc)

    return resp
