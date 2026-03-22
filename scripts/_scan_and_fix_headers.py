# =============================================================================
# CVG Rainfall Wizard — Dev Utility: Recursive Header Scanner & Fixer
# Clearview Geographic LLC — Proprietary and Confidential
# ADF Build: 1.0.x | Python 3.10+
# =============================================================================
"""
Recursively scans all .py files in the CVG Rainfall Wizard project and applies
the CVG proprietary header to any file missing it. Also catalogues root-level
JSON / TXT artifacts that may be stale.

Usage:
    python scripts/_scan_and_fix_headers.py [--dry-run] [--report-artifacts]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_SKIP_DIRS = {
    "__pycache__", ".git", ".github", ".pytest_cache",
    "htmlcov", ".venv", "venv", "node_modules",
    "rainfall_wizard.egg-info",
}

_HEADER_MARKER = "Clearview Geographic LLC"

_HEADER_TEMPLATE = """\
# =============================================================================
# CVG Rainfall Wizard — {title}
# Clearview Geographic LLC — Proprietary and Confidential
# ADF Build: 1.0.x | Python 3.10+
# =============================================================================
"""

_ARTIFACT_EXTS = {".json", ".txt", ".csv", ".pdf", ".tif", ".log"}


def _collect_py_files() -> list[Path]:
    files: list[Path] = []
    for p in ROOT.rglob("*.py"):
        if any(part in _SKIP_DIRS for part in p.parts):
            continue
        files.append(p)
    return sorted(files)


def _needs_header(text: str) -> bool:
    return _HEADER_MARKER not in text


def _inject(path: Path, dry_run: bool) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        print(f"  ERROR reading {path.relative_to(ROOT)}: {exc}")
        return False
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
    parser = argparse.ArgumentParser(description="Scan & fix CVG headers in Rainfall Wizard")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-artifacts", action="store_true")
    args = parser.parse_args()

    py_files = _collect_py_files()
    added = 0
    already_ok = 0
    print(f"Scanning {len(py_files)} .py files under {ROOT.name}/\n")

    for p in py_files:
        rel = p.relative_to(ROOT)
        changed = _inject(p, dry_run=args.dry_run)
        if changed:
            tag = "DRY-RUN" if args.dry_run else "ADDED  "
            print(f"  {tag}  {rel}")
            added += 1
        else:
            already_ok += 1

    print(f"\n{'[DRY-RUN] ' if args.dry_run else ''}Total: {len(py_files)} files | "
          f"Headers added: {added} | Already OK: {already_ok}")

    if args.report_artifacts:
        artifacts = sorted(
            p for p in ROOT.iterdir()
            if p.is_file() and p.suffix.lower() in _ARTIFACT_EXTS
        )
        if artifacts:
            print(f"\nRoot-level artifacts ({len(artifacts)}):")
            for a in artifacts:
                print(f"  {a.name:40s}  {a.stat().st_size/1024:7.1f} KB")

    sys.exit(0)


if __name__ == "__main__":
    main()
