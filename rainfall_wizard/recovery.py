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
recovery.py — Checkpoint / restart system for the Rainfall Wizard.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class Stage(str, Enum):
    INIT        = "init"
    LOAD_DEM    = "load_dem"
    CLIP_AOI    = "clip_aoi"
    FETCH_PFDS  = "fetch_pfds"
    HYETOGRAPH  = "hyetograph"
    RUNOFF      = "runoff"
    DEPTH_GRID  = "depth_grid"
    REPORT      = "report"
    DONE        = "done"

STAGE_ORDER = [
    Stage.INIT, Stage.LOAD_DEM, Stage.CLIP_AOI,
    Stage.FETCH_PFDS, Stage.HYETOGRAPH, Stage.RUNOFF,
    Stage.DEPTH_GRID, Stage.REPORT, Stage.DONE,
]


class CheckpointManager:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._data: Dict[str, Any] = {}

    def load(self) -> bool:
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as fh:
                    self._data = json.load(fh)
                return True
            except Exception as exc:
                log.warning("Could not load checkpoint: %s", exc)
        return False

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
        self._data = {}

    @property
    def completed_stages(self) -> List[str]:
        return self._data.get("completed_stages", [])

    def mark_stage_complete(self, stage: Stage, meta: Optional[Dict] = None) -> None:
        done = self.completed_stages
        if stage.value not in done:
            done.append(stage.value)
        self._data["completed_stages"] = done
        self._data[f"stage_{stage.value}_ts"] = time.time()
        if meta:
            self._data[f"stage_{stage.value}_meta"] = meta
        self.save()

    def is_stage_complete(self, stage: Stage) -> bool:
        return stage.value in self.completed_stages


class RecoveryManager:
    def __init__(self, run_id: str, output_dir: str | Path) -> None:
        self.run_id = run_id
        from .paths import get_checkpoint_path
        self.checkpoint = CheckpointManager(get_checkpoint_path(run_id, output_dir))
        self._resumed = False

    def try_resume(self) -> bool:
        found = self.checkpoint.load()
        if found and self.checkpoint.completed_stages:
            self._resumed = True
        return self._resumed

    def should_skip(self, stage: Stage) -> bool:
        return self._resumed and self.checkpoint.is_stage_complete(stage)

    def complete(self, stage: Stage, meta: Optional[Dict] = None) -> None:
        self.checkpoint.mark_stage_complete(stage, meta)

    def finish(self) -> None:
        self.checkpoint.mark_stage_complete(Stage.DONE)
        self.checkpoint.clear()


def build_cache_key(config_dict: Dict) -> str:
    blob = json.dumps(config_dict, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:16]
