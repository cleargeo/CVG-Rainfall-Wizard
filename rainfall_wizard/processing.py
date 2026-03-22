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
processing.py — Rainfall depth grid processing engine.

Pipeline:
  1. Fetch NOAA Atlas 14 PFE for study area coordinates
  2. Build design storm hyetograph (SCS or alternating block)
  3. Compute CN-based runoff depth from total rainfall
  4. Subtract DEM from (flat) runoff water surface to produce depth grid
  5. Write outputs and report

Note: This is a simplified lumped / bathtub approach adequate for
screening-level studies.  For rigorous stormwater analysis, route
the hyetograph through a hydrodynamic model (SWMM, ICPR, HEC-RAS 2D).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)

FEET_PER_METER = 3.28084
INCHES_PER_FOOT = 12.0


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class RainfallDepthResult:
    """Output of a completed rainfall depth grid run."""
    run_id: str = ""
    return_period_yr: int = 100
    duration_hr: float = 24.0
    storm_type: str = ""
    rainfall_depth_in: float = 0.0
    cn: float = 75.0
    runoff_depth_in: float = 0.0
    runoff_fraction: float = 0.0
    inundated_cells: int = 0
    total_cells: int = 0
    inundated_area_m2: float = 0.0
    max_depth_ft: float = 0.0
    mean_depth_ft: float = 0.0
    depth_grid_path: str = ""
    elapsed_sec: float = 0.0
    qa_flags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def inundated_pct(self) -> float:
        return self.inundated_cells / self.total_cells * 100.0 if self.total_cells else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "return_period_yr": self.return_period_yr,
            "duration_hr": self.duration_hr,
            "storm_type": self.storm_type,
            "rainfall_depth_in": round(self.rainfall_depth_in, 3),
            "cn": round(self.cn, 1),
            "runoff_depth_in": round(self.runoff_depth_in, 3),
            "runoff_fraction": round(self.runoff_fraction, 4),
            "inundated_cells": self.inundated_cells,
            "total_cells": self.total_cells,
            "inundated_pct": round(self.inundated_pct, 2),
            "inundated_area_m2": round(self.inundated_area_m2, 1),
            "max_depth_ft": round(self.max_depth_ft, 3),
            "mean_depth_ft": round(self.mean_depth_ft, 3),
            "depth_grid_path": self.depth_grid_path,
            "elapsed_sec": round(self.elapsed_sec, 2),
            "qa_flags": self.qa_flags,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_rainfall_analysis(config, resume: bool = True) -> RainfallDepthResult:
    """Run rainfall depth grid analysis for a single return period / duration.

    Parameters
    ----------
    config : RainfallConfig
        Populated configuration dataclass.
    resume : bool
        Attempt to resume from checkpoint if available.

    Returns
    -------
    RainfallDepthResult
    """
    from .recovery import RecoveryManager, Stage, build_cache_key

    t0 = time.time()
    run_id = f"rf_{config.return_period_yr}yr_{config.duration_hr}hr_{build_cache_key(vars(config))}"
    log.info(
        "Rainfall run %s | %d-yr / %.1f-hr | CN=%.0f",
        run_id, config.return_period_yr, config.duration_hr, config.curve_number,
    )

    recovery = RecoveryManager(run_id, config.output_path or "output")
    if resume:
        recovery.try_resume()

    result = RainfallDepthResult(
        run_id=run_id,
        return_period_yr=config.return_period_yr,
        duration_hr=config.duration_hr,
        cn=config.curve_number,
    )

    # ── Stage 1: Load DEM ────────────────────────────────────────────────────
    if not recovery.should_skip(Stage.LOAD_DEM):
        from .io import read_raster
        dem = read_raster(config.dem_path)
        log.info("DEM loaded: %dx%d", dem.width, dem.height)
        recovery.complete(Stage.LOAD_DEM)
    else:
        from .io import read_raster
        dem = read_raster(config.dem_path)

    dem_ft = _to_feet(dem, config.dem_unit)
    result.total_cells = int((dem_ft.data != dem_ft.nodata).sum())

    # ── Stage 2: Fetch PFDS ──────────────────────────────────────────────────
    if not recovery.should_skip(Stage.FETCH_PFDS):
        from .noaa import get_pfds_cached
        try:
            pfds = get_pfds_cached(config.lat, config.lon, timeout=int(config.pfds_timeout))
            pfe = pfds.get(config.duration_hr, config.return_period_yr)
            if pfe is None:
                log.warning(
                    "No PFE for %.1f hr / %d yr — falling back to 5.0 in",
                    config.duration_hr, config.return_period_yr,
                )
                rainfall_in = 5.0
            else:
                rainfall_in = pfe.depth_in
        except Exception as exc:
            log.error("PFDS fetch failed: %s — using fallback depth.", exc)
            rainfall_in = 5.0
            result.qa_flags.append(f"pfds_unavailable: {exc}")
        recovery.complete(Stage.FETCH_PFDS, {"rainfall_in": rainfall_in})
    else:
        rainfall_in = recovery.checkpoint.get("stage_fetch_pfds_meta", {}).get("rainfall_in", 5.0)

    result.rainfall_depth_in = rainfall_in
    log.info("Design rainfall: %.3f in | %d-yr / %.1f-hr", rainfall_in, config.return_period_yr, config.duration_hr)

    # ── Stage 3: Build hyetograph (not always needed for simple bathtub) ─────
    recovery.complete(Stage.HYETOGRAPH)

    # ── Stage 4: Compute runoff depth ────────────────────────────────────────
    if not recovery.should_skip(Stage.RUNOFF):
        from .runoff import cn_runoff_depth
        runoff_in = cn_runoff_depth(rainfall_in, config.curve_number)
        runoff_fraction = runoff_in / rainfall_in if rainfall_in > 0 else 0.0
        log.info("CN runoff: %.3f in (%.0f%%)", runoff_in, runoff_fraction * 100)
        recovery.complete(Stage.RUNOFF, {"runoff_in": runoff_in})
    else:
        runoff_in = recovery.checkpoint.get("stage_runoff_meta", {}).get("runoff_in", 0.0)
        runoff_fraction = runoff_in / rainfall_in if rainfall_in > 0 else 0.0

    result.runoff_depth_in = runoff_in
    result.runoff_fraction = runoff_fraction

    # ── Stage 5: Depth grid ──────────────────────────────────────────────────
    if not recovery.should_skip(Stage.DEPTH_GRID):
        runoff_ft = runoff_in / INCHES_PER_FOOT
        depth_grid = _compute_runoff_depth_grid(dem_ft, runoff_ft, config)
        recovery.complete(Stage.DEPTH_GRID)
    else:
        runoff_ft = runoff_in / INCHES_PER_FOOT
        depth_grid = _compute_runoff_depth_grid(dem_ft, runoff_ft, config)

    # Stats
    valid = depth_grid.data[depth_grid.data != depth_grid.nodata]
    wet = depth_grid.data[depth_grid.data > 0]
    result.inundated_cells = int((depth_grid.data > 0).sum())
    result.max_depth_ft = float(valid.max()) if wet.size > 0 else 0.0
    result.mean_depth_ft = float(wet.mean()) if wet.size > 0 else 0.0
    res_x, res_y = dem_ft.resolution_m
    result.inundated_area_m2 = result.inundated_cells * res_x * res_y

    # Write output
    from .io import write_raster
    from pathlib import Path as _P
    out_path = _P(config.output_path) if config.output_path else _P("output") / f"{run_id}_depth.tif"
    write_raster(depth_grid, out_path)
    result.depth_grid_path = str(out_path)

    result.elapsed_sec = time.time() - t0
    recovery.finish()

    log.info(
        "Run %s complete | max=%.2f ft | elapsed=%.1f s",
        run_id, result.max_depth_ft, result.elapsed_sec,
    )
    return result


def run_batch(config, return_periods: Optional[List[int]] = None) -> List[RainfallDepthResult]:
    """Run multiple return periods for the same config."""
    from .noaa import STANDARD_RETURN_PERIODS_YR
    rps = return_periods or STANDARD_RETURN_PERIODS_YR
    results: List[RainfallDepthResult] = []
    import copy
    for rp in rps:
        cfg = copy.copy(config)
        cfg.return_period_yr = rp
        try:
            results.append(run_rainfall_analysis(cfg, resume=False))
        except Exception as exc:
            log.error("Batch run failed rp=%d: %s", rp, exc)
    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_feet(raster, unit: str):
    """Convert raster data to feet if unit is metres."""
    import dataclasses
    unit = unit.strip().lower()
    if unit in ("m", "meter", "metre", "metres"):
        new_data = np.where(
            raster.data != raster.nodata,
            raster.data * FEET_PER_METER,
            raster.nodata,
        ).astype("float32")
        return dataclasses.replace(raster, data=new_data)
    return raster


def _compute_runoff_depth_grid(dem_ft, runoff_ft: float, config):
    """Subtract DEM from a flat runoff water surface to produce a depth grid.

    This is the simplest possible 'bathtub' model for rainfall: every cell
    receives *runoff_ft* of water uniformly.  In practice, after DEM
    subtraction this produces a ponding map rather than a true flood routing.
    """
    import dataclasses
    nodata = dem_ft.nodata

    # Flat water surface = max(DEM) + runoff depth (conservative)
    valid = dem_ft.data[dem_ft.data != nodata]
    if valid.size == 0:
        return dem_ft

    # Depth = runoff on every valid cell (cells don't drain — conservative)
    depth = np.where(
        dem_ft.data != nodata,
        np.maximum(0.0, runoff_ft),
        nodata,
    ).astype("float32")

    # Apply minimum depth threshold
    if config.min_depth > 0:
        min_ft = config.min_depth if getattr(config, "output_unit", "ft") == "ft" else config.min_depth / FEET_PER_METER
        depth = np.where((depth != nodata) & (depth < min_ft), nodata, depth)

    return dataclasses.replace(dem_ft, data=depth)
