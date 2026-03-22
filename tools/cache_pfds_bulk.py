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
"""cache_pfds_bulk.py — Pre-cache NOAA Atlas 14 PFDS data for a bounding box.

Generates a grid of lat/lon sample points within a county or state bounding box
and pre-populates the local PFDS cache for each point.  Subsequent API calls
within the cached area will return immediately without hitting the NOAA server.

Usage::

    python tools/cache_pfds_bulk.py --bbox 24.4 25.4 -81.9 -80.1 --spacing 0.1
    python tools/cache_pfds_bulk.py --county "Monroe,FL" --spacing 0.1

Output
------
Cache files are written to the default Rainfall Wizard cache directory
(``~/.cache/rainfall_wizard/pfds/``), one JSON file per grid point.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# Approximate county bounding boxes (lat_min, lat_max, lon_min, lon_max)
COUNTY_BBOX: dict = {
    "Monroe,FL":   (24.40, 25.40, -81.90, -80.10),
    "Miami-Dade,FL": (25.20, 25.98, -80.88, -80.10),
    "Broward,FL":  (25.95, 26.32, -80.40, -80.08),
    "Palm Beach,FL": (26.32, 26.98, -80.34, -80.03),
    "Collier,FL":  (25.65, 26.35, -81.90, -80.88),
    "Lee,FL":      (26.30, 26.78, -82.28, -81.55),
    "Hillsborough,FL": (27.70, 28.08, -82.77, -82.18),
    "Pinellas,FL": (27.65, 28.10, -82.91, -82.58),
    "Volusia,FL":  (28.85, 29.40, -81.65, -80.78),
    "Duval,FL":    (30.10, 30.57, -82.05, -81.40),
}


def bbox_grid(lat_min: float, lat_max: float, lon_min: float, lon_max: float,
              spacing: float) -> Iterator[Tuple[float, float]]:
    """Yield (lat, lon) grid points within a bounding box."""
    lat = lat_min
    while lat <= lat_max + spacing / 2:
        lon = lon_min
        while lon <= lon_max + spacing / 2:
            yield round(lat, 6), round(lon, 6)
            lon += spacing
        lat += spacing


def cache_point(lat: float, lon: float, cache_dir: Path,
                duration_hr: float = 24.0, timeout: int = 30) -> bool:
    """Fetch and cache PFDS data for a single (lat, lon) point."""
    cache_file = cache_dir / f"pfds_{lat:.4f}_{lon:.4f}.json"
    if cache_file.exists():
        log.debug("Cache hit: %s", cache_file.name)
        return True

    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent.parent))
        from rainfall_wizard.noaa import fetch_pfds

        resp = fetch_pfds(lat, lon, timeout=timeout)
        export = {
            "state": resp.state,
            "county": resp.county,
            "series": resp.atlas_series,
            "estimates": [e.to_dict() for e in resp.estimates],
        }
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with cache_file.open("w") as fh:
            json.dump(export, fh, indent=2)
        log.debug("Cached: %s", cache_file.name)
        return True
    except Exception as exc:
        log.warning("Failed to cache (%.4f, %.4f): %s", lat, lon, exc)
        return False


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pre-cache NOAA PFDS data for a geographic bounding box."
    )
    bbox_grp = parser.add_mutually_exclusive_group(required=True)
    bbox_grp.add_argument("--bbox", nargs=4, type=float,
                          metavar=("LAT_MIN", "LAT_MAX", "LON_MIN", "LON_MAX"),
                          help="Explicit bounding box (decimal degrees).")
    bbox_grp.add_argument("--county", metavar="NAME,ST",
                          help=f"Named county (e.g. Monroe,FL). Available: {', '.join(COUNTY_BBOX)}")
    parser.add_argument("--spacing", type=float, default=0.1, metavar="DEG",
                        help="Grid spacing in decimal degrees (default 0.1 ≈ 11 km).")
    parser.add_argument("--cache-dir", default=None, metavar="DIR",
                        help="Cache directory (default: ~/.cache/rainfall_wizard/pfds/).")
    parser.add_argument("--delay", type=float, default=0.5, metavar="SEC",
                        help="Seconds to wait between API requests (default 0.5).")
    parser.add_argument("--dry-run", action="store_true",
                        help="List grid points only; do not fetch data.")
    args = parser.parse_args(argv)

    # Resolve bounding box
    if args.bbox:
        lat_min, lat_max, lon_min, lon_max = args.bbox
    elif args.county:
        key = args.county.strip()
        if key not in COUNTY_BBOX:
            log.error("Unknown county: %s. Available: %s", key, list(COUNTY_BBOX))
            return 1
        lat_min, lat_max, lon_min, lon_max = COUNTY_BBOX[key]
    else:
        return 1

    # Resolve cache dir
    if args.cache_dir:
        cache_dir = Path(args.cache_dir)
    else:
        cache_dir = Path.home() / ".cache" / "rainfall_wizard" / "pfds"

    points = list(bbox_grid(lat_min, lat_max, lon_min, lon_max, args.spacing))
    log.info("Grid: %d points @ %.2f° spacing within (%.2f–%.2f, %.2f–%.2f)",
             len(points), args.spacing, lat_min, lat_max, lon_min, lon_max)

    if args.dry_run:
        for lat, lon in points:
            print(f"  ({lat:.4f}, {lon:.4f})")
        log.info("Dry run complete — %d points listed.", len(points))
        return 0

    cache_dir.mkdir(parents=True, exist_ok=True)
    successes = 0
    for i, (lat, lon) in enumerate(points, 1):
        log.info("[%d/%d] Caching (%.4f, %.4f)", i, len(points), lat, lon)
        if cache_point(lat, lon, cache_dir):
            successes += 1
        if args.delay > 0:
            time.sleep(args.delay)

    log.info("Done: %d/%d cached successfully.", successes, len(points))
    return 0 if successes == len(points) else 1


if __name__ == "__main__":
    sys.exit(main())
