# -*- coding: utf-8 -*-
# =============================================================================
# (c) Clearview Geographic LLC -- All Rights Reserved | Est. 2018
# CVG Rainfall Wizard — test_idf.py
# =============================================================================
"""Unit tests for rainfall_wizard.idf (hyetograph generation)."""

import pytest
import numpy as np
from rainfall_wizard.idf import (
    build_scs_hyetograph,
    build_alternating_block_hyetograph,
    STORM_TYPE_I, STORM_TYPE_IA, STORM_TYPE_II, STORM_TYPE_III,
    STORM_TYPE_ALT_BLOCK,
    VALID_STORM_TYPES,
)


# ---------------------------------------------------------------------------
# SCS hyetograph
# ---------------------------------------------------------------------------

def test_scs_hyetograph_total_depth():
    """Cumulative total should equal input depth."""
    hyet = build_scs_hyetograph(total_depth_in=6.5, duration_hr=24.0, storm_type=STORM_TYPE_II)
    assert abs(hyet.cumulative_in[-1] - 6.5) < 0.01


def test_scs_hyetograph_time_steps():
    hyet = build_scs_hyetograph(total_depth_in=5.0, duration_hr=24.0,
                                 storm_type=STORM_TYPE_II, dt_hr=0.5)
    assert hyet.n_steps == 49  # 0 to 24 in 0.5 steps = 49 points


def test_scs_type_ii_peak_around_midpoint():
    """Type II: peak intensity should be near t=12 hr."""
    hyet = build_scs_hyetograph(5.0, 24.0, STORM_TYPE_II, dt_hr=0.5)
    tp = hyet.time_to_peak_hr
    assert 11.0 <= tp <= 13.0


def test_scs_type_iii_peak_around_midpoint():
    """Type III: peak intensity is at t=13–15 hr for a 24-hr storm.

    TR-55 Table B-3 shows the steepest mass-curve slope between t/D = 0.55
    and 0.60, which maps to 13.2–14.4 hrs on a 24-hour design storm.
    With dt=0.5 hr the argmax of intensity lands at ~14.0 hrs.
    """
    hyet = build_scs_hyetograph(5.0, 24.0, STORM_TYPE_III, dt_hr=0.5)
    tp = hyet.time_to_peak_hr
    assert 12.0 <= tp <= 15.0


def test_scs_incremental_nonnegative():
    hyet = build_scs_hyetograph(6.0, 24.0, STORM_TYPE_II)
    for v in hyet.incremental_in:
        assert v >= -0.0001  # allow tiny floating-point noise


def test_all_scs_storm_types_run():
    for st in [STORM_TYPE_I, STORM_TYPE_IA, STORM_TYPE_II, STORM_TYPE_III]:
        hyet = build_scs_hyetograph(5.0, 24.0, st, dt_hr=1.0)
        assert hyet.n_steps == 25
        assert abs(hyet.cumulative_in[-1] - 5.0) < 0.01


def test_invalid_storm_type_raises():
    with pytest.raises(ValueError):
        build_scs_hyetograph(5.0, storm_type="SCS_IV")


def test_hyetograph_to_dict():
    hyet = build_scs_hyetograph(5.0, 24.0, STORM_TYPE_II, dt_hr=1.0)
    d = hyet.to_dict()
    assert d["storm_type"] == STORM_TYPE_II
    assert d["total_depth_in"] == 5.0
    assert "peak_intensity_in_hr" in d
    assert d["n_steps"] == 25


# ---------------------------------------------------------------------------
# Alternating block hyetograph
# ---------------------------------------------------------------------------

def test_alternating_block_basic():
    idf = {1.0: 4.0, 2.0: 2.5, 3.0: 1.8, 6.0: 1.2, 12.0: 0.8, 24.0: 0.5}
    hyet = build_alternating_block_hyetograph(idf, design_duration_hr=24.0, dt_hr=1.0)
    assert hyet.storm_type == STORM_TYPE_ALT_BLOCK
    assert hyet.n_steps > 0


def test_alternating_block_peak_near_center():
    """Peak block should be near the centre of the storm."""
    idf = {1.0: 5.0, 2.0: 3.0, 3.0: 2.2, 6.0: 1.5, 12.0: 1.0}
    hyet = build_alternating_block_hyetograph(idf, design_duration_hr=12.0, dt_hr=1.0)
    tp = hyet.time_to_peak_hr
    assert 5.0 <= tp <= 7.0


# ---------------------------------------------------------------------------
# Peak intensity ordering
# ---------------------------------------------------------------------------

def test_type_ii_higher_peak_than_type_i():
    """Type II should produce a higher peak intensity than Type I for same depth."""
    h1 = build_scs_hyetograph(5.0, 24.0, STORM_TYPE_I, dt_hr=0.5)
    h2 = build_scs_hyetograph(5.0, 24.0, STORM_TYPE_II, dt_hr=0.5)
    assert h2.peak_intensity_in_hr > h1.peak_intensity_in_hr
