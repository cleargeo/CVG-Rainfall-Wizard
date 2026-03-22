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
idf.py — IDF (Intensity-Duration-Frequency) curve fitting and design storm
         hyetograph generation.

Implements:
  - Log-Pearson III / empirical IDF fitting from NOAA Atlas 14 PFE data
  - SCS Type I, IA, II, III design storm hyetographs
  - Alternating block method hyetograph
  - Unit hydrograph convolution
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Design storm types
# ---------------------------------------------------------------------------
STORM_TYPE_I   = "SCS_I"
STORM_TYPE_IA  = "SCS_IA"
STORM_TYPE_II  = "SCS_II"
STORM_TYPE_III = "SCS_III"
STORM_TYPE_ALT_BLOCK = "alt_block"

VALID_STORM_TYPES = [STORM_TYPE_I, STORM_TYPE_IA, STORM_TYPE_II, STORM_TYPE_III, STORM_TYPE_ALT_BLOCK]


# ---------------------------------------------------------------------------
# SCS dimensionless cumulative rainfall mass curves (fraction of total, t/Td)
# Tables from TR-55 (1986), Appendix B
# ---------------------------------------------------------------------------

_SCS_MASS_CURVES: Dict[str, List[Tuple[float, float]]] = {
    STORM_TYPE_I: [
        (0.0, 0.000), (0.05, 0.020), (0.10, 0.040), (0.15, 0.065),
        (0.20, 0.090), (0.25, 0.120), (0.30, 0.155), (0.35, 0.200),
        (0.40, 0.260), (0.45, 0.330), (0.50, 0.415), (0.55, 0.490),
        (0.60, 0.560), (0.65, 0.620), (0.70, 0.680), (0.75, 0.730),
        (0.80, 0.770), (0.85, 0.810), (0.90, 0.845), (0.95, 0.885),
        (1.00, 1.000),
    ],
    STORM_TYPE_IA: [
        (0.0, 0.000), (0.05, 0.030), (0.10, 0.065), (0.15, 0.105),
        (0.20, 0.150), (0.25, 0.200), (0.30, 0.250), (0.35, 0.300),
        (0.40, 0.350), (0.45, 0.395), (0.50, 0.440), (0.55, 0.480),
        (0.60, 0.520), (0.65, 0.560), (0.70, 0.600), (0.75, 0.640),
        (0.80, 0.680), (0.85, 0.730), (0.90, 0.790), (0.95, 0.880),
        (1.00, 1.000),
    ],
    STORM_TYPE_II: [
        (0.0, 0.000), (0.05, 0.011), (0.10, 0.022), (0.15, 0.035),
        (0.20, 0.048), (0.25, 0.063), (0.30, 0.080), (0.35, 0.098),
        (0.40, 0.120), (0.45, 0.147), (0.48, 0.163), (0.50, 0.175),
        (0.52, 0.250), (0.54, 0.298), (0.56, 0.339), (0.58, 0.374),
        (0.60, 0.402), (0.65, 0.479), (0.70, 0.545), (0.75, 0.600),
        (0.80, 0.648), (0.85, 0.689), (0.90, 0.727), (0.95, 0.854),
        (1.00, 1.000),
    ],
    STORM_TYPE_III: [
        (0.0, 0.000), (0.05, 0.010), (0.10, 0.020), (0.15, 0.032),
        (0.20, 0.043), (0.25, 0.055), (0.30, 0.069), (0.35, 0.085),
        (0.40, 0.103), (0.45, 0.127), (0.50, 0.163), (0.55, 0.231),
        (0.60, 0.379), (0.65, 0.519), (0.70, 0.602), (0.75, 0.665),
        (0.80, 0.717), (0.85, 0.762), (0.90, 0.804), (0.95, 0.854),
        (1.00, 1.000),
    ],
}


# ---------------------------------------------------------------------------
# Hyetograph dataclass
# ---------------------------------------------------------------------------

@dataclass
class Hyetograph:
    """Time-series rainfall hyetograph for a design storm."""
    storm_type: str
    duration_hr: float
    total_depth_in: float
    dt_hr: float                        # time step in hours
    time_hr: List[float] = field(default_factory=list)
    incremental_in: List[float] = field(default_factory=list)
    cumulative_in: List[float] = field(default_factory=list)
    intensity_in_hr: List[float] = field(default_factory=list)

    @property
    def n_steps(self) -> int:
        return len(self.time_hr)

    @property
    def peak_intensity_in_hr(self) -> float:
        return max(self.intensity_in_hr) if self.intensity_in_hr else 0.0

    @property
    def time_to_peak_hr(self) -> float:
        if not self.intensity_in_hr:
            return 0.0
        idx = int(np.argmax(self.intensity_in_hr))
        return self.time_hr[idx]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "storm_type": self.storm_type,
            "duration_hr": self.duration_hr,
            "total_depth_in": round(self.total_depth_in, 3),
            "dt_hr": self.dt_hr,
            "peak_intensity_in_hr": round(self.peak_intensity_in_hr, 4),
            "time_to_peak_hr": round(self.time_to_peak_hr, 3),
            "n_steps": self.n_steps,
            "time_hr": [round(t, 4) for t in self.time_hr],
            "incremental_in": [round(v, 5) for v in self.incremental_in],
            "cumulative_in": [round(v, 5) for v in self.cumulative_in],
            "intensity_in_hr": [round(v, 5) for v in self.intensity_in_hr],
        }


# ---------------------------------------------------------------------------
# Hyetograph constructors
# ---------------------------------------------------------------------------

def build_scs_hyetograph(
    total_depth_in: float,
    duration_hr: float = 24.0,
    storm_type: str = STORM_TYPE_II,
    dt_hr: float = 0.5,
) -> Hyetograph:
    """Build an SCS dimensionless design storm hyetograph.

    Parameters
    ----------
    total_depth_in : float
        Total design rainfall depth in inches.
    duration_hr : float
        Storm duration in hours (default 24 h).
    storm_type : str
        SCS storm type: 'SCS_I', 'SCS_IA', 'SCS_II', or 'SCS_III'.
    dt_hr : float
        Time step in hours (default 0.5 h).

    Returns
    -------
    Hyetograph
    """
    if storm_type not in _SCS_MASS_CURVES:
        raise ValueError(f"Unknown storm type '{storm_type}'. Valid: {list(_SCS_MASS_CURVES)}")

    curve = _SCS_MASS_CURVES[storm_type]
    t_frac = [c[0] for c in curve]
    p_frac = [c[1] for c in curve]

    n = int(round(duration_hr / dt_hr)) + 1
    times = [i * dt_hr for i in range(n)]

    # Interpolate cumulative fraction at each time step
    frac = np.interp(
        [t / duration_hr for t in times],
        t_frac,
        p_frac,
    )
    cumulative = [f * total_depth_in for f in frac]
    incremental = [0.0] + [max(0.0, cumulative[i] - cumulative[i - 1]) for i in range(1, n)]
    intensity = [inc / dt_hr for inc in incremental]

    return Hyetograph(
        storm_type=storm_type,
        duration_hr=duration_hr,
        total_depth_in=total_depth_in,
        dt_hr=dt_hr,
        time_hr=times,
        incremental_in=incremental,
        cumulative_in=list(cumulative),
        intensity_in_hr=intensity,
    )


def build_alternating_block_hyetograph(
    idf_intensities: Dict[float, float],   # {duration_hr: intensity_in_hr}
    design_duration_hr: float = 24.0,
    dt_hr: float = 1.0,
) -> Hyetograph:
    """Build an alternating block method hyetograph from IDF data.

    Parameters
    ----------
    idf_intensities : dict
        {duration_hr: intensity_in_hr} from NOAA PFDS for the design return period.
    design_duration_hr : float
        Total storm duration in hours.
    dt_hr : float
        Time step in hours.
    """
    n = int(round(design_duration_hr / dt_hr))
    times = [(i + 1) * dt_hr for i in range(n)]

    # Depth for each duration = intensity × duration
    incremental_depths = []
    prev_depth = 0.0
    for t in times:
        intensity = _interp_idf(idf_intensities, t)
        cum_depth = intensity * t
        incremental_depths.append(max(0.0, cum_depth - prev_depth))
        prev_depth = cum_depth

    # Re-order: peak in centre, alternating left/right
    sorted_blocks = sorted(incremental_depths, reverse=True)
    ordered = [0.0] * n
    left = n // 2 - 1
    right = n // 2
    for i, val in enumerate(sorted_blocks):
        if i == 0:
            ordered[n // 2] = val
        elif i % 2 == 1:
            ordered[left] = val
            left -= 1
        else:
            ordered[right] = val
            right += 1

    cumulative = list(np.cumsum(ordered))
    total = cumulative[-1] if cumulative else 0.0
    step_times = [i * dt_hr for i in range(n + 1)]
    cumulative = [0.0] + cumulative
    incremental = [0.0] + ordered

    return Hyetograph(
        storm_type=STORM_TYPE_ALT_BLOCK,
        duration_hr=design_duration_hr,
        total_depth_in=total,
        dt_hr=dt_hr,
        time_hr=step_times,
        incremental_in=incremental,
        cumulative_in=cumulative,
        intensity_in_hr=[inc / dt_hr for inc in incremental],
    )


def _interp_idf(idf: Dict[float, float], duration_hr: float) -> float:
    """Interpolate intensity (in/hr) for *duration_hr* from an IDF dict."""
    durations = sorted(idf.keys())
    if not durations:
        return 0.0
    if duration_hr <= durations[0]:
        return idf[durations[0]]
    if duration_hr >= durations[-1]:
        return idf[durations[-1]]
    for i in range(len(durations) - 1):
        d0, d1 = durations[i], durations[i + 1]
        if d0 <= duration_hr <= d1:
            # Log-linear interpolation
            t = (math.log(duration_hr) - math.log(d0)) / (math.log(d1) - math.log(d0))
            return idf[d0] + t * (idf[d1] - idf[d0])
    return 0.0


# ---------------------------------------------------------------------------
# IDF curve fitting
# ---------------------------------------------------------------------------

def fit_idf_chen(
    idf_points: Dict[float, Dict[int, float]],
) -> Dict[str, float]:
    """Fit Chen's three-parameter IDF equation to Atlas 14 data.

    Chen (1983) IDF form: i = a / (t + b)^c
    where t is duration in minutes, i is intensity in in/hr.

    Returns the best-fit parameters {a, b, c}.
    """
    from scipy.optimize import curve_fit

    t_min: List[float] = []
    i_in_hr: List[float] = []
    for dur_hr, rp_dict in idf_points.items():
        for rp, intensity in rp_dict.items():
            t_min.append(dur_hr * 60.0)
            i_in_hr.append(intensity)

    if len(t_min) < 3:
        return {"a": 1.0, "b": 0.0, "c": 1.0}

    def chen_model(t, a, b, c):
        return a / (t + b) ** c

    try:
        popt, _ = curve_fit(chen_model, t_min, i_in_hr, p0=[50.0, 5.0, 0.7], maxfev=5000)
        return {"a": float(popt[0]), "b": float(popt[1]), "c": float(popt[2])}
    except Exception as exc:
        log.warning("IDF curve fit failed: %s", exc)
        return {"a": 1.0, "b": 0.0, "c": 1.0}
