# -*- coding: utf-8 -*-
# =============================================================================
# (c) Clearview Geographic LLC -- All Rights Reserved | Est. 2018
# Proprietary Software -- Internal Use Only
# =============================================================================
"""NOAA Atlas 14 / PFDS (Precipitation Frequency Data Server) client.

Queries the NOAA Precipitation Frequency Data Server (PFDS) for design storm
depths at a given latitude/longitude, duration, and return period.

Reference
---------
NOAA Atlas 14: Precipitation-Frequency Atlas of the United States
https://hdsc.nws.noaa.gov/hdsc/pfds/

API endpoint
-----------
https://hdsc.nws.noaa.gov/hdsc/pfds/pfds_pointdatav2.html?lat={lat}&lon={lon}
    &data=depth&units=english&series=pds

Scientific Notes
----------------
* NOAA Atlas 14 uses **partial-duration series (PDS)** fitting, which
  counts all independent storm peaks above a threshold — not just annual
  maxima.  PDS generally yields slightly higher depths than AMS for
  shorter return periods (< ~10 yr).
* Depths are given in **inches** (English units) or **mm** (metric).
* Duration codes supported by PFDS: 5min, 10min, 15min, 30min, 60min,
  2hr, 3hr, 6hr, 12hr, 24hr, 2day, 3day, 4day, 7day, 10day.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

_log = logging.getLogger(__name__)

# NOAA PFDS JSON API endpoint
_PFDS_API_URL = "https://hdsc.nws.noaa.gov/hdsc/pfds/pfds_pointdatav2.html"

# Return period labels as published by PFDS
PFDS_RETURN_PERIODS = [1, 2, 5, 10, 25, 50, 100, 200, 500, 1000]

# Duration code mapping: hours → PFDS duration string
DURATION_CODE_MAP: Dict[float, str] = {
    0.0833: "5min",
    0.1667: "10min",
    0.25: "15min",
    0.5: "30min",
    1.0: "60min",
    2.0: "2hr",
    3.0: "3hr",
    6.0: "6hr",
    12.0: "12hr",
    24.0: "24hr",
    48.0: "2day",
    72.0: "3day",
    96.0: "4day",
    168.0: "7day",
    240.0: "10day",
}


@dataclass
class PfdsResult:
    """Result from a NOAA PFDS precipitation frequency data query.

    Attributes
    ----------
    lat : float
        Query latitude.
    lon : float
        Query longitude.
    duration_hr : float
        Storm duration in hours.
    duration_code : str
        PFDS duration code (e.g. ``"24hr"``).
    units : str
        Data units: ``"english"`` (inches) or ``"metric"`` (mm).
    depths : dict
        Mapping of return period (years, int) → precipitation depth.
        Example: ``{100: 9.44}`` means 9.44 inches for 100-year storm.
    lower_ci : dict
        90% lower confidence interval for each return period.
    upper_ci : dict
        90% upper confidence interval for each return period.
    region : str
        NOAA Atlas 14 volume/region label.
    source : str
        API URL used for this query.
    warning : str
        Any warning text returned by the PFDS API.
    """
    lat: float = 0.0
    lon: float = 0.0
    duration_hr: float = 24.0
    duration_code: str = "24hr"
    units: str = "english"
    depths: Dict[int, float] = None  # return_period_yr → depth
    lower_ci: Dict[int, float] = None
    upper_ci: Dict[int, float] = None
    region: str = ""
    source: str = ""
    warning: str = ""

    def __post_init__(self):
        if self.depths is None:
            self.depths = {}
        if self.lower_ci is None:
            self.lower_ci = {}
        if self.upper_ci is None:
            self.upper_ci = {}

    def get_depth(self, return_period_yr: int) -> Optional[float]:
        """Return the precipitation depth for a given return period.

        Parameters
        ----------
        return_period_yr : int
            Return period in years (1, 2, 5, 10, 25, 50, 100, 200, 500, 1000).

        Returns
        -------
        float or None
            Design storm depth in the configured units, or ``None`` if not available.
        """
        return self.depths.get(int(return_period_yr))

    def get_depth_inches(self, return_period_yr: int) -> Optional[float]:
        """Return depth in inches regardless of query units."""
        d = self.get_depth(return_period_yr)
        if d is None:
            return None
        if self.units == "metric":
            return d / 25.4
        return d


def _duration_to_code(duration_hr: float) -> str:
    """Return the PFDS duration code for a given numeric duration in hours.

    Uses exact match first, then nearest neighbour for values within 5%.
    Raises ``ValueError`` if no close match is found.
    """
    # Exact match
    if duration_hr in DURATION_CODE_MAP:
        return DURATION_CODE_MAP[duration_hr]

    # Nearest match within 5%
    best: Optional[str] = None
    best_diff = float("inf")
    for hr, code in DURATION_CODE_MAP.items():
        diff = abs(hr - duration_hr) / max(hr, 1e-9)
        if diff < best_diff:
            best_diff = diff
            best = code

    if best is not None and best_diff < 0.05:
        _log.debug("Duration %.3f hr mapped to PFDS code '%s' (%.1f%% error).", duration_hr, best, best_diff * 100)
        return best

    raise ValueError(
        f"Duration {duration_hr} hr has no matching PFDS duration code. "
        f"Supported durations (hours): {sorted(DURATION_CODE_MAP.keys())}"
    )


def fetch_pfds_depths(
    lat: float,
    lon: float,
    *,
    duration_hr: float = 24.0,
    units: str = "english",
    timeout: float = 30.0,
    retries: int = 3,
    backoff: float = 1.5,
) -> PfdsResult:
    """Fetch precipitation frequency depths from the NOAA Atlas 14 PFDS API.

    Queries the NOAA Precipitation Frequency Data Server for design storm
    depths at the specified coordinates and duration.

    Parameters
    ----------
    lat : float
        Site latitude in decimal degrees (WGS84/NAD83).
    lon : float
        Site longitude in decimal degrees (WGS84/NAD83).
    duration_hr : float
        Storm duration in hours (default 24).
        Common values: 0.5, 1, 2, 3, 6, 12, 24, 48, 72.
    units : str
        ``"english"`` (inches, default) or ``"metric"`` (mm).
    timeout : float
        HTTP timeout in seconds (default 30).
    retries : int
        Number of retry attempts on transient errors (default 3).
    backoff : float
        Exponential backoff base in seconds between retries (default 1.5).

    Returns
    -------
    PfdsResult
        Populated result with ``depths`` dict mapping return period → depth.

    Raises
    ------
    ValueError
        When the PFDS API returns an error response or the duration is not supported.
    URLError
        When the PFDS API is unreachable and retries are exhausted.

    Examples
    --------
    >>> result = fetch_pfds_depths(24.556, -81.807, duration_hr=24)
    >>> print(f"100-yr 24-hr depth: {result.get_depth(100):.2f} inches")
    """
    duration_code = _duration_to_code(duration_hr)
    units_param = "english" if units == "english" else "metric"

    params = {
        "lat": f"{lat:.4f}",
        "lon": f"{lon:.4f}",
        "data": "depth",
        "units": units_param,
        "series": "pds",
        "stype": "partial",
        "freq": duration_code,
    }
    url = f"{_PFDS_API_URL}?{urlencode(params)}"

    last_error: Optional[Exception] = None
    for attempt in range(max(1, retries)):
        try:
            with urlopen(url, timeout=timeout) as response:  # nosec - NOAA public API
                raw = response.read().decode("utf-8")
            break
        except (HTTPError, URLError) as exc:
            last_error = exc
            _log.warning("PFDS request attempt %d failed: %s", attempt + 1, exc)
            if attempt < retries - 1:
                time.sleep(backoff * (1.5 ** attempt))
    else:
        raise last_error or URLError("PFDS request failed after all retries")

    return _parse_pfds_response(raw, lat=lat, lon=lon, duration_hr=duration_hr,
                                duration_code=duration_code, units=units_param, source=url)


def _parse_pfds_response(
    raw: str,
    *,
    lat: float,
    lon: float,
    duration_hr: float,
    duration_code: str,
    units: str,
    source: str,
) -> PfdsResult:
    """Parse the NOAA PFDS JSON/text response into a :class:`PfdsResult`.

    The PFDS response is a JavaScript-like text (not pure JSON).  The relevant
    data are embedded in ``var data_values = [[...]]`` arrays.  This parser
    extracts the depth values for all return periods.
    """
    depths: Dict[int, float] = {}
    lower_ci: Dict[int, float] = {}
    upper_ci: Dict[int, float] = {}
    region = ""
    warning = ""

    # PFDS returns data in a pseudo-JSON JS variable assignment block.
    # Format (example): var data_values = [[1,5,10,25],[3.45,5.67,7.89,10.1]]
    # First sub-array = return periods (years), second = depths.
    import re

    # Extract region name
    region_match = re.search(r'"region"\s*:\s*"([^"]+)"', raw)
    if region_match:
        region = region_match.group(1)

    # Try JSON-flavored parse first (newer PFDS format)
    try:
        # Look for {"data": {"freq": [...], "returnperiods": [...], ...}} structure
        json_match = re.search(r'\{.*"returnperiods".*\}', raw, re.DOTALL)
        if json_match:
            obj = json.loads(json_match.group(0))
            data = obj.get("data", {})
            periods = [int(x) for x in data.get("returnperiods", [])]
            values = [float(x) for x in data.get("quantiles", [])]
            lower = [float(x) for x in data.get("lower90", [])]
            upper = [float(x) for x in data.get("upper90", [])]
            for p, v, lo, hi in zip(periods, values, lower or [None]*len(periods), upper or [None]*len(periods)):
                depths[p] = v
                if lo is not None:
                    lower_ci[p] = lo
                if hi is not None:
                    upper_ci[p] = hi
    except Exception:
        pass

    # Legacy text-format fallback
    if not depths:
        # Pattern: javascript arrays like: var data_values = [[2,5,10,25,50,100,200,500,1000],[1.23,2.34,...]]
        arr_match = re.search(r'var\s+data_values\s*=\s*(\[\[.*?\]\])', raw, re.DOTALL)
        if arr_match:
            try:
                arrays = json.loads(arr_match.group(1))
                if len(arrays) >= 2:
                    for period, depth in zip(arrays[0], arrays[1]):
                        depths[int(period)] = float(depth)
            except Exception:
                pass

    # Fallback: look for tabular data patterns
    if not depths:
        # Pattern: return_period depth_inches on each line
        for line in raw.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                try:
                    p = int(parts[0])
                    v = float(parts[1])
                    if p in PFDS_RETURN_PERIODS and v > 0:
                        depths[p] = v
                except (ValueError, IndexError):
                    continue

    if not depths:
        warning = (
            "PFDS response could not be parsed — no depth data extracted. "
            "The site may be outside the NOAA Atlas 14 coverage area, or the "
            "PFDS API format may have changed. "
            "Visit https://hdsc.nws.noaa.gov/hdsc/pfds/ to retrieve data manually."
        )
        _log.warning("PFDS parse failed for (%.4f, %.4f) %s: %s", lat, lon, duration_code, warning)

    return PfdsResult(
        lat=lat,
        lon=lon,
        duration_hr=duration_hr,
        duration_code=duration_code,
        units=units,
        depths=depths,
        lower_ci=lower_ci,
        upper_ci=upper_ci,
        region=region,
        source=source,
        warning=warning,
    )
