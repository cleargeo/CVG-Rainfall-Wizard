# -*- coding: utf-8 -*-
# =============================================================================
# (c) Clearview Geographic LLC -- All Rights Reserved | Est. 2018
# Proprietary Software -- Internal Use Only
# =============================================================================
"""Rainfall Wizard configuration dataclasses."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RainfallConfig:
    """Configuration for a NOAA PFDS rainfall frequency + depth grid run.

    Parameters
    ----------
    lat : float
        Site latitude in decimal degrees (WGS84/NAD83).
    lon : float
        Site longitude in decimal degrees (WGS84/NAD83).
    duration_hr : float
        Storm duration in hours.  Common NOAA Atlas 14 durations:
        0.5, 1, 2, 3, 6, 12, 24, 48, 72 hours.
    return_period_yr : int
        Return period (AEP) in years (1, 2, 5, 10, 25, 50, 100, 200, 500, 1000).
    curve_number : float
        NRCS TR-55 Curve Number (CN) for the watershed (0–100).
        Higher CN = more runoff.  Typical values:
          - CN 55–65 : rural/lightly developed, HSG-A/B soils
          - CN 70–80 : mixed land use, HSG-B/C soils
          - CN 85–98 : highly impervious urban, HSG-C/D soils
    dem_path : str
        Path to the input DEM GeoTIFF.
    dem_unit : str
        Elevation unit of the DEM (``"m"`` or ``"ft"``).
    output_path : str
        Path to write the output flood depth GeoTIFF.
    output_unit : str
        Unit for the output depth grid (``"ft"`` or ``"m"``).
    output_nodata : float
        NoData value for dry cells in the output raster.
    project_name : str
        Identifier for this run.
    pfds_timeout : float
        HTTP timeout (seconds) for NOAA PFDS API requests.
    pfds_units : str
        ``"english"`` (inches) or ``"metric"`` (mm) for PFDS data fetch.
    min_depth : float
        Minimum depth threshold below which cells are treated as dry (output_unit).
    notes : str
        Free-text notes.
    """
    lat: float = 0.0
    lon: float = 0.0
    duration_hr: float = 24.0
    return_period_yr: int = 100
    curve_number: float = 75.0
    dem_path: str = ""
    dem_unit: str = "m"
    output_path: str = ""
    output_unit: str = "ft"
    output_nodata: float = -9999.0
    project_name: str = "rainfall_analysis"
    pfds_timeout: float = 30.0
    pfds_units: str = "english"
    min_depth: float = 0.0
    notes: str = ""


@dataclass
class CompoundFloodConfig:
    """Configuration for compound hazard analysis (storm surge + rainfall + SLR).

    Computes the combined water surface elevation from three independent hazard
    components, then subtracts the DEM to produce a compound flood depth grid.

    **Do NOT simply add independent flood depths** — that overstates the hazard
    because the return periods are not additive.  This config requires the user
    to supply the pre-computed water surface elevation (WSE) for each component,
    which are then combined using the selected ``combination_method``.

    Parameters
    ----------
    storm_surge_wse_ft : float | None
        Baseline storm surge still-water elevation (NAVD88, output_unit).
    rainfall_runoff_ft : float | None
        Rainfall-derived runoff depth above the ground surface (output_unit).
        Computed by the Rainfall Wizard and represents the additional water
        volume added to the site from precipitation.
    slr_ft : float | None
        Sea level rise increment (output_unit) from NOAA TR-083.
        Use ``slr_wizard.project_slr()`` to obtain.
    combination_method : str
        How to combine the three components:
        - ``"additive"`` — adds all three (conservative upper bound)
        - ``"surge_plus_slr"`` — storm surge + SLR only (no rainfall)
        - ``"rainfall_only"`` — rainfall component only (no surge/SLR)
    dem_path : str
        Path to the input DEM.
    dem_unit : str
        Elevation unit of the DEM (``"m"`` or ``"ft"``).
    output_path : str
        Path for the output compound flood depth GeoTIFF.
    output_unit : str
        Output unit (``"ft"`` or ``"m"``).
    output_nodata : float
        NoData value for dry cells.
    project_name : str
        Run identifier.
    """
    storm_surge_wse_ft: Optional[float] = None
    rainfall_runoff_ft: Optional[float] = None
    slr_ft: Optional[float] = None
    combination_method: str = "additive"
    dem_path: str = ""
    dem_unit: str = "m"
    output_path: str = ""
    output_unit: str = "ft"
    output_nodata: float = -9999.0
    project_name: str = "compound_flood"
    notes: str = ""
