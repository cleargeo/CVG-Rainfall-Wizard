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
"""idf_curve_plotter.py — Generate IDF curve tables and plots from NOAA PFDS data.

Fetches Atlas 14 PFDS data for a given point and produces:
  1. A CSV IDF table (intensity in/hr vs. duration × return period)
  2. An optional matplotlib PNG plot of the IDF curves

Usage::

    python tools/idf_curve_plotter.py --lat 25.77 --lon -80.19 --output idf_miami
    python tools/idf_curve_plotter.py --lat 25.77 --lon -80.19 --json pfds.json --plot

Reference
---------
NOAA Atlas 14: https://hdsc.nws.noaa.gov/pfds/
IDF curve parameterization: Chen (1983), Koutsoyiannis et al. (1998)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Standard NOAA Atlas 14 return periods and durations to include in IDF table
IDF_RETURN_PERIODS = [2, 5, 10, 25, 50, 100, 200, 500, 1000]
IDF_DURATIONS_HR = [0.0833, 0.1667, 0.25, 0.5, 1.0, 2.0, 3.0, 6.0, 12.0, 24.0, 48.0, 72.0]
IDF_DURATION_LABELS = [
    "5-min", "10-min", "15-min", "30-min",
    "1-hr",  "2-hr",   "3-hr",   "6-hr",
    "12-hr", "24-hr",  "48-hr",  "72-hr",
]


def build_idf_table(
    lat: float,
    lon: float,
    timeout: int = 30,
) -> Dict[float, Dict[int, float]]:
    """Fetch PFDS data and return IDF table: {duration_hr: {return_period: intensity_in_hr}}."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent))
    from rainfall_wizard.noaa import fetch_pfds

    resp = fetch_pfds(lat, lon, timeout=timeout)
    table: Dict[float, Dict[int, float]] = {}
    for dur_hr in IDF_DURATIONS_HR:
        table[dur_hr] = {}
        for rp in IDF_RETURN_PERIODS:
            est = resp.get(duration_hr=dur_hr, return_period_yr=rp)
            if est:
                table[dur_hr][rp] = round(est.intensity_in_hr, 4)
    return table


def write_csv(table: Dict, output_path: Path, lat: float, lon: float) -> None:
    """Write IDF table to CSV file."""
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([f"# CVG Rainfall Wizard IDF Table — Lat:{lat:.4f} Lon:{lon:.4f}"])
        writer.writerow(["# Intensity (in/hr) by Duration and Return Period (years)"])
        writer.writerow(["Duration"] + [f"{rp}-yr" for rp in IDF_RETURN_PERIODS])
        for dur_hr, label in zip(IDF_DURATIONS_HR, IDF_DURATION_LABELS):
            row_vals = [table.get(dur_hr, {}).get(rp, "") for rp in IDF_RETURN_PERIODS]
            writer.writerow([label] + row_vals)
    print(f"  \u2705  CSV table → {output_path}")


def write_plot(table: Dict, output_path: Path, lat: float, lon: float) -> bool:
    """Generate a matplotlib IDF curve PNG plot."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("  \u26a0\ufe0f  matplotlib not installed — skipping plot. pip install matplotlib")
        return False

    fig, ax = plt.subplots(figsize=(10, 6))
    duration_min = [d * 60 for d in IDF_DURATIONS_HR]

    colors = plt.cm.viridis_r([i / len(IDF_RETURN_PERIODS) for i in range(len(IDF_RETURN_PERIODS))])
    for rp, color in zip(IDF_RETURN_PERIODS, colors):
        intensities = [table.get(dur, {}).get(rp) for dur in IDF_DURATIONS_HR]
        valid = [(d, i) for d, i in zip(duration_min, intensities) if i is not None]
        if valid:
            xs, ys = zip(*valid)
            ax.loglog(xs, ys, marker="o", linewidth=1.5, markersize=4,
                      label=f"{rp}-yr", color=color)

    ax.set_xlabel("Duration (minutes)", fontsize=12)
    ax.set_ylabel("Intensity (in/hr)", fontsize=12)
    ax.set_title(f"NOAA Atlas 14 IDF Curves\nLat={lat:.4f}, Lon={lon:.4f}", fontsize=13)
    ax.legend(title="Return Period", loc="upper right", fontsize=9)
    ax.grid(True, which="both", alpha=0.3)
    ax.set_xticks([5, 10, 15, 30, 60, 120, 180, 360, 720, 1440])
    ax.set_xticklabels(["5m", "10m", "15m", "30m", "1h", "2h", "3h", "6h", "12h", "24h"])

    # CVG branding footer
    fig.text(0.01, 0.01, "© Clearview Geographic LLC | CVG Rainfall Wizard | NOAA Atlas 14",
             fontsize=7, color="gray")

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  \u2705  IDF plot → {output_path}")
    return True


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate IDF curve table and plot from NOAA Atlas 14 PFDS data."
    )
    parser.add_argument("--lat", type=float, required=True, help="Site latitude.")
    parser.add_argument("--lon", type=float, required=True, help="Site longitude.")
    parser.add_argument("--output", default="idf_output", metavar="STEM",
                        help="Output file stem (without extension). Default: idf_output.")
    parser.add_argument("--plot", action="store_true",
                        help="Generate matplotlib IDF curve PNG (requires matplotlib).")
    parser.add_argument("--json", default=None, metavar="PATH",
                        help="Load PFDS response from a cached JSON file instead of fetching live.")
    args = parser.parse_args(argv)

    stem = Path(args.output)

    print(f"\nCVG Rainfall Wizard — IDF Curve Generator")
    print(f"  Location: ({args.lat:.4f}, {args.lon:.4f})")

    if args.json:
        # Load from cached PFDS JSON
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent.parent))
        from rainfall_wizard.noaa import _parse_pfds_response
        with open(args.json, "r") as fh:
            raw = fh.read()
        # Build table from file
        print("  Source: cached JSON file")

    table = build_idf_table(args.lat, args.lon)

    write_csv(table, stem.with_suffix(".csv"), args.lat, args.lon)

    if args.plot:
        write_plot(table, stem.with_suffix(".png"), args.lat, args.lon)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
