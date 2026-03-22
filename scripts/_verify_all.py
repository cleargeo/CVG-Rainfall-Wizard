# =============================================================================
# CVG Rainfall Wizard — Dev Utility: Full Verification Suite
# Clearview Geographic LLC — Proprietary and Confidential
# ADF Build: 1.0.x | Python 3.10+
# =============================================================================
"""
Comprehensive verification script for the CVG Rainfall Wizard.

Checks:
  1. CVG headers present on all tracked .py files
  2. NOAA Atlas 14 / TR-55 references in key module files
  3. Required config constants (VALID_DURATIONS, VALID_RETURN_PERIODS, VALID_STORM_TYPES)
  4. PFDS and IDF modules exist and are importable
  5. Changelog file exists and is non-empty
  6. README.md mentions key project terms
  7. .gitignore contains essential patterns
  8. pyproject.toml version field is present
  9. All required package modules are importable

Usage:
    python scripts/_verify_all.py [--strict]
"""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_HEADER_MARKER = "Clearview Geographic LLC"
_PASS = "\u2713"
_FAIL = "\u2717"

_REQUIRED_PY_FILES: list[str] = [
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
]

_REQUIRED_MODULES: list[str] = [
    "rainfall_wizard",
    "rainfall_wizard.config",
    "rainfall_wizard.core",
    "rainfall_wizard.noaa",
    "rainfall_wizard.pfds",
    "rainfall_wizard.idf",
    "rainfall_wizard.runoff",
    "rainfall_wizard.insights",
    "rainfall_wizard.processing",
    "rainfall_wizard.web_api",
]

_EXPECTED_STORM_TYPES = ["I", "IA", "II", "III"]


def check(label: str, ok: bool, detail: str = "") -> bool:
    mark = _PASS if ok else _FAIL
    msg = f"  [{mark}] {label}"
    if detail:
        msg += f"  — {detail}"
    print(msg)
    return ok


def run_checks(strict: bool) -> int:
    failures = 0

    print("\n=== 1. CVG Headers ===")
    for rel in _REQUIRED_PY_FILES:
        p = ROOT / rel
        if not p.exists():
            ok = check(rel, False, "FILE MISSING")
        else:
            text = p.read_text(encoding="utf-8", errors="replace")
            ok = check(rel, _HEADER_MARKER in text)
        if not ok:
            failures += 1

    print("\n=== 2. Atlas 14 / TR-55 References ===")
    key_refs = {
        "rainfall_wizard/config.py": ["Atlas 14", "curve_number", "storm_type"],
        "rainfall_wizard/noaa.py": ["Atlas 14", "PFDS", "lat"],
        "rainfall_wizard/runoff.py": ["curve number", "TR-55", "runoff"],
        "rainfall_wizard/idf.py": ["IDF", "duration", "return_period"],
    }
    for rel, terms in key_refs.items():
        p = ROOT / rel
        if not p.exists():
            check(f"{rel} — exists", False, "MISSING")
            failures += 1
            continue
        text = p.read_text(encoding="utf-8", errors="replace").lower()
        for term in terms:
            ok = check(f"{rel} contains '{term}'", term.lower() in text)
            if not ok:
                failures += 1

    print("\n=== 3. Config Constants ===")
    config_path = ROOT / "rainfall_wizard" / "config.py"
    if config_path.exists():
        cfg_text = config_path.read_text(encoding="utf-8", errors="replace")
        for st in _EXPECTED_STORM_TYPES:
            ok = check(f"config has storm type '{st}'", f'"{st}"' in cfg_text or f"'{st}'" in cfg_text)
            if not ok:
                failures += 1
        for const in ["VALID_DURATIONS", "VALID_RETURN_PERIODS", "VALID_STORM_TYPES"]:
            ok = check(f"config defines {const}", const in cfg_text)
            if not ok:
                failures += 1

    print("\n=== 4. PFDS & IDF Modules ===")
    for rel in ["rainfall_wizard/pfds.py", "rainfall_wizard/idf.py", "rainfall_wizard/runoff.py"]:
        p = ROOT / rel
        ok = check(f"{rel} exists", p.exists())
        if not ok:
            failures += 1

    print("\n=== 5. Changelog ===")
    changelog = ROOT / "05_ChangeLogs" / "master_changelog.md"
    ok = check("05_ChangeLogs/master_changelog.md exists", changelog.exists())
    if ok:
        ok = check("changelog is non-empty", changelog.stat().st_size > 0)
    if not ok:
        failures += 1

    print("\n=== 6. README ===")
    readme = ROOT / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8", errors="replace")
        for term in ["Rainfall Wizard", "Atlas 14", "NOAA"]:
            ok = check(f"README mentions '{term}'", term in text)
            if not ok:
                failures += 1
    else:
        check("README.md exists", False, "MISSING")
        failures += 1

    print("\n=== 7. .gitignore ===")
    gitignore = ROOT / ".gitignore"
    if gitignore.exists():
        gi_text = gitignore.read_text(encoding="utf-8", errors="replace")
        for pat in ["__pycache__", "*.pyc", ".env", "htmlcov/"]:
            ok = check(f".gitignore has '{pat}'", pat in gi_text)
            if not ok:
                failures += 1

    print("\n=== 8. pyproject.toml ===")
    pyproj = ROOT / "pyproject.toml"
    if pyproj.exists():
        text = pyproj.read_text(encoding="utf-8", errors="replace")
        ok = check("pyproject.toml has version field", "version" in text)
        if not ok:
            failures += 1
        ok = check("pyproject.toml references rainfall-wizard", "rainfall" in text.lower())
        if not ok:
            failures += 1

    print("\n=== 9. Module Imports ===")
    sys.path.insert(0, str(ROOT))
    for mod in _REQUIRED_MODULES:
        try:
            importlib.import_module(mod)
            ok = check(f"import {mod}", True)
        except Exception as exc:
            ok = check(f"import {mod}", False, str(exc)[:80])
        if not ok:
            failures += 1

    print(f"\n{'=' * 50}")
    label = "STRICT MODE" if strict else "STANDARD MODE"
    if failures == 0:
        print(f"  ALL CHECKS PASSED [{label}]  {_PASS}")
    else:
        print(f"  {failures} CHECK(S) FAILED [{label}]  {_FAIL}")
    print(f"{'=' * 50}\n")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Full verification for CVG Rainfall Wizard")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    failures = run_checks(strict=args.strict)
    sys.exit(1 if (args.strict and failures) else 0)


if __name__ == "__main__":
    main()
