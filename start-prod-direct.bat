@echo off
:: =============================================================================
:: CVG Rainfall Wizard — Production Direct Start (no Docker)
:: Use this when Docker Desktop is not available.
:: Pairs with cloudflared tunnel for public HTTPS access.
::
:: App runs at: http://localhost:8020
:: Public URL:  https://rainfall.cleargeo.tech  (via cloudflare tunnel)
:: =============================================================================
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo [CVG RFW] Starting Rainfall Wizard API (production, direct)...
echo [CVG RFW] API:    http://localhost:8020
echo [CVG RFW] Docs:   http://localhost:8020/docs
echo [CVG RFW] Health: http://localhost:8020/health
echo.

:: Optional: restrict allowed data paths
set RFW_ALLOWED_DATA_ROOTS=G:\2019;Z:\2019

python -m uvicorn rainfall_wizard.web_api:app ^
    --host 0.0.0.0 ^
    --port 8020 ^
    --workers 2 ^
    --log-level info ^
    --access-log
