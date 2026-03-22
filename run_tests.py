#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# (c) Clearview Geographic LLC -- All Rights Reserved | Est. 2018
# CVG Rainfall Wizard — run_tests.py
# =============================================================================
"""
Convenience script to run the Rainfall Wizard test suite from the project root.

Usage:
    python run_tests.py           # unit tests only (fast)
    python run_tests.py --all     # all tests including integration
    python run_tests.py --cov     # with coverage report
"""

import subprocess
import sys


def main():
    args = sys.argv[1:]
    run_all = "--all" in args
    run_cov = "--cov" in args

    # Use `python -m pytest` instead of `pytest`.
    #
    # Rationale: In some Windows environments (locked-down endpoints, AV rules,
    # corporate execution policies, etc.), the `pytest.exe` console-script
    # entrypoint under `<python>\Scripts\pytest.exe` may be blocked and
    # result in `PermissionError: [WinError 5] Access is denied`.
    # Running pytest as a module avoids that executable and is more reliable.
    cmd = [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"]

    if not run_all:
        cmd += ["-m", "not integration and not slow"]

    if run_cov:
        cmd += [
            "--cov=rainfall_wizard",
            "--cov-report=html",
            "--cov-report=term-missing",
        ]

    print(f"\n  CVG Rainfall Wizard — Running: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
