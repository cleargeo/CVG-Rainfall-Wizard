# -*- coding: utf-8 -*-
# =============================================================================
# (c) Clearview Geographic LLC -- All Rights Reserved | Est. 2018
# Proprietary Software -- Internal Use Only
# =============================================================================
"""CVG Rainfall Wizard — NOAA PFDS rainfall frequency analysis and flood depth grids.

© Clearview Geographic, LLC — All Rights Reserved | Est. 2018
Proprietary Software — Internal Use Only

This package provides rainfall-driven flood depth grid computation using:

- **NOAA Atlas 14 / PFDS** (Precipitation Frequency Data Server) for design
  storm depths from hourly to 24-hour durations at return periods 2yr–1000yr.
- **NRCS TR-55 Curve Number (CN) method** for rainfall-to-runoff conversion.
- **Standalone raster DEM engine** (``rainfall_wizard.io``, zero dependency on
  ``storm_surge_wizard``) for raster DEM processing and GeoTIFF output.

Optionally combines with storm surge and SLR for **compound hazard analysis**.

Two ``run_rainfall_analysis`` implementations are provided:

* ``run_rainfall_analysis`` (:mod:`~rainfall_wizard.core`) — Lightweight,
  no-dependency pipeline.  Fetches NOAA PFDS, applies NRCS TR-55, applies
  runoff to DEM, writes GeoTIFF.  Returns :class:`~rainfall_wizard.core.RainfallResult`.
  Recommended for scripted workflows and programmatic use.

* ``run_rainfall_analysis_full`` (:mod:`~rainfall_wizard.processing`) — Full
  production pipeline with checkpoint/resume, recovery manager, and multi-stage
  logging.  Returns :class:`~rainfall_wizard.processing.RainfallDepthResult`.
  Used by the web API (``POST /api/run``).

Quickstart (simple)::

    from rainfall_wizard import run_rainfall_analysis, RainfallConfig

    cfg = RainfallConfig(
        lat=24.556, lon=-81.807,
        duration_hr=24,
        return_period_yr=100,
        curve_number=75,
        dem_path="/data/dem.tif",
        output_path="/data/rainfall_depth_100yr.tif",
    )
    result = run_rainfall_analysis(cfg)
    print(result.output_path, result.stats)

Quickstart (full, with checkpointing)::

    from rainfall_wizard import run_rainfall_analysis_full, RainfallConfig

    cfg = RainfallConfig(
        lat=24.556, lon=-81.807,
        duration_hr=24,
        return_period_yr=100,
        curve_number=75,
        dem_path="/data/dem.tif",
        output_path="/data/output",
    )
    result = run_rainfall_analysis_full(cfg, resume=True)
    print(result.depth_grid_path, result.max_depth_ft)
"""
from __future__ import annotations

from rainfall_wizard.config import RainfallConfig, CompoundFloodConfig
from rainfall_wizard.core import run_rainfall_analysis, RainfallResult
from rainfall_wizard.pfds import fetch_pfds_depths, PfdsResult

# Full production engine — checkpoint/resume, multi-stage, used by web API
from rainfall_wizard.processing import (
    run_rainfall_analysis as run_rainfall_analysis_full,
    RainfallDepthResult,
)

__version__ = "1.1.0"

__all__ = [
    # Config
    "RainfallConfig",
    "CompoundFloodConfig",
    # Simple projection + depth-grid pipeline (no checkpointing)
    "run_rainfall_analysis",
    "RainfallResult",
    # Full production pipeline (checkpoint/resume, multi-stage logging)
    "run_rainfall_analysis_full",
    "RainfallDepthResult",
    # NOAA PFDS client
    "fetch_pfds_depths",
    "PfdsResult",
]
