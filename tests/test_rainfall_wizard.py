# -*- coding: utf-8 -*-
"""Tests for the CVG Rainfall Wizard package.
Network tests (PFDS queries) are marked integration and skipped by default.
"""
from __future__ import annotations
import pytest
from rainfall_wizard.config import RainfallConfig, CompoundFloodConfig
from rainfall_wizard.core import compute_runoff_cn, RainfallResult
from rainfall_wizard.pfds import PfdsResult, _duration_to_code, DURATION_CODE_MAP


# ---------------------------------------------------------------------------
# RainfallConfig
# ---------------------------------------------------------------------------

class TestRainfallConfig:
    def test_defaults(self):
        cfg = RainfallConfig()
        assert cfg.duration_hr == 24.0
        assert cfg.return_period_yr == 100
        assert cfg.curve_number == 75.0
        assert cfg.output_unit == "ft"

    def test_custom(self):
        cfg = RainfallConfig(lat=24.556, lon=-81.807, curve_number=85, return_period_yr=500)
        assert cfg.lat == pytest.approx(24.556)
        assert cfg.curve_number == 85
        assert cfg.return_period_yr == 500


# ---------------------------------------------------------------------------
# NRCS TR-55 compute_runoff_cn
# ---------------------------------------------------------------------------

class TestComputeRunoffCn:
    """Scientific validation of the NRCS TR-55 Curve Number runoff equation."""

    def test_zero_precipitation_gives_zero_runoff(self):
        assert compute_runoff_cn(0.0, 75) == pytest.approx(0.0)

    def test_below_initial_abstraction_gives_zero(self):
        # S = 1000/75 - 10 = 3.333in; Ia = 0.2*S = 0.667in
        # P = 0.5in < Ia → Q = 0
        assert compute_runoff_cn(0.5, 75) == pytest.approx(0.0)

    def test_high_cn_gives_more_runoff_than_low_cn(self):
        q_low = compute_runoff_cn(4.0, 55)
        q_high = compute_runoff_cn(4.0, 90)
        assert q_high > q_low

    def test_more_rain_gives_more_runoff(self):
        q1 = compute_runoff_cn(3.0, 75)
        q2 = compute_runoff_cn(6.0, 75)
        assert q2 > q1

    def test_cn_100_raises(self):
        with pytest.raises(ValueError):
            compute_runoff_cn(5.0, 100)

    def test_cn_0_raises(self):
        with pytest.raises(ValueError):
            compute_runoff_cn(5.0, 0)

    def test_negative_precip_raises(self):
        with pytest.raises(ValueError):
            compute_runoff_cn(-1.0, 75)

    def test_cn98_near_100pct_runoff(self):
        # CN=98 (nearly impervious) with heavy rain → Q ≈ P
        Q = compute_runoff_cn(10.0, 98)
        assert Q > 9.0  # > 90% runoff

    def test_known_value_cn75_p4(self):
        # TR-55 example: CN=75, P=4.0in → Q ≈ 1.60in
        Q = compute_runoff_cn(4.0, 75)
        # S=3.333, Ia=0.667, Q=(3.333)^2/(3.333+3.333) ≈ 1.667
        assert 1.5 < Q < 1.9

    def test_runoff_always_non_negative(self):
        for cn in [50, 65, 75, 85, 95]:
            for p in [0.1, 1.0, 5.0, 10.0]:
                assert compute_runoff_cn(p, cn) >= 0.0


# ---------------------------------------------------------------------------
# PFDS duration code mapping
# ---------------------------------------------------------------------------

class TestDurationToCode:
    def test_exact_24(self):
        assert _duration_to_code(24.0) == "24hr"

    def test_exact_1(self):
        assert _duration_to_code(1.0) == "60min"

    def test_near_24_within_5pct(self):
        code = _duration_to_code(24.5)
        assert code == "24hr"

    def test_all_standard_durations_mapped(self):
        for hr in DURATION_CODE_MAP:
            assert _duration_to_code(hr) == DURATION_CODE_MAP[hr]

    def test_unsupported_duration_raises(self):
        # 150 hr is not within 5% of any supported duration (nearest is 168hr / 7day at 12% off)
        with pytest.raises(ValueError):
            _duration_to_code(150.0)


# ---------------------------------------------------------------------------
# PfdsResult
# ---------------------------------------------------------------------------

class TestPfdsResult:
    def test_get_depth_returns_none_for_missing(self):
        r = PfdsResult(depths={100: 9.4})
        assert r.get_depth(500) is None

    def test_get_depth_returns_value(self):
        r = PfdsResult(depths={100: 9.4})
        assert r.get_depth(100) == pytest.approx(9.4)

    def test_get_depth_inches_from_english(self):
        r = PfdsResult(depths={100: 9.4}, units="english")
        assert r.get_depth_inches(100) == pytest.approx(9.4)

    def test_get_depth_inches_from_metric(self):
        r = PfdsResult(depths={100: 239.0}, units="metric")
        assert r.get_depth_inches(100) == pytest.approx(239.0 / 25.4, abs=0.01)

    def test_post_init_sets_empty_dicts(self):
        r = PfdsResult()
        assert r.depths == {}
        assert r.lower_ci == {}
        assert r.upper_ci == {}


# ---------------------------------------------------------------------------
# CompoundFloodConfig
# ---------------------------------------------------------------------------

class TestCompoundFloodConfig:
    def test_defaults(self):
        cfg = CompoundFloodConfig()
        assert cfg.combination_method == "additive"
        assert cfg.storm_surge_wse_ft is None
        assert cfg.rainfall_runoff_ft is None
        assert cfg.slr_ft is None

    def test_custom(self):
        cfg = CompoundFloodConfig(storm_surge_wse_ft=8.5, slr_ft=1.64,
                                   rainfall_runoff_ft=0.25, combination_method="additive")
        assert cfg.storm_surge_wse_ft == 8.5


# ---------------------------------------------------------------------------
# Integration bridge (wizards.py compound functions)
# ---------------------------------------------------------------------------

class TestCompoundFunctions:
    def test_additive_combination(self):
        from storm_surge_wizard.wizards import combine_surge_rainfall
        r = combine_surge_rainfall(8.5, 0.3, slr=1.64, unit="ft")
        assert r["total_wse"] == pytest.approx(10.44, abs=0.01)
        assert r["method"] == "additive"

    def test_surge_plus_slr(self):
        from storm_surge_wizard.wizards import combine_surge_rainfall
        r = combine_surge_rainfall(8.5, 0.3, slr=1.64, unit="ft",
                                   combination_method="surge_plus_slr")
        assert r["total_wse"] == pytest.approx(10.14, abs=0.01)

    def test_rainfall_only(self):
        from storm_surge_wizard.wizards import combine_surge_rainfall
        r = combine_surge_rainfall(8.5, 0.3, slr=1.64, unit="ft",
                                   combination_method="rainfall_only")
        assert r["total_wse"] == pytest.approx(0.3, abs=0.001)

    def test_regulatory_note_present(self):
        from storm_surge_wizard.wizards import combine_surge_rainfall
        r = combine_surge_rainfall(8.5, 0.3)
        assert "regulatory_note" in r
        assert len(r["regulatory_note"]) > 20
