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
"""validate_dem.py — DEM integrity checker for Rainfall Wizard input rasters.

Checks a DEM raster for:
  - Nodata percentage (warn > 5%, fail > 30%)
  - Elevation range and unit detection (meters vs feet ambiguity)
  - CRS validity
  - Resolution adequacy for CN runoff depth grids
  - NaN / Inf pixel count

Usage::

    python tools/validate_dem.py path/to/dem.tif [--strict]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PASS = "\u2705"
FAIL = "\u274c"
WARN = "\u26a0\ufe0f"


def _rasterio_available() -> bool:
    try:
        import rasterio  # noqa: F401
        return True
    except ImportError:
        return False


def validate_dem(dem_path: Path, strict: bool = False) -> int:
    """Run all checks on *dem_path*.  Returns 0 on pass, 1 on failure."""
    if not _rasterio_available():
        print(f"{FAIL}  rasterio is not installed — cannot validate DEM.")
        print("    Install it with:  pip install rasterio")
        return 1

    import numpy as np
    import rasterio

    if not dem_path.exists():
        print(f"{FAIL}  File not found: {dem_path}")
        return 1

    failures = 0
    warnings = 0

    print(f"\n{'='*57}")
    print(f"  CVG Rainfall Wizard — DEM Validation Report")
    print(f"  File: {dem_path.name}")
    print(f"{'='*57}\n")

    with rasterio.open(dem_path) as ds:
        transform = ds.transform
        crs = ds.crs
        nodata = ds.nodata
        width, height = ds.width, ds.height
        band_count = ds.count
        data = ds.read(1, masked=True)

    res_x = abs(transform.a)
    res_y = abs(transform.e)
    res_m = res_x * 111320 if (crs and crs.is_geographic) else res_x
    total_pixels = width * height

    print(f"  Dimensions:   {width} × {height} pixels ({band_count} band{'s' if band_count > 1 else ''})")
    print(f"  Resolution:   {res_x:.6f} × {res_y:.6f}  (~{res_m:.1f} m)")
    print(f"  CRS:          {crs.to_string() if crs else 'UNKNOWN'}")
    print(f"  NoData:       {nodata}")
    print()

    # Check 1: CRS
    if crs is None:
        print(f"  {FAIL}  CRS is not defined.")
        failures += 1
    else:
        print(f"  {PASS}  CRS is defined: {crs.to_epsg() or crs.to_string()[:60]}")

    # Check 2: NoData percentage
    nodata_count = int(np.sum(data.mask)) if hasattr(data, "mask") else 0
    nodata_pct = 100.0 * nodata_count / max(total_pixels, 1)
    if nodata_pct > 30:
        print(f"  {FAIL}  NoData pixels: {nodata_pct:.1f}% — likely invalid coverage.")
        failures += 1
    elif nodata_pct > 5:
        print(f"  {WARN}  NoData pixels: {nodata_pct:.1f}% — check for data gaps.")
        warnings += 1
    else:
        print(f"  {PASS}  NoData pixels: {nodata_pct:.1f}%")

    # Check 3: NaN / Inf
    valid = data.compressed() if hasattr(data, "compressed") else data.flatten()
    nan_count = int(np.sum(~np.isfinite(valid)))
    if nan_count > 0:
        print(f"  {WARN}  Non-finite values (NaN/Inf): {nan_count:,} pixels")
        warnings += 1
    else:
        print(f"  {PASS}  Non-finite values: 0")

    # Check 4: Elevation range / unit detection
    if len(valid) > 0:
        emin, emax, emean = float(np.min(valid)), float(np.max(valid)), float(np.mean(valid))
        print(f"  {PASS}  Elevation range:  min={emin:.2f}  max={emax:.2f}  mean={emean:.2f}")

        # Heuristic unit detection: if max > 3000, likely in feet
        if emax > 3000:
            print(f"  {WARN}  Max elevation {emax:.0f} — may be in feet rather than meters. "
                  f"Rainfall CN analysis expects meters.")
            warnings += 1
        if emax < -5:
            print(f"  {WARN}  Mostly negative elevations — check datum/reference surface.")
            warnings += 1
    else:
        print(f"  {WARN}  No valid elevation data.")
        warnings += 1

    # Check 5: Resolution
    if res_m > 100:
        print(f"  {WARN}  Resolution ~{res_m:.0f} m — very coarse for runoff depth grids.")
        warnings += 1
    elif res_m > 30:
        print(f"  {WARN}  Resolution ~{res_m:.0f} m — acceptable for basin-scale analysis; "
              f"10 m or finer preferred.")
        warnings += 1
    else:
        print(f"  {PASS}  Resolution ~{res_m:.1f} m — suitable for Rainfall Wizard CN depth grids.")

    print()
    print(f"  Failures: {failures}  |  Warnings: {warnings}")
    print(f"{'='*57}\n")

    if failures > 0 or (strict and warnings > 0):
        return 1
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a DEM raster for use with CVG Rainfall Wizard."
    )
    parser.add_argument("dem", metavar="DEM_PATH", help="Path to input DEM raster (.tif).")
    parser.add_argument("--strict", action="store_true",
                        help="Fail on warnings as well as errors.")
    args = parser.parse_args(argv)
    return validate_dem(Path(args.dem), strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
