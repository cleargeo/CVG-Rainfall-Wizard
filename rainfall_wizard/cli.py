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
cli.py — Command-line interface for the CVG Rainfall Wizard.

Usage:
  rainfall-wizard run    LAT LON --dem DEM.tif --rp 100 --dur 24 --cn 75
  rainfall-wizard batch  LAT LON --dem DEM.tif --dur 24 --cn 75
  rainfall-wizard pfds   LAT LON [--dur 24] [--rp 100]
  rainfall-wizard web    [--host 0.0.0.0] [--port 8020]
  rainfall-wizard insights [QUERY]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional
import logging

log = logging.getLogger(__name__)


def main(argv: Optional[List[str]] = None) -> int:
    # Ensure Unicode characters print correctly on Windows cp1252 terminals.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_logging(getattr(args, "verbose", False))
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return args.func(args)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def _cmd_run(args) -> int:
    from .config import RainfallConfig
    from .processing import run_rainfall_analysis
    from .report import write_reports
    from pathlib import Path as _P

    cfg = RainfallConfig(
        lat=args.lat,
        lon=args.lon,
        duration_hr=args.dur,
        return_period_yr=args.rp,
        curve_number=args.cn,
        dem_path=args.dem,
        dem_unit=args.dem_unit,
        output_path=args.output or "",
        project_name=args.project or "rainfall_run",
    )
    result = run_rainfall_analysis(cfg, resume=args.resume)

    out_dir = _P(args.output).parent if args.output else _P("output")
    out_paths = write_reports(result, cfg, out_dir)
    _print_summary(result, out_paths)
    return 0


def _cmd_batch(args) -> int:
    from .config import RainfallConfig
    from .processing import run_batch

    cfg = RainfallConfig(
        lat=args.lat, lon=args.lon,
        duration_hr=args.dur, curve_number=args.cn,
        dem_path=args.dem, dem_unit=args.dem_unit,
    )
    results = run_batch(cfg)
    print(f"\n✓ Batch complete — {len(results)} run(s)")
    for r in results:
        print(f"  {r.return_period_yr:5d}-yr  rainfall={r.rainfall_depth_in:.2f}in  "
              f"runoff={r.runoff_depth_in:.2f}in  max={r.max_depth_ft:.2f}ft")
    return 0


def _cmd_pfds(args) -> int:
    from .noaa import fetch_pfds, STANDARD_RETURN_PERIODS_YR
    print(f"\nFetching NOAA Atlas 14 PFDS for ({args.lat:.4f}, {args.lon:.4f}) …")
    try:
        resp = fetch_pfds(args.lat, args.lon)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    dur = args.dur or 24.0
    print(f"\n  Duration: {dur} hr  |  State: {resp.state}  County: {resp.county}")
    print(f"{'Return Period':>15s}  {'Depth (in)':>12s}  {'Intensity (in/hr)':>18s}")
    print("─" * 50)
    for rp in STANDARD_RETURN_PERIODS_YR:
        pfe = resp.get(dur, rp)
        if pfe:
            print(f"  {rp:13d}-yr  {pfe.depth_in:12.3f}  {pfe.intensity_in_hr:18.4f}")
    return 0


def _cmd_web(args) -> int:
    try:
        import uvicorn
        from .web_api import create_app
        app = create_app()
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    except ImportError:
        print("[ERROR] uvicorn required: pip install uvicorn", file=sys.stderr)
        return 1
    return 0


def _cmd_insights(args) -> int:
    from .insights import search_insights, list_topics
    query = " ".join(args.query) if args.query else ""
    if not query:
        print("Knowledge base topics:")
        for t in list_topics():
            print(f"  • {t}")
        return 0
    for entry in search_insights(query):
        print(f"\n{'='*60}\n  [{entry.topic}] {entry.title}")
        print(f"  Source: {entry.source}\n{'─'*60}")
        print(entry.body)
    return 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rainfall-wizard",
        description="CVG Rainfall Wizard — NOAA Atlas 14 Rainfall Depth Grid Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="© Clearview Geographic LLC | azelenski@clearviewgeographic.com",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(title="commands")

    def _add_site_args(p):
        p.add_argument("lat", type=float, help="Site latitude (decimal degrees)")
        p.add_argument("lon", type=float, help="Site longitude (decimal degrees)")
        p.add_argument("--dem", required=True, help="DEM GeoTIFF path")
        p.add_argument("--dem-unit", default="m", choices=["m", "ft"])
        p.add_argument("--dur", type=float, default=24.0, help="Duration (hr)")
        p.add_argument("--cn", type=float, default=75.0, help="Curve Number")

    # run
    p_run = sub.add_parser("run", help="Single return period run")
    _add_site_args(p_run)
    p_run.add_argument("--rp", type=int, default=100, help="Return period (yr)")
    p_run.add_argument("--output", default=None, help="Output GeoTIFF path")
    p_run.add_argument("--project", default="rainfall_run")
    p_run.add_argument("--resume", action="store_true", default=True)
    p_run.set_defaults(func=_cmd_run)

    # batch
    p_batch = sub.add_parser("batch", help="Run all standard return periods")
    _add_site_args(p_batch)
    p_batch.set_defaults(func=_cmd_batch)

    # pfds
    p_pfds = sub.add_parser("pfds", help="Fetch NOAA Atlas 14 PFDS data")
    p_pfds.add_argument("lat", type=float)
    p_pfds.add_argument("lon", type=float)
    p_pfds.add_argument("--dur", type=float, default=None)
    p_pfds.add_argument("--rp", type=int, default=None)
    p_pfds.set_defaults(func=_cmd_pfds)

    # web
    p_web = sub.add_parser("web", help="Start web UI")
    p_web.add_argument("--host", default="127.0.0.1")
    p_web.add_argument("--port", type=int, default=8020)
    p_web.set_defaults(func=_cmd_web)

    # insights
    p_ins = sub.add_parser("insights", help="Search knowledge base")
    p_ins.add_argument("query", nargs="*")
    p_ins.set_defaults(func=_cmd_insights)

    return parser


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _print_summary(result, out_paths: dict) -> None:
    print(f"\n{'═'*55}")
    print(f"  CVG Rainfall Wizard — Run Complete")
    print(f"{'═'*55}")
    print(f"  Run ID       : {result.run_id}")
    print(f"  Return Period: {result.return_period_yr}-yr")
    print(f"  Duration     : {result.duration_hr:.1f} hr")
    print(f"  Rainfall     : {result.rainfall_depth_in:.3f} in")
    print(f"  CN Runoff    : {result.runoff_depth_in:.3f} in  ({result.runoff_fraction*100:.0f}%)")
    print(f"  Max depth    : {result.max_depth_ft:.2f} ft")
    print(f"  Elapsed      : {result.elapsed_sec:.1f} s")
    for fmt, path in out_paths.items():
        print(f"  [{fmt.upper()}] {path}")
    print(f"{'═'*55}\n")


if __name__ == "__main__":
    sys.exit(main())
