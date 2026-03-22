@echo off
:: =============================================================================
:: (c) Clearview Geographic LLC -- All Rights Reserved | Est. 2018
:: CVG Rainfall Wizard — Development Server Launcher (Windows)
:: Author: Alex Zelenski, GISP | azelenski@clearviewgeographic.com
:: =============================================================================
title CVG Rainfall Wizard — Dev Server

echo.
echo  ================================================================
echo    CVG Rainfall Wizard — Starting Development Server
echo    Port: 8020  ^|  http://localhost:8020
echo    Swagger UI: http://localhost:8020/docs
echo  ================================================================
echo.

if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
    echo  [INFO] Virtual environment activated.
) else (
    echo  [WARN] No .venv found — using system Python.
)

pip show rainfall-wizard >nul 2>&1
if %errorlevel% neq 0 (
    echo  [INFO] Installing rainfall-wizard...
    pip install -e ".[web]" -q
)

echo  [INFO] Launching rainfall-wizard web server...
echo.

rainfall-wizard web --host 127.0.0.1 --port 8020

echo.
echo  [INFO] Server stopped.
pause
