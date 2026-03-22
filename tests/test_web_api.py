# -*- coding: utf-8 -*-
# (c) Clearview Geographic LLC -- All Rights Reserved
from __future__ import annotations
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from rainfall_wizard.web_api import create_app


@pytest.fixture(scope='module')
def client():
    return TestClient(create_app())


def _mock_pfe():
    from rainfall_wizard.noaa import PrecipFreqEstimate
    return PrecipFreqEstimate(lat=29.65,lon=-82.32,duration_hr=24.0,return_period_yr=100,depth_in=8.5,depth_mm=215.9)


def _mock_pfds_resp():
    from rainfall_wizard.noaa import PFDSResponse
    resp = MagicMock(spec=PFDSResponse)
    resp.state = 'FL'; resp.county = 'Alachua'
    resp.atlas_series = 'Volume 2'
    resp.estimates = [_mock_pfe()]
    resp.get.return_value = _mock_pfe()
    return resp


class TestRootEndpoint:
    def test_root_200(self, client): assert client.get('/').status_code == 200
    def test_root_tool(self, client): assert client.get('/').json()['tool'] == 'CVG Rainfall Wizard'
    def test_root_status_ok(self, client): assert client.get('/').json()['status'] == 'ok'
    def test_root_has_version(self, client): assert 'version' in client.get('/').json()
    def test_root_has_copyright(self, client): assert 'copyright' in client.get('/').json()


class TestPfdsEndpoint:
    def test_pfds_ok_with_mock(self, client):
        # patch at the noaa module level (lazy import inside endpoint)
        with patch('rainfall_wizard.noaa.get_pfds_cached', return_value=_mock_pfds_resp()):
            r = client.get('/api/pfds', params={'lat': 29.65, 'lon': -82.32})
        assert r.status_code == 200
    def test_pfds_503_on_exception(self, client):
        with patch('rainfall_wizard.noaa.get_pfds_cached', side_effect=RuntimeError('net err')):
            r = client.get('/api/pfds', params={'lat': 29.65, 'lon': -82.32})
        assert r.status_code == 503
    def test_pfds_404_on_missing_data(self, client):
        resp = _mock_pfds_resp(); resp.get.return_value = None
        with patch('rainfall_wizard.noaa.get_pfds_cached', return_value=resp):
            r = client.get('/api/pfds', params={'lat': 29.65, 'lon': -82.32, 'return_period_yr': 999})
        assert r.status_code == 404
    def test_pfds_missing_lat_422(self, client):
        r = client.get('/api/pfds', params={'lon': -82.32})
        assert r.status_code == 422


class TestRunoffEndpoint:
    def test_runoff_200(self, client):
        r = client.get('/api/runoff', params={'rainfall_in': 8.5, 'cn': 75.0})
        assert r.status_code == 200
    def test_runoff_has_cn(self, client):
        r = client.get('/api/runoff', params={'rainfall_in': 8.5, 'cn': 75.0})
        assert 'cn' in r.json()
    def test_runoff_has_runoff_depth(self, client):
        r = client.get('/api/runoff', params={'rainfall_in': 8.5, 'cn': 75.0})
        assert 'runoff_depth_in' in r.json()
    def test_runoff_has_runoff_fraction(self, client):
        r = client.get('/api/runoff', params={'rainfall_in': 8.5, 'cn': 75.0})
        assert 'runoff_fraction' in r.json()
    def test_runoff_missing_rainfall_422(self, client):
        r = client.get('/api/runoff', params={'cn': 75.0})
        assert r.status_code == 422


class TestInsightsEndpoint:
    def test_insights_200(self, client): assert client.get('/api/insights').status_code == 200
    def test_insights_returns_list(self, client): assert isinstance(client.get('/api/insights').json(), list)
    def test_insights_with_query(self, client):
        r = client.get('/api/insights', params={'q': 'runoff'})
        assert r.status_code == 200
    def test_insights_topic_404(self, client):
        r = client.get('/api/insights/nonexistent_topic_xyz')
        assert r.status_code == 404


class TestWizardsStatus:
    def test_wizards_status_200(self, client): assert client.get('/api/wizards/status').status_code == 200
    def test_wizards_status_has_timestamp(self, client): assert 'timestamp_utc' in client.get('/api/wizards/status').json()
    def test_wizards_status_has_wizards(self, client): assert 'wizards' in client.get('/api/wizards/status').json()
    def test_wizards_rainfall_available(self, client):
        wiz = client.get('/api/wizards/status').json()['wizards']
        assert 'rainfall_wizard' in wiz and wiz['rainfall_wizard']['available'] is True


class TestRunEndpoint:
    def test_run_422_on_missing_dem(self, client):
        payload = {'lat': 29.65, 'lon': -82.32, 'dem_path': '/nonexistent/dem.tif',
                   'duration_hr': 24.0, 'return_period_yr': 100, 'curve_number': 75.0}
        with patch('rainfall_wizard.processing.run_rainfall_analysis', side_effect=FileNotFoundError('/nonexistent/dem.tif')):
            r = client.post('/api/run', json=payload)
        assert r.status_code == 422
    def test_run_500_on_generic_error(self, client):
        payload = {'lat': 29.65, 'lon': -82.32, 'dem_path': 'fake.tif',
                   'duration_hr': 24.0, 'return_period_yr': 100, 'curve_number': 75.0}
        with patch('rainfall_wizard.processing.run_rainfall_analysis', side_effect=ValueError('bad data')):
            r = client.post('/api/run', json=payload)
        assert r.status_code == 500
    def test_run_missing_dem_path_422(self, client):
        r = client.post('/api/run', json={'lat': 29.65, 'lon': -82.32})
        assert r.status_code == 422
