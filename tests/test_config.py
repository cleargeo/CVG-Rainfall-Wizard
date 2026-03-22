# -*- coding: utf-8 -*-
# =============================================================================
# (c) Clearview Geographic LLC -- All Rights Reserved | Est. 2018
# CVG Rainfall Wizard — test_config.py
# =============================================================================
"""Unit tests for rainfall_wizard.config."""

import pytest
from rainfall_wizard.config import RainfallConfig, CompoundFloodConfig


# ---------------------------------------------------------------------------
# RainfallConfig
# ---------------------------------------------------------------------------

def test_default_config():
    cfg = RainfallConfig()
    assert cfg.lat == 0.0
    assert cfg.lon == 0.0
    assert cfg.duration_hr == 24.0
    assert cfg.return_period_yr == 100
    assert cfg.curve_number == 75.0
    assert cfg.dem_unit == "m"
    assert cfg.output_unit == "ft"
    assert cfg.pfds_units == "english"


def test_custom_config():
    cfg = RainfallConfig(
        lat=29.65, lon=-82.32,
        duration_hr=6.0,
        return_period_yr=25,
        curve_number=85.0,
        dem_path="test.tif",
        project_name="test_project",
    )
    assert cfg.lat == 29.65
    assert cfg.lon == -82.32
    assert cfg.duration_hr == 6.0
    assert cfg.return_period_yr == 25
    assert abs(cfg.curve_number - 85.0) < 0.001
    assert cfg.dem_path == "test.tif"
    assert cfg.project_name == "test_project"


def test_cn_range():
    """CN should accept 0–100 range."""
    for cn in [0.0, 25.0, 50.0, 75.0, 98.0, 100.0]:
        cfg = RainfallConfig(curve_number=cn)
        assert cfg.curve_number == cn


def test_valid_durations():
    """Standard Atlas 14 durations should be accepted."""
    for dur in [0.5, 1.0, 2.0, 3.0, 6.0, 12.0, 24.0, 48.0, 72.0]:
        cfg = RainfallConfig(duration_hr=dur)
        assert cfg.duration_hr == dur


def test_valid_return_periods():
    for rp in [1, 2, 5, 10, 25, 50, 100, 200, 500, 1000]:
        cfg = RainfallConfig(return_period_yr=rp)
        assert cfg.return_period_yr == rp


def test_pfds_units_options():
    for units in ["english", "metric"]:
        cfg = RainfallConfig(pfds_units=units)
        assert cfg.pfds_units == units


def test_output_unit_options():
    for unit in ["ft", "m"]:
        cfg = RainfallConfig(output_unit=unit)
        assert cfg.output_unit == unit


def test_dem_unit_options():
    for unit in ["m", "ft"]:
        cfg = RainfallConfig(dem_unit=unit)
        assert cfg.dem_unit == unit


def test_min_depth_default():
    cfg = RainfallConfig()
    assert cfg.min_depth == 0.0


def test_notes_field():
    cfg = RainfallConfig(notes="This is a test run")
    assert cfg.notes == "This is a test run"


# ---------------------------------------------------------------------------
# CompoundFloodConfig
# ---------------------------------------------------------------------------

def test_compound_flood_defaults():
    cfg = CompoundFloodConfig()
    assert cfg.storm_surge_wse_ft is None
    assert cfg.rainfall_runoff_ft is None
    assert cfg.slr_ft is None
    assert cfg.combination_method == "additive"
    assert cfg.output_unit == "ft"


def test_compound_flood_additive():
    cfg = CompoundFloodConfig(
        storm_surge_wse_ft=8.5,
        rainfall_runoff_ft=1.2,
        slr_ft=1.0,
        combination_method="additive",
    )
    assert cfg.storm_surge_wse_ft == 8.5
    assert cfg.rainfall_runoff_ft == 1.2
    assert cfg.slr_ft == 1.0
    assert cfg.combination_method == "additive"


def test_compound_flood_surge_plus_slr():
    cfg = CompoundFloodConfig(
        storm_surge_wse_ft=8.5,
        slr_ft=1.0,
        combination_method="surge_plus_slr",
    )
    assert cfg.combination_method == "surge_plus_slr"
    assert cfg.rainfall_runoff_ft is None


def test_compound_flood_rainfall_only():
    cfg = CompoundFloodConfig(
        rainfall_runoff_ft=2.5,
        combination_method="rainfall_only",
    )
    assert cfg.combination_method == "rainfall_only"
    assert cfg.storm_surge_wse_ft is None


def test_config_vars_accessible():
    """Verify all fields are accessible via vars() for report writing."""
    cfg = RainfallConfig(lat=29.0, lon=-82.0, project_name="test")
    d = vars(cfg)
    assert "lat" in d
    assert "lon" in d
    assert "project_name" in d
    assert "curve_number" in d
