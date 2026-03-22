# -*- coding: utf-8 -*-
# =============================================================================
# (c) Clearview Geographic LLC -- All Rights Reserved | Est. 2018
# Proprietary Software -- Internal Use Only
# =============================================================================
"""Rainfall Wizard core processing — rainfall to flood depth grid.

Pipeline
--------
1. Fetch NOAA Atlas 14 precipitation depth from PFDS for site (lat, lon),
   duration, and return period.
2. Convert precipitation depth → runoff depth using NRCS TR-55 Curve Number.
3. Treat runoff depth as a uniform water surface rise and subtract the DEM
   to compute a flood depth grid.
4. Write the flood depth GeoTIFF using the Storm Surge Wizard raster engine.

Scientific Notes
----------------
NRCS TR-55 (Curve Number method):
    Q = (P - Ia)² / (P - Ia + S)     when P > Ia, else Q = 0

    where:
      P  = total precipitation depth (inches or mm)
      S  = maximum potential retention = (1000/CN) - 10  [inches]
           (or (25400/CN) - 254  [mm])
      Ia = initial abstraction ≈ 0.2 × S  (standard assumption)
      Q  = direct runoff depth (same units as P)
      CN = NRCS Curve Number (dimensionless, 0–100)

    Reference: USDA SCS (1986) TR-55 Urban Hydrology for Small Watersheds.

The method assumes that **runoff depth Q acts as a uniform ponding layer** on
the DEM.  This is valid for flat coastal or urban study areas where the primary
hazard is ponding of direct precipitation, not channelized flow routing.  For
complex terrain with significant slope, a full hydrologic routing model is
required.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class RainfallResult:
    """Result of a completed rainfall flood depth analysis.

    Attributes
    ----------
    project_name : str
        Run identifier.
    output_path : str
        Path to the output flood depth GeoTIFF.
    stats : dict
        Descriptive statistics for the depth grid
        (``min``, ``max``, ``mean``, ``std``, ``flooded_cells_pct``).
    precipitation_in : float
        NOAA Atlas 14 design storm depth (inches).
    runoff_in : float
        NRCS TR-55 estimated runoff depth (inches).
    runoff_output_unit : float
        Runoff depth converted to the output unit (ft or m).
    output_unit : str
        Output unit (``"ft"`` or ``"m"``).
    curve_number : float
        CN value used.
    duration_hr : float
        Storm duration in hours.
    return_period_yr : int
        Return period in years.
    pfds_region : str
        NOAA Atlas 14 region label.
    method : str
        Computation method description.
    notes : str
        Free-text notes from the config.
    """
    project_name: str = ""
    output_path: str = ""
    stats: Dict[str, Any] = field(default_factory=dict)
    precipitation_in: float = 0.0
    runoff_in: float = 0.0
    runoff_output_unit: float = 0.0
    output_unit: str = "ft"
    curve_number: float = 75.0
    duration_hr: float = 24.0
    return_period_yr: int = 100
    pfds_region: str = ""
    method: str = "NRCS TR-55 CN method + NOAA Atlas 14 PFDS"
    notes: str = ""


# ---------------------------------------------------------------------------
# NRCS TR-55 Curve Number method
# ---------------------------------------------------------------------------

def compute_runoff_cn(
    precipitation_in: float,
    curve_number: float,
    *,
    initial_abstraction_ratio: float = 0.2,
) -> float:
    """Compute direct runoff depth using the NRCS TR-55 Curve Number method.

    Parameters
    ----------
    precipitation_in : float
        Total storm precipitation depth (inches).
    curve_number : float
        NRCS Curve Number (CN) for the watershed (0 < CN < 100).
    initial_abstraction_ratio : float
        Ratio of initial abstraction to maximum storage (default 0.2 per TR-55).
        Some recent research supports 0.05, but FEMA and TR-55 use 0.20.

    Returns
    -------
    float
        Direct runoff depth Q (inches).  Returns 0.0 when P ≤ Ia.

    References
    ----------
    USDA SCS (1986) Technical Release 55 (TR-55):
    Urban Hydrology for Small Watersheds, 2nd ed., pp. 2-1–2-9.
    """
    if curve_number <= 0 or curve_number >= 100:
        raise ValueError(f"CN must be between 0 and 100 (exclusive), got {curve_number}")
    if precipitation_in < 0:
        raise ValueError(f"Precipitation must be non-negative, got {precipitation_in}")

    # Maximum potential retention S (inches)
    S = (1000.0 / curve_number) - 10.0

    # Initial abstraction Ia
    Ia = initial_abstraction_ratio * S

    if precipitation_in <= Ia:
        return 0.0  # No runoff; precipitation does not exceed initial abstraction

    # TR-55 direct runoff equation
    Q = (precipitation_in - Ia) ** 2 / (precipitation_in - Ia + S)
    return max(0.0, Q)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_rainfall_analysis(config) -> RainfallResult:
    """Run a full NOAA PFDS + NRCS TR-55 + DEM flood depth grid computation.

    Parameters
    ----------
    config : RainfallConfig
        Populated configuration object.

    Returns
    -------
    RainfallResult
        Structured result with output paths and statistics.

    Raises
    ------
    ValueError
        When the config is invalid or PFDS returns no data.
    """
    from rainfall_wizard.pfds import fetch_pfds_depths

    _log.info(
        "Starting rainfall analysis: lat=%.4f lon=%.4f dur=%.1fhr RP=%dyr CN=%.1f",
        config.lat, config.lon, config.duration_hr, config.return_period_yr, config.curve_number,
    )

    # ── Step 1: Fetch NOAA Atlas 14 precipitation depth ──────────────────────
    pfds = fetch_pfds_depths(
        config.lat,
        config.lon,
        duration_hr=config.duration_hr,
        units=config.pfds_units,
        timeout=config.pfds_timeout,
    )

    precip_depth_raw = pfds.get_depth(config.return_period_yr)
    if precip_depth_raw is None or precip_depth_raw <= 0:
        raise ValueError(
            f"PFDS returned no depth for return period {config.return_period_yr} yr. "
            f"Available periods: {sorted(pfds.depths.keys())}. "
            f"Site: ({config.lat:.4f}, {config.lon:.4f}), duration: {config.duration_hr} hr."
        )

    # Normalise to inches for CN computation
    if pfds.units == "metric":
        precip_in = precip_depth_raw / 25.4
    else:
        precip_in = precip_depth_raw

    _log.info("PFDS: %.2f inches for %d-yr %g-hr storm at (%.4f, %.4f) [%s]",
              precip_in, config.return_period_yr, config.duration_hr,
              config.lat, config.lon, pfds.region or "unknown region")

    # ── Step 2: NRCS TR-55 CN runoff depth ────────────────────────────────────
    runoff_in = compute_runoff_cn(precip_in, config.curve_number)
    _log.info("TR-55 CN=%g: P=%.2f in → Q=%.2f in runoff", config.curve_number, precip_in, runoff_in)

    if runoff_in <= 0:
        _log.warning(
            "TR-55 CN=%g produces zero runoff for P=%.2f in. "
            "The precipitation does not exceed initial abstraction Ia=%.2f in.",
            config.curve_number, precip_in, 0.2 * ((1000.0 / config.curve_number) - 10.0),
        )

    # ── Step 3: Convert runoff to output unit ─────────────────────────────────
    out_unit = (config.output_unit or "ft").strip().lower()
    if out_unit in ("m", "meter", "metre", "metres"):
        runoff_out = runoff_in * 0.0254
    else:
        runoff_out = runoff_in / 12.0  # inches → feet

    # ── Step 4: Apply to DEM and write depth grid ────────────────────────────
    stats: Dict[str, Any] = {}
    output_path = config.output_path

    if config.dem_path and Path(config.dem_path).exists():
        try:
            from rainfall_wizard.io import read_raster, write_raster, RasterData, compute_stats

            dem = read_raster(config.dem_path)
            dem_mask = ~np.isfinite(dem.data) | (dem.data == dem.nodata)

            # Convert DEM to output unit
            dem_values = dem.data.astype("float32")
            if config.dem_unit == "m" and out_unit in ("ft", "feet", "foot"):
                dem_values = dem_values * 3.28084
            elif config.dem_unit == "ft" and out_unit in ("m", "meter", "metre", "metres"):
                dem_values = dem_values * 0.3048

            # Water surface = runoff depth ponds on top of existing terrain
            # For flat coastal areas, treat runoff as a uniform ponding height
            # above the lowest DEM elevation in the watershed.
            dem_min = float(np.nanmin(dem_values[~dem_mask])) if np.any(~dem_mask) else 0.0
            water_surface = dem_min + runoff_out

            # Depth = water surface − ground elevation
            depth = (water_surface - dem_values).astype("float32")

            # Apply min depth threshold and nodata
            nodata = float(config.output_nodata)
            if config.min_depth > 0:
                depth[(depth < config.min_depth) & ~dem_mask] = 0.0
            depth[dem_mask] = nodata
            depth[~np.isfinite(depth)] = nodata

            depth_raster = RasterData(
                data=depth, transform=dem.transform, crs=dem.crs,
                nodata=nodata, width=dem.width, height=dem.height, dtype="float32",
            )
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            write_raster(depth_raster, output_path, compress=True)

            stats = compute_stats(depth, nodata)
            valid = depth != nodata
            flooded = np.sum(valid & (depth > 0))
            total = np.sum(valid)
            stats["flooded_cells_pct"] = round(float(flooded) / max(int(total), 1) * 100, 2)

            _log.info("Wrote rainfall depth grid: %s  max=%.2f %s flooded=%.1f%%",
                      output_path, stats.get("max", 0), out_unit, stats.get("flooded_cells_pct", 0))

        except ImportError as exc:
            _log.warning("rainfall_wizard.io not available for DEM processing: %s", exc)
            stats = {"note": "DEM processing skipped — rasterio not installed"}
    else:
        if config.dem_path:
            _log.warning("DEM not found at %s — depth grid not written.", config.dem_path)
        stats = {"note": "No DEM provided — depth grid not written"}

    return RainfallResult(
        project_name=config.project_name,
        output_path=output_path,
        stats=stats,
        precipitation_in=round(precip_in, 4),
        runoff_in=round(runoff_in, 4),
        runoff_output_unit=round(runoff_out, 6),
        output_unit=out_unit,
        curve_number=config.curve_number,
        duration_hr=config.duration_hr,
        return_period_yr=config.return_period_yr,
        pfds_region=pfds.region,
        notes=config.notes,
    )


def run_compound_flood(config) -> Dict[str, Any]:
    """Produce a compound flood depth grid combining surge + rainfall + SLR.

    Takes a :class:`~rainfall_wizard.config.CompoundFloodConfig` with
    pre-computed water surface elevation components and:

    1. Combines them according to ``combination_method``.
    2. Subtracts the DEM to produce a total compound flood depth.
    3. Writes the result GeoTIFF.

    Parameters
    ----------
    config : CompoundFloodConfig
        Configuration with individual WSE components and DEM path.

    Returns
    -------
    dict
        ``{output_path, total_wse_ft, stats, combination_method, components}``
    """
    out_unit = (config.output_unit or "ft").strip().lower()

    # Resolve WSE components to output unit
    def _to_out(val: Optional[float]) -> float:
        if val is None:
            return 0.0
        if out_unit in ("m", "meter", "metre", "metres"):
            return float(val) * 0.3048  # assume input in ft
        return float(val)

    surge_wse = _to_out(config.storm_surge_wse_ft)
    rainfall = _to_out(config.rainfall_runoff_ft)
    slr = _to_out(config.slr_ft)

    method = (config.combination_method or "additive").lower()
    if method == "surge_plus_slr":
        total_wse = surge_wse + slr
    elif method == "rainfall_only":
        total_wse = rainfall
    else:  # "additive" — conservative upper bound
        total_wse = surge_wse + slr + rainfall

    _log.info(
        "Compound flood (%s): surge=%.3f + SLR=%.3f + rain=%.3f = total=%.3f %s",
        method, surge_wse, slr, rainfall, total_wse, out_unit,
    )

    stats: Dict[str, Any] = {}
    output_path = config.output_path

    if config.dem_path and Path(config.dem_path).exists():
        try:
            from rainfall_wizard.io import read_raster, write_raster, RasterData, compute_stats
            import numpy as np

            dem = read_raster(config.dem_path)
            nodata = float(config.output_nodata)
            dem_values = dem.data.astype("float32")

            if config.dem_unit == "m" and out_unit in ("ft", "feet", "foot"):
                dem_values = dem_values * 3.28084
            elif config.dem_unit == "ft" and out_unit in ("m", "meter", "metre", "metres"):
                dem_values = dem_values * 0.3048

            dem_mask = ~np.isfinite(dem_values)

            depth = (total_wse - dem_values).astype("float32")
            depth[depth < 0] = 0.0
            depth[dem_mask] = nodata

            depth_raster = RasterData(
                data=depth, transform=dem.transform, crs=dem.crs,
                nodata=nodata, width=dem.width, height=dem.height, dtype="float32",
            )
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            write_raster(depth_raster, output_path, compress=True)
            stats = compute_stats(depth, nodata)

        except Exception as exc:
            _log.warning("Compound flood DEM processing failed: %s", exc)
            stats = {"error": str(exc)}

    return {
        "output_path": output_path,
        "total_wse": round(total_wse, 4),
        "output_unit": out_unit,
        "combination_method": method,
        "components": {
            "storm_surge_wse": round(surge_wse, 4),
            "slr": round(slr, 4),
            "rainfall_runoff": round(rainfall, 4),
        },
        "stats": stats,
        "project_name": config.project_name,
    }
