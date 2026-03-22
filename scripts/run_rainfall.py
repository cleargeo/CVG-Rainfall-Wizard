#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# (c) Clearview Geographic LLC -- All Rights Reserved | Est. 2018
# CVG Rainfall Wizard — example run script
# Author: Alex Zelenski, GISP | azelenski@clearviewgeographic.com
# =============================================================================
"""
scripts/run_rainfall.py — Example script for running the Rainfall Wizard.

Edit the site parameters below and run:
    python scripts/run_rainfall.py

Or use the CLI:
    rainfall-wizard run 29.65 -82.32 --dem dem.tif --rp 100 --dur 24 --cn 75
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# ---------------------------------------------------------------------------
# Site parameters — edit these
# ---------------------------------------------------------------------------
SITE_LAT = 29.65      # Gainesville, FL area
SITE_LON = -82.32
DEM_PATH = "my_dem.tif"
CURVE_NUMBER = 75.0


# ---------------------------------------------------------------------------
# Example 1: Quick PFDS lookup (no DEM required)
# ---------------------------------------------------------------------------
def example_pfds_lookup():
    from rainfall_wizard.noaa import fetch_pfds, STANDARD_RETURN_PERIODS_YR

    print(f"\nFetching NOAA Atlas 14 PFDS for ({SITE_LAT}, {SITE_LON}) …")
    try:
        resp = fetch_pfds(SITE_LAT, SITE_LON)
        dur = 24.0
        print(f"\n  State: {resp.state}  |  County: {resp.county}")
        print(f"  Duration: {dur} hr")
        print(f"\n  {'Return Pd':>12s}  {'Depth (in)':>12s}  {'Intensity':>14s}")
        print("  " + "-"*42)
        for rp in STANDARD_RETURN_PERIODS_YR:
            pfe = resp.get(dur, rp)
            if pfe:
                print(f"  {rp:10d}-yr  {pfe.depth_in:12.3f}  {pfe.intensity_in_hr:12.4f} in/hr")
    except Exception as e:
        print(f"  [PFDS unavailable: {e}]")
        print("  (Check internet connection or use cached data)")


# ---------------------------------------------------------------------------
# Example 2: CN runoff calculation
# ---------------------------------------------------------------------------
def example_cn_runoff():
    from rainfall_wizard.runoff import compute_runoff

    print("\n  NRCS CN Runoff — 100-yr / 24-hr scenario")
    print(f"  CN = {CURVE_NUMBER:.0f}  |  Site: ({SITE_LAT}, {SITE_LON})")

    # Assume 6 inches for demo (would come from PFDS in real use)
    for rainfall_in in [3.0, 5.0, 7.0, 9.0]:
        result = compute_runoff(rainfall_in, CURVE_NUMBER)
        print(
            f"  P={rainfall_in:.1f} in → Q={result.runoff_depth_in:.2f} in  "
            f"({result.runoff_fraction*100:.0f}%)"
        )


# ---------------------------------------------------------------------------
# Example 3: SCS hyetograph
# ---------------------------------------------------------------------------
def example_hyetograph():
    from rainfall_wizard.idf import build_scs_hyetograph, STORM_TYPE_II

    total_depth = 6.5  # inches
    hyet = build_scs_hyetograph(total_depth, 24.0, STORM_TYPE_II, dt_hr=0.5)
    print(f"\n  SCS Type II Hyetograph ({total_depth} in / 24 hr)")
    print(f"  Peak intensity: {hyet.peak_intensity_in_hr:.3f} in/hr at t={hyet.time_to_peak_hr:.1f} hr")
    print(f"  Time steps    : {hyet.n_steps}")


# ---------------------------------------------------------------------------
# Example 4: Full depth grid run (requires a real DEM file)
# ---------------------------------------------------------------------------
def example_full_run(dem_path: str = DEM_PATH):
    from rainfall_wizard.config import RainfallConfig
    from rainfall_wizard.processing import run_rainfall_analysis
    from rainfall_wizard.report import write_reports

    cfg = RainfallConfig(
        lat=SITE_LAT,
        lon=SITE_LON,
        duration_hr=24.0,
        return_period_yr=100,
        curve_number=CURVE_NUMBER,
        dem_path=dem_path,
        dem_unit="m",
        output_path="output/100yr_24hr_depth.tif",
        output_unit="ft",
        project_name="Gainesville 100-yr Study",
    )

    result = run_rainfall_analysis(cfg, resume=True)
    paths = write_reports(result, cfg, output_dir="output")

    print(f"\n  Run complete: {result.run_id}")
    print(f"  Rainfall   : {result.rainfall_depth_in:.3f} in")
    print(f"  CN Runoff  : {result.runoff_depth_in:.3f} in  ({result.runoff_fraction*100:.0f}%)")
    print(f"  Max depth  : {result.max_depth_ft:.2f} ft")
    for fmt, path in paths.items():
        print(f"  [{fmt.upper()}] {path}")


# ---------------------------------------------------------------------------
# Example 5: Batch run (all standard return periods)
# ---------------------------------------------------------------------------
def example_batch_run(dem_path: str = DEM_PATH):
    from rainfall_wizard.config import RainfallConfig
    from rainfall_wizard.processing import run_batch

    cfg = RainfallConfig(
        lat=SITE_LAT, lon=SITE_LON,
        duration_hr=24.0,
        curve_number=CURVE_NUMBER,
        dem_path=dem_path, dem_unit="m",
    )
    results = run_batch(cfg)
    print(f"\n  Batch complete: {len(results)} runs")
    for r in results:
        print(f"  {r.return_period_yr:6d}-yr  rainfall={r.rainfall_depth_in:.2f} in  "
              f"runoff={r.runoff_depth_in:.2f} in  max={r.max_depth_ft:.2f} ft")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    example_pfds_lookup()
    example_cn_runoff()
    example_hyetograph()
    # Uncomment to run with a real DEM:
    # example_full_run("path/to/your/dem.tif")
    # example_batch_run("path/to/your/dem.tif")
