# -*- coding: utf-8 -*-
# =============================================================================
# (c) Clearview Geographic LLC -- All Rights Reserved | Est. 2018
# CVG Rainfall Wizard — test_runoff.py
# =============================================================================
"""Unit tests for rainfall_wizard.runoff (NRCS CN method)."""

import pytest
from rainfall_wizard.runoff import (
    cn_runoff_depth,
    cn_runoff_series,
    compute_runoff,
    composite_cn,
    LandCoverArea,
    lookup_cn,
    tc_sheet_flow,
    tc_shallow_concentrated,
    time_of_concentration,
    peak_discharge_rational,
)


# ---------------------------------------------------------------------------
# CN Runoff depth
# ---------------------------------------------------------------------------

def test_no_runoff_when_rainfall_below_ia():
    """P < 0.2S → no runoff."""
    # CN=75, S=1000/75-10=3.33, Ia=0.667; rainfall=0.5 < Ia
    Q = cn_runoff_depth(rainfall_in=0.5, cn=75.0)
    assert Q == 0.0


def test_runoff_increases_with_rainfall():
    Qs = [cn_runoff_depth(p, cn=80.0) for p in [1.0, 2.0, 4.0, 6.0, 8.0]]
    for i in range(len(Qs) - 1):
        assert Qs[i] <= Qs[i + 1], "Runoff should increase with rainfall"


def test_cn98_nearly_all_runoff():
    """Near-impervious (CN=98) should have runoff ≈ rainfall."""
    Q = cn_runoff_depth(rainfall_in=5.0, cn=98.0)
    assert Q > 4.5  # >90% runoff


def test_cn30_very_little_runoff():
    """Dense forest / low CN should absorb most rainfall."""
    Q = cn_runoff_depth(rainfall_in=3.0, cn=30.0)
    assert Q < 0.5  # <17% runoff


def test_runoff_never_exceeds_rainfall():
    for cn in [40, 60, 80, 95, 98]:
        for p in [1.0, 3.0, 6.0, 10.0]:
            Q = cn_runoff_depth(p, cn)
            assert Q <= p + 0.001, f"Runoff ({Q:.3f}) > rainfall ({p}) for CN={cn}"


def test_cn_clamped_at_99():
    """CN=100 would cause division by zero; should be clamped."""
    Q = cn_runoff_depth(5.0, cn=100.0)
    assert Q >= 0.0


def test_known_value_cn75_6in():
    """Known: CN=75, P=6 in → Q ≈ 3.20 in (TR-55 Table 2-1)."""
    Q = cn_runoff_depth(6.0, cn=75.0)
    assert abs(Q - 3.20) < 0.10


def test_runoff_series_cumulative():
    Ps = [0.0, 0.5, 1.0, 2.0, 3.0, 5.0]
    runoff, incremental = cn_runoff_series(Ps, cn=80.0)
    # Cumulative runoff should be non-decreasing
    for i in range(len(runoff) - 1):
        assert runoff[i] <= runoff[i + 1]
    # All incremental values should be non-negative
    for v in incremental:
        assert v >= 0.0


# ---------------------------------------------------------------------------
# Composite CN
# ---------------------------------------------------------------------------

def test_composite_cn_single_cover():
    lcs = [LandCoverArea("impervious", cn=98.0, area_acres=10.0)]
    assert abs(composite_cn(lcs) - 98.0) < 0.01


def test_composite_cn_weighted():
    lcs = [
        LandCoverArea("forest", cn=55.0, area_acres=50.0),
        LandCoverArea("impervious", cn=98.0, area_acres=50.0),
    ]
    cn = composite_cn(lcs)
    assert abs(cn - 76.5) < 0.1  # (55+98)/2


def test_composite_cn_empty_returns_fallback():
    assert composite_cn([]) == 75.0


# ---------------------------------------------------------------------------
# CN lookup table
# ---------------------------------------------------------------------------

def test_lookup_cn_impervious():
    for hsg in ["A", "B", "C", "D"]:
        assert lookup_cn("impervious", hsg) == 98


def test_lookup_cn_unknown_returns_none():
    assert lookup_cn("unknown_cover", "A") is None


# ---------------------------------------------------------------------------
# Time of concentration
# ---------------------------------------------------------------------------

def test_tc_sheet_flow_positive():
    tc = tc_sheet_flow(
        rainfall_2yr_24hr_in=3.5,
        n=0.4,
        slope_ftft=0.005,
        length_ft=100.0,
    )
    assert tc > 0.0


def test_tc_sheet_flow_zero_slope():
    tc = tc_sheet_flow(3.5, n=0.4, slope_ftft=0.0, length_ft=100.0)
    assert tc == 0.0


def test_tc_shallow_concentrated_paved_faster():
    tc_paved = tc_shallow_concentrated(500.0, 0.02, surface="paved")
    tc_unpaved = tc_shallow_concentrated(500.0, 0.02, surface="unpaved")
    assert tc_paved < tc_unpaved


def test_time_of_concentration_sums():
    tc = time_of_concentration(0.1, 0.2, 0.3)
    assert abs(tc - 0.6) < 0.0001


# ---------------------------------------------------------------------------
# Rational method
# ---------------------------------------------------------------------------

def test_rational_method_basic():
    Q = peak_discharge_rational(C=0.8, intensity_in_hr=2.0, area_acres=10.0)
    assert abs(Q - 16.0) < 0.01  # 0.8 * 2.0 * 10.0


# ---------------------------------------------------------------------------
# compute_runoff convenience function
# ---------------------------------------------------------------------------

def test_compute_runoff_result_fields():
    result = compute_runoff(rainfall_in=5.0, cn=75.0)
    assert 0 <= result.runoff_depth_in <= 5.0
    assert 0 <= result.runoff_fraction <= 1.0
    d = result.to_dict()
    assert "runoff_depth_in" in d
    assert "cn" in d
