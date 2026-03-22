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
runoff.py — NRCS Curve Number runoff calculations (TR-55 / TR-20).

Implements:
  - CN-based runoff depth (TR-55 Eq. 2-1)
  - Ia (initial abstraction) as 0.2S or 0.05S (urban)
  - Composite CN from land use × hydrologic soil group
  - Time of concentration (TR-55 method)
  - Peak discharge (TR-55 graphical / tabular)

References:
  USDA-NRCS (1986). Urban Hydrology for Small Watersheds. TR-55, 2nd Ed.
  USDA-NRCS (1992). Computer Program for Project Formulation Hydrology. TR-20.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CN runoff equation
# ---------------------------------------------------------------------------

def cn_runoff_depth(
    rainfall_in: float,
    cn: float,
    ia_ratio: float = 0.2,
) -> float:
    """Compute direct runoff depth (inches) using NRCS CN method (TR-55 Eq. 2-1).

    Q = (P - 0.2S)² / (P + 0.8S)   when  P > 0.2S
    Q = 0                            when  P ≤ 0.2S

    Parameters
    ----------
    rainfall_in : float
        Total rainfall depth in inches.
    cn : float
        NRCS Curve Number (1–100).
    ia_ratio : float
        Initial abstraction ratio (default 0.2; use 0.05 for urban).

    Returns
    -------
    float
        Direct runoff depth in inches.
    """
    cn = float(np.clip(cn, 1.0, 99.99))
    S = 1000.0 / cn - 10.0          # potential maximum retention (in)
    Ia = ia_ratio * S                 # initial abstraction (in)
    if rainfall_in <= Ia:
        return 0.0
    Q = (rainfall_in - Ia) ** 2 / (rainfall_in - Ia + S)
    return max(0.0, Q)


def cn_runoff_series(
    rainfall_series_in: List[float],
    cn: float,
    ia_ratio: float = 0.2,
) -> Tuple[List[float], List[float]]:
    """Compute incremental runoff from a cumulative rainfall series.

    Returns (runoff_depth_series_in, incremental_runoff_in).
    """
    runoff = [cn_runoff_depth(p, cn, ia_ratio) for p in rainfall_series_in]
    incremental = [0.0] + [max(0.0, runoff[i] - runoff[i - 1]) for i in range(1, len(runoff))]
    return runoff, incremental


# ---------------------------------------------------------------------------
# Composite CN
# ---------------------------------------------------------------------------

@dataclass
class LandCoverArea:
    """One land cover type contributing to a composite CN."""
    description: str
    cn: float       # NRCS CN for this cover/HSG combination
    area_acres: float


def composite_cn(land_covers: List[LandCoverArea]) -> float:
    """Compute area-weighted composite CN.

    CN_composite = Σ(CNi × Ai) / Σ(Ai)
    """
    total_area = sum(lc.area_acres for lc in land_covers)
    if total_area == 0:
        return 75.0  # placeholder
    return sum(lc.cn * lc.area_acres for lc in land_covers) / total_area


# ---------------------------------------------------------------------------
# NRCS CN lookup table snippet (TR-55 Table 2-2a/b)
# Format: {(cover_type, HSG): cn}
# ---------------------------------------------------------------------------

CN_TABLE: Dict[Tuple[str, str], float] = {
    # Open space / parks
    ("open_space_good",        "A"): 39, ("open_space_good",        "B"): 61,
    ("open_space_good",        "C"): 74, ("open_space_good",        "D"): 80,
    ("open_space_fair",        "A"): 49, ("open_space_fair",        "B"): 69,
    ("open_space_fair",        "C"): 79, ("open_space_fair",        "D"): 84,
    # Impervious
    ("impervious",             "A"): 98, ("impervious",             "B"): 98,
    ("impervious",             "C"): 98, ("impervious",             "D"): 98,
    # Residential 1/4 acre
    ("residential_025ac",      "A"): 54, ("residential_025ac",      "B"): 70,
    ("residential_025ac",      "C"): 80, ("residential_025ac",      "D"): 85,
    # Residential 1/2 acre
    ("residential_05ac",       "A"): 25, ("residential_05ac",       "B"): 55,
    ("residential_05ac",       "C"): 70, ("residential_05ac",       "D"): 80,
    # Commercial
    ("commercial",             "A"): 89, ("commercial",             "B"): 92,
    ("commercial",             "C"): 94, ("commercial",             "D"): 95,
    # Industrial
    ("industrial",             "A"): 81, ("industrial",             "B"): 88,
    ("industrial",             "C"): 91, ("industrial",             "D"): 93,
    # Row crops straight
    ("row_crops_straight",     "A"): 72, ("row_crops_straight",     "B"): 81,
    ("row_crops_straight",     "C"): 88, ("row_crops_straight",     "D"): 91,
    # Woods with good cover
    ("woods_good",             "A"): 30, ("woods_good",             "B"): 55,
    ("woods_good",             "C"): 70, ("woods_good",             "D"): 77,
    # Wetlands
    ("wetlands",               "A"): 40, ("wetlands",               "B"): 65,
    ("wetlands",               "C"): 78, ("wetlands",               "D"): 82,
    # Water
    ("water",                  "A"): 100, ("water",                 "B"): 100,
    ("water",                  "C"): 100, ("water",                 "D"): 100,
}


def lookup_cn(cover_type: str, hsg: str) -> Optional[float]:
    """Look up CN from the TR-55 table."""
    key = (cover_type.lower(), hsg.upper())
    return CN_TABLE.get(key)


# ---------------------------------------------------------------------------
# Time of concentration (TR-55)
# ---------------------------------------------------------------------------

def tc_sheet_flow(
    rainfall_2yr_24hr_in: float,
    n: float,          # Manning's n for sheet flow
    slope_ftft: float, # average slope (ft/ft)
    length_ft: float,  # flow length (≤300 ft)
) -> float:
    """TR-55 sheet flow travel time in hours."""
    if slope_ftft <= 0 or length_ft <= 0:
        return 0.0
    ts = 0.007 * (n * length_ft) ** 0.8 / (rainfall_2yr_24hr_in ** 0.5 * slope_ftft ** 0.4)
    return ts


def tc_shallow_concentrated(
    length_ft: float,
    slope_ftft: float,
    surface: str = "unpaved",   # "paved" or "unpaved"
) -> float:
    """TR-55 shallow concentrated flow travel time in hours."""
    if slope_ftft <= 0:
        return 0.0
    # Velocity from TR-55 Figure 3-1 regression
    if surface == "paved":
        v = 20.3282 * slope_ftft ** 0.5   # ft/s
    else:
        v = 16.1345 * slope_ftft ** 0.5   # ft/s
    t_sec = length_ft / v
    return t_sec / 3600.0


def tc_channel_flow(
    length_ft: float,
    velocity_fps: float,
) -> float:
    """Channel flow travel time in hours."""
    if velocity_fps <= 0:
        return 0.0
    return length_ft / velocity_fps / 3600.0


def time_of_concentration(*travel_times_hr: float) -> float:
    """Sum component TR-55 travel times → Tc in hours."""
    return sum(t for t in travel_times_hr if t > 0)


# ---------------------------------------------------------------------------
# Peak discharge (TR-55 tabular method)
# ---------------------------------------------------------------------------

def peak_discharge_rational(
    C: float,           # Rational C coefficient
    intensity_in_hr: float,
    area_acres: float,
) -> float:
    """Rational method peak discharge (cfs). Q = CiA"""
    return C * intensity_in_hr * area_acres


def peak_discharge_tr55(
    rainfall_in: float,
    cn: float,
    area_sqmi: float,
    tc_hr: float,
    ia_ratio: float = 0.2,
) -> float:
    """Approximate peak discharge (cfs) using TR-55 tabular/graphical method.

    This is a simplified unit peak discharge approach using the relationship:
        q_u = f(Tc, Ia/P) from TR-55 exhibits
    Then qp = q_u × A × Q  (where Q is runoff in inches from CN equation)
    """
    Q = cn_runoff_depth(rainfall_in, cn, ia_ratio)
    if Q <= 0:
        return 0.0
    S = 1000.0 / cn - 10.0
    Ia = ia_ratio * S
    ia_p = min(Ia / rainfall_in, 0.50) if rainfall_in > 0 else 0.10

    # Unit peak discharge interpolation (simplified polynomial from TR-55 Exhibit 4-II)
    # log(qu) = C0 + C1*log(Tc) + C2*(log(Tc))^2
    # Coefficients for 24-hr Type II storm (TR-55 Table 4-1)
    _coeff = {
        0.10: (2.55323, -0.61512, -0.16403),
        0.30: (2.46532, -0.62257, -0.11657),
        0.50: (2.41896, -0.61677, -0.09271),
    }
    ia_key = min(_coeff.keys(), key=lambda k: abs(k - ia_p))
    c0, c1, c2 = _coeff[ia_key]
    log_tc = math.log10(max(tc_hr, 0.1))
    log_qu = c0 + c1 * log_tc + c2 * log_tc ** 2
    qu = 10 ** log_qu   # cfs per sq mi per inch of runoff

    qp = qu * area_sqmi * Q
    return round(qp, 2)


# ---------------------------------------------------------------------------
# Runoff result
# ---------------------------------------------------------------------------

@dataclass
class RunoffResult:
    cn: float
    rainfall_in: float
    runoff_depth_in: float
    abstraction_in: float
    retention_in: float
    runoff_fraction: float
    tc_hr: Optional[float] = None
    peak_discharge_cfs: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cn": round(self.cn, 1),
            "rainfall_in": round(self.rainfall_in, 3),
            "runoff_depth_in": round(self.runoff_depth_in, 3),
            "abstraction_in": round(self.abstraction_in, 3),
            "retention_in": round(self.retention_in, 3),
            "runoff_fraction": round(self.runoff_fraction, 4),
            "tc_hr": round(self.tc_hr, 3) if self.tc_hr else None,
            "peak_discharge_cfs": round(self.peak_discharge_cfs, 2) if self.peak_discharge_cfs else None,
        }


def compute_runoff(
    rainfall_in: float,
    cn: float,
    ia_ratio: float = 0.2,
    tc_hr: Optional[float] = None,
    area_sqmi: Optional[float] = None,
) -> RunoffResult:
    """Full runoff calculation returning a :class:`RunoffResult`."""
    S = 1000.0 / max(cn, 1.0) - 10.0
    Ia = ia_ratio * S
    Q = cn_runoff_depth(rainfall_in, cn, ia_ratio)
    abstraction = min(rainfall_in, Ia + (rainfall_in - Q - Ia if Q > 0 else 0))
    retention = rainfall_in - Q

    qp = None
    if tc_hr is not None and area_sqmi is not None:
        qp = peak_discharge_tr55(rainfall_in, cn, area_sqmi, tc_hr, ia_ratio)

    return RunoffResult(
        cn=cn,
        rainfall_in=rainfall_in,
        runoff_depth_in=round(Q, 4),
        abstraction_in=round(Ia, 4),
        retention_in=round(retention, 4),
        runoff_fraction=round(Q / rainfall_in, 4) if rainfall_in > 0 else 0.0,
        tc_hr=tc_hr,
        peak_discharge_cfs=qp,
    )
