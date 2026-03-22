@echo off
:: =============================================================================
:: (c) Clearview Geographic LLC -- All Rights Reserved | Est. 2018
:: CVG Rainfall Wizard — Run Tests with Coverage (Windows)
:: =============================================================================
title CVG Rainfall Wizard — Coverage

echo.
echo  Running CVG Rainfall Wizard Tests with Coverage...
echo.

if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

pytest tests\ --cov=rainfall_wizard --cov-report=html --cov-report=term-missing -v

echo.
echo  Coverage report saved to: htmlcov\index.html
echo.
pause
