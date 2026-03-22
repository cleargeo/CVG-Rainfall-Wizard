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
"""_check_external.py — Quick connectivity check for all Rainfall Wizard external dependencies.

Run from the project root::

    python tools/_check_external.py

Exit code 0 = all checks passed; non-zero = at least one failure.
"""

from __future__ import annotations

import sys
import urllib.request
from typing import List, Tuple

PASS = "\u2705"
FAIL = "\u274c"
WARN = "\u26a0\ufe0f"


def _check(label: str, fn) -> bool:
    try:
        fn()
        print(f"  {PASS}  {label}")
        return True
    except Exception as exc:
        print(f"  {FAIL}  {label}  →  {exc}")
        return False


def check_noaa_pfds_api() -> None:
    """NOAA PFDS JSON API (Key West test point)."""
    url = "https://hdsc.nws.noaa.gov/pfds/pfds_json.php?lat=24.5551&lon=-81.7800&type=pf&data=depth&units=english&series=pds"
    with urllib.request.urlopen(url, timeout=15) as r:
        assert r.status == 200, f"HTTP {r.status}"


def check_noaa_pfds_v2() -> None:
    """NOAA PFDS pointdata v2 endpoint."""
    url = "https://hdsc.nws.noaa.gov/hdsc/pfds/pfds_pointdatav2.html?lat=24.5551&lon=-81.7800&data=depth&units=english&series=pds"
    with urllib.request.urlopen(url, timeout=15) as r:
        assert r.status == 200, f"HTTP {r.status}"


def check_noaa_atlas14_page() -> None:
    """NOAA Atlas 14 public landing page."""
    url = "https://hdsc.nws.noaa.gov/hdsc/pfds/"
    with urllib.request.urlopen(url, timeout=10) as r:
        assert r.status == 200, f"HTTP {r.status}"


def check_rainfall_wizard_import() -> None:
    """rainfall_wizard package imports cleanly."""
    import rainfall_wizard  # noqa: F401
    from rainfall_wizard import noaa, config, pfds, runoff, idf, insights  # noqa: F401


def check_rainfall_wizard_version() -> None:
    """rainfall_wizard has a version string."""
    import rainfall_wizard
    v = getattr(rainfall_wizard, "__version__", None)
    assert v, "No __version__ attribute found"
    print(f"       version: {v}", end="")


def check_scipy() -> None:
    """scipy scientific computing library is importable."""
    import scipy  # noqa: F401


def check_numpy() -> None:
    """numpy array computing library is importable."""
    import numpy  # noqa: F401


def check_reportlab() -> None:
    """reportlab PDF library is importable."""
    from reportlab.pdfgen import canvas  # noqa: F401


def check_rasterio() -> None:
    """rasterio geospatial raster library is importable."""
    import rasterio  # noqa: F401


def check_httpx() -> None:
    """httpx async HTTP client is importable."""
    import httpx  # noqa: F401


def check_fastapi() -> None:
    """FastAPI web framework is importable."""
    import fastapi  # noqa: F401


def main() -> int:
    print("\n========================================")
    print("  CVG Rainfall Wizard — External Checks")
    print("========================================\n")

    checks: List[Tuple[str, object]] = [
        ("NOAA PFDS JSON API", check_noaa_pfds_api),
        ("NOAA PFDS pointdata v2 endpoint", check_noaa_pfds_v2),
        ("NOAA Atlas 14 landing page", check_noaa_atlas14_page),
        ("rainfall_wizard package import", check_rainfall_wizard_import),
        ("rainfall_wizard version string", check_rainfall_wizard_version),
        ("scipy (statistics/optimization)", check_scipy),
        ("numpy (array computing)", check_numpy),
        ("reportlab (PDF generation)", check_reportlab),
        ("rasterio (raster I/O)", check_rasterio),
        ("httpx (async HTTP)", check_httpx),
        ("fastapi (web API)", check_fastapi),
    ]

    results = []
    for label, fn in checks:
        results.append(_check(label, fn))

    passed = sum(results)
    total = len(results)
    print(f"\n{'='*40}")
    print(f"  {passed}/{total} checks passed")
    print(f"{'='*40}\n")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
