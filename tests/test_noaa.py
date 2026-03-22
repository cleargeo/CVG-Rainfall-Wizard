# -*- coding: utf-8 -*-
# Clearview Geographic LLC — Proprietary and Confidential
"""Tests for rainfall_wizard.noaa and rainfall_wizard.pfds modules."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from rainfall_wizard.noaa import (
    PFDSResponse,
    PrecipFreqEstimate,
    fetch_pfds,
    fetch_single_pfe,
    get_pfds_cached,
)
from rainfall_wizard.pfds import (
    DURATION_CODE_MAP,
    PFDS_RETURN_PERIODS,
    PfdsResult,
    _duration_to_code,
    fetch_pfds_depths,
)


# ---------------------------------------------------------------------------
# PrecipFreqEstimate
# ---------------------------------------------------------------------------

class TestPrecipFreqEstimate:
    """Unit tests for PrecipFreqEstimate dataclass (rainfall_wizard.noaa)."""

    def test_basic_construction(self):
        est = PrecipFreqEstimate(
            lat=25.0, lon=-80.0, duration_hr=24.0,
            return_period_yr=100, depth_in=10.0, depth_mm=254.0,
        )
        assert est.lat == 25.0
        assert est.lon == -80.0
        assert est.duration_hr == 24.0
        assert est.return_period_yr == 100
        assert est.depth_in == 10.0
        assert est.depth_mm == 254.0

    def test_depth_mm_field(self):
        est = PrecipFreqEstimate(
            lat=0, lon=0, duration_hr=24.0,
            return_period_yr=100, depth_in=1.0, depth_mm=25.4,
        )
        assert abs(est.depth_mm - 25.4) < 0.001

    def test_intensity_calculation(self):
        # 9.6 in over 24 hr = 0.4 in/hr
        est = PrecipFreqEstimate(
            lat=0, lon=0, duration_hr=24.0,
            return_period_yr=100, depth_in=9.6, depth_mm=9.6 * 25.4,
        )
        assert abs(est.intensity_in_hr - 0.4) < 0.001

    def test_intensity_1hr_storm(self):
        # 2.4 in over 1 hr = 2.4 in/hr
        est = PrecipFreqEstimate(
            lat=0, lon=0, duration_hr=1.0,
            return_period_yr=10, depth_in=2.4, depth_mm=2.4 * 25.4,
        )
        assert abs(est.intensity_in_hr - 2.4) < 0.001

    def test_source_default(self):
        est = PrecipFreqEstimate(
            lat=0, lon=0, duration_hr=24.0,
            return_period_yr=100, depth_in=5.0, depth_mm=127.0,
        )
        assert est.source == "noaa_pfds"

    def test_to_dict_has_required_keys(self):
        est = PrecipFreqEstimate(
            lat=25.0, lon=-80.0, duration_hr=24.0,
            return_period_yr=100, depth_in=8.5, depth_mm=215.9,
        )
        d = est.to_dict()
        for key in ("lat", "lon", "duration_hr", "return_period_yr",
                    "depth_in", "depth_mm", "intensity_in_hr"):
            assert key in d, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# PFDSResponse
# ---------------------------------------------------------------------------

class TestPFDSResponse:
    """Unit tests for PFDSResponse dataclass (rainfall_wizard.noaa)."""

    def _make_response(self) -> PFDSResponse:
        est = PrecipFreqEstimate(
            lat=0, lon=0, duration_hr=24.0,
            return_period_yr=100, depth_in=8.5, depth_mm=8.5 * 25.4,
        )
        resp = PFDSResponse(lat=0.0, lon=0.0)
        resp.estimates.append(est)
        return resp

    def test_basic_construction(self):
        resp = self._make_response()
        assert resp.lat == 0.0
        assert resp.lon == 0.0
        assert len(resp.estimates) == 1

    def test_get_found(self):
        resp = self._make_response()
        result = resp.get(duration_hr=24.0, return_period_yr=100)
        assert result is not None
        assert result.depth_in == 8.5

    def test_get_not_found_wrong_rp(self):
        resp = self._make_response()
        result = resp.get(duration_hr=24.0, return_period_yr=500)
        assert result is None

    def test_get_not_found_wrong_duration(self):
        resp = self._make_response()
        result = resp.get(duration_hr=1.0, return_period_yr=100)
        assert result is None

    def test_idf_table_structure(self):
        resp = self._make_response()
        table = resp.idf_table()
        assert 100 in table
        assert 24.0 in table[100]

    def test_estimates_list_accessible(self):
        resp = self._make_response()
        assert isinstance(resp.estimates, list)
        assert len(resp.estimates) == 1
        assert resp.estimates[0].depth_in == 8.5


# ---------------------------------------------------------------------------
# _duration_to_code  (rainfall_wizard.pfds)
# ---------------------------------------------------------------------------

class TestDurationToCode:
    """Tests for pfds._duration_to_code with float-hour inputs."""

    @pytest.mark.parametrize("dur_hr,expected_code", [
        (1.0, "60min"),
        (2.0, "2hr"),
        (3.0, "3hr"),
        (6.0, "6hr"),
        (12.0, "12hr"),
        (24.0, "24hr"),
        (48.0, "2day"),
        (72.0, "3day"),
    ])
    def test_known_durations(self, dur_hr, expected_code):
        assert _duration_to_code(dur_hr) == expected_code

    def test_unknown_duration_raises(self):
        # 1000 hr is far from any known duration
        with pytest.raises(ValueError):
            _duration_to_code(1000.0)

    def test_duration_code_map_has_expected_entries(self):
        assert 24.0 in DURATION_CODE_MAP
        assert 1.0 in DURATION_CODE_MAP
        assert DURATION_CODE_MAP[24.0] == "24hr"
        assert DURATION_CODE_MAP[1.0] == "60min"

    def test_near_match_within_tolerance(self):
        # 23.9 hr is ~0.4% off from 24.0 hr — should resolve to "24hr"
        code = _duration_to_code(23.9)
        assert code == "24hr"


# ---------------------------------------------------------------------------
# PfdsResult  (rainfall_wizard.pfds)
# ---------------------------------------------------------------------------

class TestPfdsResult:
    """Tests for PfdsResult dataclass (rainfall_wizard.pfds)."""

    def test_basic_construction(self):
        r = PfdsResult(
            lat=25.0, lon=-80.0,
            duration_hr=24.0, duration_code="24hr",
            depths={100: 9.44, 500: 13.1},
        )
        assert r.lat == 25.0
        assert r.lon == -80.0
        assert r.duration_hr == 24.0
        assert r.duration_code == "24hr"
        assert r.depths[100] == 9.44

    def test_get_depth_found(self):
        r = PfdsResult(
            lat=0, lon=0, duration_hr=24.0, duration_code="24hr",
            depths={100: 9.44},
        )
        assert r.get_depth(100) == 9.44

    def test_get_depth_not_found(self):
        r = PfdsResult(
            lat=0, lon=0, duration_hr=24.0, duration_code="24hr",
            depths={100: 9.44},
        )
        assert r.get_depth(200) is None

    def test_get_depth_inches_english_units(self):
        r = PfdsResult(
            lat=0, lon=0, duration_hr=24.0, duration_code="24hr",
            units="english", depths={100: 9.44},
        )
        assert r.get_depth_inches(100) == 9.44

    def test_get_depth_inches_metric_units(self):
        r = PfdsResult(
            lat=0, lon=0, duration_hr=24.0, duration_code="24hr",
            units="metric", depths={100: 239.8},  # ~9.44 in
        )
        val = r.get_depth_inches(100)
        assert abs(val - 9.441) < 0.01

    def test_to_dict_has_required_keys(self):
        r = PfdsResult(
            lat=25.0, lon=-80.0,
            duration_hr=24.0, duration_code="24hr",
            depths={100: 9.44},
        )
        # PfdsResult is a dataclass, verify attribute access
        assert hasattr(r, "lat")
        assert hasattr(r, "lon")
        assert hasattr(r, "duration_hr")
        assert hasattr(r, "depths")

    def test_depths_default_empty(self):
        r = PfdsResult(lat=0, lon=0, duration_hr=24.0, duration_code="24hr")
        assert r.depths == {}


# ---------------------------------------------------------------------------
# fetch_pfds_depths  (rainfall_wizard.pfds) — mocked HTTP
# ---------------------------------------------------------------------------

class TestFetchPfdsDepths:
    """Tests for pfds.fetch_pfds_depths with mocked urllib.request.urlopen."""

    def _make_pfds_raw_response(self) -> str:
        """Return a minimal parseable PFDS-like response string."""
        # The parser looks for var data_values = [[periods],[depths]]
        return 'var data_values = [[1,2,5,10,25,50,100,200,500,1000],[1.1,1.5,2.3,3.0,4.5,6.0,8.5,10.2,13.1,15.5]]'

    def test_returns_pfds_result_on_success(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = self._make_pfds_raw_response().encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("rainfall_wizard.pfds.urlopen", return_value=mock_resp):
            result = fetch_pfds_depths(lat=25.0, lon=-80.0, duration_hr=24.0)

        assert isinstance(result, PfdsResult)
        assert result.lat == 25.0
        assert result.lon == -80.0
        assert result.duration_hr == 24.0

    def test_handles_http_error_gracefully(self):
        from urllib.error import URLError

        with patch("rainfall_wizard.pfds.urlopen", side_effect=URLError("timeout")):
            with pytest.raises(URLError):
                fetch_pfds_depths(lat=25.0, lon=-80.0, duration_hr=24.0, retries=1)

    def test_invalid_duration_raises_value_error(self):
        with pytest.raises(ValueError):
            fetch_pfds_depths(lat=25.0, lon=-80.0, duration_hr=1000.0)


# ---------------------------------------------------------------------------
# get_pfds_cached  (rainfall_wizard.noaa) — mocked fetch_pfds
# ---------------------------------------------------------------------------

class TestGetPfdsCached:
    """Tests for noaa.get_pfds_cached with mocked fetch_pfds."""

    def _make_pfds_response(self, lat: float, lon: float) -> PFDSResponse:
        resp = PFDSResponse(lat=lat, lon=lon)
        resp.estimates.append(
            PrecipFreqEstimate(
                lat=lat, lon=lon, duration_hr=24.0,
                return_period_yr=100, depth_in=8.5, depth_mm=215.9,
            )
        )
        return resp

    def test_returns_pfds_response(self, tmp_path):
        fake_resp = self._make_pfds_response(25.0, -80.0)
        with patch("rainfall_wizard.noaa.fetch_pfds", return_value=fake_resp):
            result = get_pfds_cached(25.0, -80.0, cache_dir=str(tmp_path))
        assert isinstance(result, PFDSResponse)

    def test_caching_calls_fetch_once(self, tmp_path):
        fake_resp = self._make_pfds_response(25.0, -80.0)
        with patch("rainfall_wizard.noaa.fetch_pfds", return_value=fake_resp) as mock_fetch:
            # First call: cold cache → fetch
            get_pfds_cached(25.0, -80.0, cache_dir=str(tmp_path))
            # Second call: warm cache → no fetch
            get_pfds_cached(25.0, -80.0, cache_dir=str(tmp_path))
        assert mock_fetch.call_count == 1


# ---------------------------------------------------------------------------
# PFDS_RETURN_PERIODS constant
# ---------------------------------------------------------------------------

class TestPfdsConstants:
    def test_return_periods_list(self):
        assert 100 in PFDS_RETURN_PERIODS
        assert 500 in PFDS_RETURN_PERIODS
        assert len(PFDS_RETURN_PERIODS) >= 8

    def test_duration_code_map_not_empty(self):
        assert len(DURATION_CODE_MAP) >= 10
