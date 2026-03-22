# -*- coding: utf-8 -*-
# =============================================================================
# (c) Clearview Geographic LLC -- All Rights Reserved | Est. 2018
# CVG Rainfall Wizard — pytest conftest
# =============================================================================
"""Shared pytest fixtures for the Rainfall Wizard test suite."""

import numpy as np
import pytest


@pytest.fixture
def sample_dem_array():
    """5×5 DEM in feet (low-lying area suitable for ponding tests)."""
    return np.array([
        [5.0, 5.2, 5.8, 6.5, 7.2],
        [4.8, 5.0, 5.4, 6.0, 6.8],
        [4.5, 4.8, 5.2, 5.8, 6.5],
        [4.2, 4.5, 5.0, 5.5, 6.2],
        [4.0, 4.2, 4.7, 5.2, 6.0],
    ], dtype="float32")


@pytest.fixture
def nodata():
    return -9999.0


@pytest.fixture
def basic_rainfall_config():
    from rainfall_wizard.config import RainfallConfig
    return RainfallConfig(
        lat=29.65,
        lon=-82.32,
        duration_hr=24.0,
        return_period_yr=100,
        curve_number=75.0,
        dem_path="fake_dem.tif",
        dem_unit="ft",
        output_path="output_test/depth.tif",
    )
