# -*- coding: utf-8 -*-
# (c) Clearview Geographic LLC -- All Rights Reserved
from __future__ import annotations
import time, pytest
from rainfall_wizard.monitoring import ResourceSnapshot, take_snapshot, PerformanceTracker, timed_stage


class TestResourceSnapshot:
    def test_default_cpu_zero(self): assert ResourceSnapshot().cpu_pct == 0.0
    def test_default_ram_zero(self): assert ResourceSnapshot().ram_used_mb == 0.0
    def test_default_elapsed_zero(self): assert ResourceSnapshot().elapsed_sec == 0.0
    def test_timestamp_positive(self): assert 0 < ResourceSnapshot().timestamp
    def test_ram_pct_zero_division_safe(self):
        snap = ResourceSnapshot(ram_used_mb=512.0, ram_total_mb=0.0)
        assert snap.ram_used_pct == 0.0
    def test_ram_pct_calculated(self):
        snap = ResourceSnapshot(ram_used_mb=1024.0, ram_total_mb=4096.0)
        assert abs(snap.ram_used_pct - 25.0) < 0.01
    def test_ram_pct_100(self):
        snap = ResourceSnapshot(ram_used_mb=4096.0, ram_total_mb=4096.0)
        assert abs(snap.ram_used_pct - 100.0) < 0.001
    def test_to_dict_returns_dict(self): assert isinstance(ResourceSnapshot().to_dict(), dict)
    def test_to_dict_all_keys(self):
        d = ResourceSnapshot().to_dict()
        for k in ['timestamp','cpu_pct','ram_used_mb','ram_total_mb','ram_used_pct','disk_free_gb','elapsed_sec']: assert k in d
    def test_to_dict_cpu_rounded(self):
        assert ResourceSnapshot(cpu_pct=12.3456).to_dict()['cpu_pct'] == round(12.3456,1)
    def test_to_dict_elapsed_rounded(self):
        assert ResourceSnapshot(elapsed_sec=1.23456).to_dict()['elapsed_sec'] == round(1.23456,3)
    def test_to_dict_disk_rounded(self):
        assert ResourceSnapshot(disk_free_gb=12.34567).to_dict()['disk_free_gb'] == round(12.34567,2)
    def test_ram_total_mb_zero_by_default(self): assert ResourceSnapshot().ram_total_mb == 0.0
    def test_disk_zero_by_default(self): assert ResourceSnapshot().disk_free_gb == 0.0


class TestTakeSnapshot:
    def test_returns_resource_snapshot(self): assert isinstance(take_snapshot(), ResourceSnapshot)
    def test_elapsed_zero_without_start(self): assert take_snapshot().elapsed_sec == 0.0
    def test_elapsed_with_start_time(self):
        start = time.time() - 0.5
        snap = take_snapshot(start_time=start)
        assert 0.4 <= snap.elapsed_sec
    def test_timestamp_in_range(self):
        before = time.time(); snap = take_snapshot(); assert before <= snap.timestamp
    def test_ram_nonnegative(self): assert 0.0 <= take_snapshot().ram_used_mb


class TestPerformanceTracker:
    def test_basic_context_manager(self):
        with PerformanceTracker('t') as tr: time.sleep(0.02)
        assert 0.01 <= tr.elapsed_sec
    def test_label_stored(self): assert PerformanceTracker('my_stage').label == 'my_stage'
    def test_default_label(self): assert PerformanceTracker().label == 'operation'
    def test_start_snap_populated(self):
        with PerformanceTracker('s') as t: pass
        assert t.start_snap is not None
    def test_end_snap_populated(self):
        with PerformanceTracker('e') as t: pass
        assert t.end_snap is not None
    def test_to_dict_has_label(self):
        with PerformanceTracker('d') as t: pass
        assert t.to_dict()['label'] == 'd'
    def test_to_dict_has_elapsed_sec(self):
        with PerformanceTracker('x') as t: pass
        assert 'elapsed_sec' in t.to_dict()
    def test_to_dict_start_end_are_dicts(self):
        with PerformanceTracker('y') as t: pass
        d = t.to_dict()
        assert isinstance(d['start'], dict) and isinstance(d['end'], dict)
    def test_elapsed_before_exit_is_float(self):
        t = PerformanceTracker('pre'); t._start = time.time()
        assert isinstance(t.elapsed_sec, float)
    def test_exception_not_suppressed(self):
        with pytest.raises(ValueError):
            with PerformanceTracker('err'): raise ValueError('intentional')


class TestTimedStage:
    def test_yields_performance_tracker(self):
        with timed_stage('a') as t: assert isinstance(t, PerformanceTracker)
    def test_label_matches(self):
        with timed_stage('b') as t: assert t.label == 'b'
    def test_elapsed_after_context(self):
        with timed_stage('c') as t: time.sleep(0.02)
        assert 0.01 <= t.elapsed_sec
    def test_end_snap_set_after_exit(self):
        with timed_stage('d') as t: pass
        assert t.end_snap is not None
    def test_exception_propagates(self):
        with pytest.raises(RuntimeError):
            with timed_stage('fail'): raise RuntimeError('boom')
