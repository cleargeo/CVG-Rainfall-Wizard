@echo off
:: =============================================================================
:: (c) Clearview Geographic LLC -- All Rights Reserved | Est. 2018
:: CVG Rainfall Wizard — Run Tests (Windows)
:: =============================================================================
title CVG Rainfall Wizard — Tests

echo.
echo  Running CVG Rainfall Wizard Test Suite...
echo.

if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

:: NOTE: Use explicit test file paths to prevent pytest from resolving
:: rootdir to the sibling CVG_Storm Surge Wizard directory and running
:: SSW's test suite instead of the Rainfall Wizard's own tests.
pytest ^
    tests\test_rainfall_wizard.py ^
    tests\test_config.py ^
    tests\test_runoff.py ^
    tests\test_idf.py ^
    -v --tb=short ^
    -m "not integration and not slow" ^
    --override-ini="addopts=" ^
    --override-ini="testpaths="

echo.
echo  Done.
pause
