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
paths.py — Canonical path resolution for the Rainfall Wizard.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Package root
# ---------------------------------------------------------------------------
PACKAGE_DIR: Path = Path(__file__).resolve().parent
PROJECT_ROOT: Path = PACKAGE_DIR.parent

# ---------------------------------------------------------------------------
# Static assets bundled with the package
# ---------------------------------------------------------------------------
TEMPLATES_DIR: Path = PACKAGE_DIR / "templates"
DEMO_DATA_DIR: Path = PACKAGE_DIR / "demo_data"
CACHE_DIR: Path = PACKAGE_DIR / "cache"


def get_output_dir(base: str | Path | None = None) -> Path:
    """Return the output directory, creating it if necessary."""
    if base:
        p = Path(base)
    else:
        p = Path(os.environ.get("RAINFALL_OUTPUT_DIR", "output"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_cache_dir() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def get_checkpoint_path(run_id: str, output_dir: str | Path | None = None) -> Path:
    return get_output_dir(output_dir) / f"checkpoint_{run_id}.json"


def get_report_path(
    prefix: str,
    return_period: int,
    duration_hr: float,
    output_dir: str | Path | None = None,
    ext: str = "json",
) -> Path:
    stem = f"{prefix}_{return_period}yr_{duration_hr}hr"
    return get_output_dir(output_dir) / f"{stem}.{ext}"


def get_raster_path(
    prefix: str,
    return_period: int,
    duration_hr: float,
    layer: str = "depth",
    output_dir: str | Path | None = None,
) -> Path:
    stem = f"{prefix}_{return_period}yr_{duration_hr}hr_{layer}"
    return get_output_dir(output_dir) / f"{stem}.tif"
