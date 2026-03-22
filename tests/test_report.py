# -*- coding: utf-8 -*-
# (c) Clearview Geographic LLC -- All Rights Reserved
from __future__ import annotations
import json, types
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from rainfall_wizard.report import (
    build_json_report, write_json_report, write_pdf_report,
    REPORT_SCHEMA_VERSION, CVG_HEADER, NOAA_ATLAS14_REF, TR55_REF)
import rainfall_wizard.report as report_mod


def _mock_result(**kw):
    r = MagicMock()
    r.run_id = kw.get('run_id', 'test-001')
    r.return_period_yr = kw.get('return_period_yr', 100)
    r.duration_hr = kw.get('duration_hr', 24.0)
    r.to_dict.return_value = {'run_id': r.run_id, 'return_period_yr': 100}
    return r


def _mock_config(**kw):
    # Use SimpleNamespace so vars() returns a plain dict
    return types.SimpleNamespace(
        lat=kw.get('lat', 29.65),
        lon=kw.get('lon', -82.32),
        project_name=kw.get('project_name', 'test_proj'),
        curve_number=75.0, duration_hr=24.0, return_period_yr=100)


class TestReportConstants:
    def test_schema_version(self): assert REPORT_SCHEMA_VERSION == '1.0.0'
    def test_cvg_header_has_clearview(self): assert 'Clearview Geographic' in CVG_HEADER
    def test_noaa_ref_has_atlas14(self): assert 'Atlas 14' in NOAA_ATLAS14_REF
    def test_tr55_ref_has_tr55(self): assert 'TR-55' in TR55_REF
    def test_noaa_ref_is_str(self): assert isinstance(NOAA_ATLAS14_REF, str)
    def test_tr55_ref_is_str(self): assert isinstance(TR55_REF, str)


class TestBuildJsonReport:
    def test_returns_dict(self): assert isinstance(build_json_report(_mock_result(), _mock_config()), dict)
    def test_schema_version(self):
        r = build_json_report(_mock_result(), _mock_config())
        assert r['schema_version'] == REPORT_SCHEMA_VERSION
    def test_tool_name(self):
        r = build_json_report(_mock_result(), _mock_config())
        assert r['tool'] == 'CVG Rainfall Wizard'
    def test_tool_version_present(self):
        assert 'tool_version' in build_json_report(_mock_result(), _mock_config())
    def test_generated_utc_ends_z(self):
        r = build_json_report(_mock_result(), _mock_config())
        assert r['generated_utc'].endswith('Z')
    def test_copyright_present(self):
        r = build_json_report(_mock_result(), _mock_config())
        assert 'Clearview Geographic' in r['copyright']
    def test_references_is_list(self):
        refs = build_json_report(_mock_result(), _mock_config())['references']
        assert isinstance(refs, list) and len(refs) == 2
    def test_run_field_present(self):
        assert 'run' in build_json_report(_mock_result(), _mock_config())
    def test_config_field_present(self):
        assert 'config' in build_json_report(_mock_result(), _mock_config())
    def test_extra_merged(self):
        r = build_json_report(_mock_result(), _mock_config(), extra={'custom': 42})
        assert r['custom'] == 42
    def test_extra_none_no_error(self):
        build_json_report(_mock_result(), _mock_config(), extra=None)
    def test_config_with_to_dict(self):
        cfg = MagicMock(); cfg.to_dict.return_value = {'lat': 29.65, 'lon': -82.32}
        r = build_json_report(_mock_result(), cfg)
        assert r['config']['lat'] == 29.65


class TestWriteJsonReport:
    def test_creates_file(self, tmp_path):
        out = tmp_path / 'report.json'
        write_json_report(_mock_result(), _mock_config(), out)
        assert out.exists()
    def test_file_is_valid_json(self, tmp_path):
        out = tmp_path / 'report.json'
        write_json_report(_mock_result(), _mock_config(), out)
        data = json.loads(out.read_text(encoding='utf-8'))
        assert isinstance(data, dict)
    def test_creates_parent_dirs(self, tmp_path):
        out = tmp_path / 'sub' / 'nested' / 'report.json'
        write_json_report(_mock_result(), _mock_config(), out)
        assert out.exists()
    def test_schema_version_in_file(self, tmp_path):
        out = tmp_path / 'r.json'
        write_json_report(_mock_result(), _mock_config(), out)
        data = json.loads(out.read_text(encoding='utf-8'))
        assert data['schema_version'] == REPORT_SCHEMA_VERSION
    def test_tool_in_file(self, tmp_path):
        out = tmp_path / 't.json'
        write_json_report(_mock_result(), _mock_config(), out)
        data = json.loads(out.read_text(encoding='utf-8'))
        assert data['tool'] == 'CVG Rainfall Wizard'


class TestWritePdfReport:
    def test_returns_false_when_no_reportlab(self, tmp_path):
        out = tmp_path / 'rep.pdf'
        orig = report_mod._REPORTLAB_OK
        report_mod._REPORTLAB_OK = False
        try: result = write_pdf_report(_mock_result(), _mock_config(), out)
        finally: report_mod._REPORTLAB_OK = orig
        assert result is False
    def test_no_file_when_no_reportlab(self, tmp_path):
        out = tmp_path / 'rep.pdf'
        orig = report_mod._REPORTLAB_OK
        report_mod._REPORTLAB_OK = False
        try: write_pdf_report(_mock_result(), _mock_config(), out)
        finally: report_mod._REPORTLAB_OK = orig
        assert not out.exists()
