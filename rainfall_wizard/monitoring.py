# -*- coding: utf-8 -*-
# =============================================================================
# (c) Clearview Geographic LLC -- All Rights Reserved | Est. 2018
# Proprietary Software -- Internal Use Only
# Protected under US and International copyright, trade secret,
# trademark, cybersecurity, and intellectual property law.
# This Product is developed under CVG's Agentic Development Framework (ADF).
# Unauthorized use, replication, or modification is strictly prohibited.
# -----------------------------------------------------------------------------
# Author      : Alex Zelenski, GISP
# Organization: Clearview Geographic, LLC
# Contact     : azelenski@clearviewgeographic.com  |  386-957-2314
# License     : Proprietary -- CVG-ADF
# =============================================================================
"""
monitoring.py — System resource monitoring for the Rainfall Wizard.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, Generator, Optional

log = logging.getLogger(__name__)

try:
    import psutil
    _PSUTIL_OK = True
except ImportError:
    _PSUTIL_OK = False


@dataclass
class ResourceSnapshot:
    timestamp: float = field(default_factory=time.time)
    cpu_pct: float = 0.0
    ram_used_mb: float = 0.0
    ram_total_mb: float = 0.0
    disk_free_gb: float = 0.0
    elapsed_sec: float = 0.0

    @property
    def ram_used_pct(self) -> float:
        return self.ram_used_mb / self.ram_total_mb * 100.0 if self.ram_total_mb else 0.0

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "cpu_pct": round(self.cpu_pct, 1),
            "ram_used_mb": round(self.ram_used_mb, 1),
            "ram_total_mb": round(self.ram_total_mb, 1),
            "ram_used_pct": round(self.ram_used_pct, 1),
            "disk_free_gb": round(self.disk_free_gb, 2),
            "elapsed_sec": round(self.elapsed_sec, 3),
        }


def take_snapshot(start_time: Optional[float] = None) -> ResourceSnapshot:
    snap = ResourceSnapshot()
    if start_time is not None:
        snap.elapsed_sec = time.time() - start_time
    if _PSUTIL_OK:
        snap.cpu_pct = psutil.cpu_percent(interval=0.1)
        vm = psutil.virtual_memory()
        snap.ram_used_mb = vm.used / 1024 / 1024
        snap.ram_total_mb = vm.total / 1024 / 1024
        try:
            snap.disk_free_gb = psutil.disk_usage("/").free / 1024 / 1024 / 1024
        except Exception:
            pass
    return snap


class PerformanceTracker:
    def __init__(self, label: str = "operation") -> None:
        self.label = label
        self._start: float = 0.0
        self.start_snap: Optional[ResourceSnapshot] = None
        self.end_snap: Optional[ResourceSnapshot] = None

    def __enter__(self) -> "PerformanceTracker":
        self._start = time.time()
        self.start_snap = take_snapshot(self._start)
        return self

    def __exit__(self, *_) -> None:
        self.end_snap = take_snapshot(self._start)
        log.info(
            "[%s] %.2f s | RAM %.0f MB",
            self.label, self.elapsed_sec, self.end_snap.ram_used_mb,
        )

    @property
    def elapsed_sec(self) -> float:
        if self.end_snap:
            return self.end_snap.elapsed_sec
        return time.time() - self._start

    def to_dict(self) -> Dict:
        return {
            "label": self.label,
            "elapsed_sec": round(self.elapsed_sec, 3),
            "start": self.start_snap.to_dict() if self.start_snap else {},
            "end": self.end_snap.to_dict() if self.end_snap else {},
        }


@contextmanager
def timed_stage(label: str) -> Generator[PerformanceTracker, None, None]:
    tracker = PerformanceTracker(label)
    with tracker:
        yield tracker
