# -*- coding: utf-8 -*-
# (c) Clearview Geographic LLC -- All Rights Reserved
from __future__ import annotations
import json, pytest
from pathlib import Path
from rainfall_wizard.recovery import Stage, STAGE_ORDER, CheckpointManager, build_cache_key


class TestStageEnum:
    def test_init_value(self): assert Stage.INIT.value == 'init'
    def test_done_value(self): assert Stage.DONE.value == 'done'
    def test_runoff_value(self): assert Stage.RUNOFF.value == 'runoff'
    def test_report_value(self): assert Stage.REPORT.value == 'report'
    def test_fetch_pfds_value(self): assert Stage.FETCH_PFDS == 'fetch_pfds'
    def test_stage_order_length(self): assert len(STAGE_ORDER) == 9
    def test_stage_order_starts_init(self): assert STAGE_ORDER[0] == Stage.INIT
    def test_stage_order_ends_done(self): assert STAGE_ORDER[-1] == Stage.DONE
    def test_stage_is_str_enum(self): assert isinstance(Stage.RUNOFF, str)


class TestCheckpointManager:
    @pytest.fixture
    def cp_path(self, tmp_path): return tmp_path / 'chk.json'
    @pytest.fixture
    def cp(self, cp_path): return CheckpointManager(cp_path)
    def test_load_false_when_missing(self, cp): assert cp.load() is False
    def test_load_true_when_present(self, cp, cp_path):
        cp_path.write_text('{}', encoding='utf-8')
        assert cp.load() is True
    def test_set_and_get(self, cp):
        cp.set('foo', 42); assert cp.get('foo') == 42
    def test_get_default(self, cp): assert cp.get('missing', 'd') == 'd'
    def test_save_creates_file(self, cp, cp_path):
        cp.set('k', 1); assert cp_path.exists()
    def test_save_valid_json(self, cp, cp_path):
        cp.set('x', 99)
        data = json.loads(cp_path.read_text(encoding='utf-8'))
        assert data['x'] == 99
    def test_mark_stage_adds_to_list(self, cp):
        cp.mark_stage_complete(Stage.INIT)
        assert 'init' in cp.completed_stages
    def test_is_stage_complete_true(self, cp):
        cp.mark_stage_complete(Stage.LOAD_DEM)
        assert cp.is_stage_complete(Stage.LOAD_DEM) is True
    def test_is_stage_complete_false(self, cp): assert cp.is_stage_complete(Stage.RUNOFF) is False
    def test_no_duplicate_stage(self, cp):
        cp.mark_stage_complete(Stage.CLIP_AOI)
        cp.mark_stage_complete(Stage.CLIP_AOI)
        assert cp.completed_stages.count('clip_aoi') == 1
    def test_mark_stage_with_meta(self, cp):
        cp.mark_stage_complete(Stage.HYETOGRAPH, meta={'peak': 3.5})
        meta = cp.get('stage_hyetograph_meta')
        assert meta is not None and meta['peak'] == 3.5
    def test_clear_removes_file(self, cp, cp_path):
        cp.set('a', 1); cp.clear(); assert not cp_path.exists()
    def test_clear_resets_data(self, cp):
        cp.set('b', 2); cp.clear(); assert cp.get('b') is None
    def test_completed_stages_default_empty(self, cp): assert cp.completed_stages == []
    def test_load_corrupted_returns_false(self, cp_path):
        cp_path.write_text('NOT JSON', encoding='utf-8')
        assert CheckpointManager(cp_path).load() is False
    def test_stage_timestamp_stored(self, cp):
        cp.mark_stage_complete(Stage.INIT)
        ts = cp.get('stage_init_ts')
        assert ts is not None and 0 < ts


class TestBuildCacheKey:
    def test_returns_string(self): assert isinstance(build_cache_key({'lat': 29.65}), str)
    def test_length_16(self): assert len(build_cache_key({'lat': 29.65})) == 16
    def test_deterministic(self):
        cfg = {'lat': 29.65, 'lon': -82.32}
        assert build_cache_key(cfg) == build_cache_key(cfg)
    def test_different_configs_differ(self):
        assert build_cache_key({'lat': 29.65}) != build_cache_key({'lat': 30.00})
    def test_ordering_invariant(self):
        k1 = build_cache_key({'a': 1, 'b': 2})
        k2 = build_cache_key({'b': 2, 'a': 1})
        assert k1 == k2
    def test_empty_dict(self): assert len(build_cache_key({})) == 16
