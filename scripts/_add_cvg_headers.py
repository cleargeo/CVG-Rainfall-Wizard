# =============================================================================
# CVG Rainfall Wizard — Dev Utility: Add CVG Headers to Source Files
# Clearview Geographic LLC — Proprietary and Confidential
# ADF Build: 1.0.x | Python 3.10+
# =============================================================================
"""
Targeted header injector for the CVG Rainfall Wizard Python source files.

Adds the standard CVG ADF proprietary header block to each file that
is missing it. Preserves existing shebangs (#!/usr/bin/env python3).

Usage:
    python scripts/_add_cvg_headers.py [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_MANIFEST: list[str] = [
    "rainfall_wizard/__init__.py",
    "rainfall_wizard/cli.py",
    "rainfall_wizard/config.py",
    "rainfall_wizard/core.py",
    "rainfall_wizard/idf.py",
    "rainfall_wizard/insights.py",
    "rainfall_wizard/io.py",
    "rainfall_wizard/monitoring.py",
    "rainfall_wizard/noaa.py",
    "rainfall_wizard/paths.py",
    "rainfall_wizard/pfds.py",
    "rainfall_wizard/processing.py",
    "rainfall_wizard/recovery.py",
    "rainfall_wizard/report.py",
    "rainfall_wizard/runoff.py",
    "rainfall_wizard/web_api.py",
    "rainfall_wizard/web.py",
    "tests/conftest.py",
    "tests/test_config.py",
    "tests/test_idf.py",
    "tests/test_noaa.py",
    "tests/test_insights.py",
    "tests/test_rainfall_wizard.py",
    "tests/test_runoff.py",
    "scripts/run_rainfall.py",
    "portal/app.py",
]

_HEADER_MARKER = "Clearview Geographic LLC"

_HEADER_TEMPLATE = """\
# =============================================================================
# CVG Rainfall Wizard — {title}
# Clearview Geographic LLC — Proprietary and Confidential
# ADF Build: 1.0.x | Python 3.10+
# =============================================================================
"""


def _needs_header(text: str) -> bool:
    return _HEADER_MARKER not in text


def _inject(path: Path, dry_run: bool) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not _needs_header(text):
        return False
    title = path.stem.replace("_", " ").title()
    header = _HEADER_TEMPLATE.format(title=title)
    lines = text.splitlines(keepends=True)
    if lines and lines[0].startswith("#!"):
        new_text = lines[0] + header + "".join(lines[1:])
    else:
        new_text = header + text
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Add CVG headers to Rainfall Wizard source files")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    modified = 0
    missing  = 0
    for rel in _MANIFEST:
        p = ROOT / rel
        if not p.exists():
            print(f"  MISSING  {rel}")
            missing += 1
            continue
        changed = _inject(p, dry_run=args.dry_run)
        tag = "DRY-RUN" if args.dry_run and changed else ("ADDED  " if changed else "OK     ")
        print(f"  {tag}  {rel}")
        if changed:
            modified += 1

    print(f"\n{'[DRY-RUN] ' if args.dry_run else ''}Headers added: {modified}  |  Missing files: {missing}")
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
