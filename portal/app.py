# =============================================================================
# CVG Rainfall Wizard — Portal Dashboard Application
# Clearview Geographic LLC — Proprietary and Confidential
# ADF Build: 1.0.x | FastAPI + Jinja2 | Python 3.10+
# =============================================================================
"""
Lightweight dashboard portal for the CVG Rainfall Wizard.

Provides a browser-based UI that proxies and aggregates data from the
Rainfall Wizard REST API (running on port 8020 by default). Shows:
  - API health / version status
  - Recent PFDS fetch and run history (in-memory, last 50)
  - Live precipitation frequency lookup form
  - Quick CN runoff calculator
  - Engineering insights KB browser

Environment variables
---------------------
RFW_API_URL  Base URL of the Rainfall Wizard API (default: http://localhost:8020)
PORT         Listening port for this portal (default: 8040)
"""

from __future__ import annotations

import os
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
RFW_API_URL: str = os.environ.get("RFW_API_URL", "http://localhost:8020").rstrip("/")
PORTAL_VERSION: str = "1.0.0"
MAX_HISTORY: int = 50

# ---------------------------------------------------------------------------
# In-memory run history
# ---------------------------------------------------------------------------
_history: Deque[Dict[str, Any]] = deque(maxlen=MAX_HISTORY)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="CVG Rainfall Wizard Portal",
    description="Dashboard for the CVG Rainfall Wizard API",
    version=PORTAL_VERSION,
    docs_url="/api-docs",
)

_TMPL_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_TMPL_DIR)


# ---------------------------------------------------------------------------
# HTTP client factory
# ---------------------------------------------------------------------------
def _rfw_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=RFW_API_URL, timeout=20.0)


# ---------------------------------------------------------------------------
# Helper: safe API call
# ---------------------------------------------------------------------------
async def _api_get(path: str) -> tuple[Optional[Dict], Optional[str]]:
    try:
        async with _rfw_client() as client:
            r = await client.get(path)
            r.raise_for_status()
            return r.json(), None
    except httpx.ConnectError:
        return None, f"Cannot connect to Rainfall Wizard API at {RFW_API_URL}"
    except Exception as exc:
        return None, str(exc)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main portal dashboard."""
    health, health_err = await _api_get("/health")

    ctx = {
        "request": request,
        "api_url": RFW_API_URL,
        "portal_version": PORTAL_VERSION,
        "api_health": health,
        "api_error": health_err,
        "history": list(_history),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    return templates.TemplateResponse("dashboard.html", ctx)


@app.get("/api/proxy/health")
async def proxy_health():
    data, err = await _api_get("/health")
    if err:
        return JSONResponse({"error": err}, status_code=503)
    return data


@app.get("/api/proxy/pfds")
async def proxy_pfds(
    lat: float = 25.7617,
    lon: float = -80.1918,
    duration: str = "24h",
    return_period: int = 100,
):
    """Proxy a PFDS request and record it in history."""
    path = f"/api/pfds?lat={lat}&lon={lon}&duration={duration}&return_period={return_period}"
    data, err = await _api_get(path)
    if err:
        return JSONResponse({"error": err}, status_code=503)

    _history.appendleft({
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "type": "pfds",
        "lat": lat,
        "lon": lon,
        "duration": duration,
        "return_period": return_period,
        "depth_in": (data or {}).get("depth_in"),
        "ok": data is not None,
    })
    return data


@app.get("/api/proxy/runoff")
async def proxy_runoff(
    cn: int = 75,
    rainfall_in: float = 8.0,
    area_acres: float = 100.0,
    slope_pct: float = 1.0,
    storm_type: str = "II",
):
    """Proxy a CN runoff calculation and record it in history."""
    path = (f"/api/runoff?cn={cn}&rainfall_in={rainfall_in}"
            f"&area_acres={area_acres}&slope_pct={slope_pct}&storm_type={storm_type}")
    data, err = await _api_get(path)
    if err:
        return JSONResponse({"error": err}, status_code=503)

    _history.appendleft({
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "type": "runoff",
        "cn": cn,
        "rainfall_in": rainfall_in,
        "storm_type": storm_type,
        "Q_in": (data or {}).get("Q_in"),
        "ok": data is not None,
    })
    return data


@app.get("/api/proxy/insights")
async def proxy_insights(query: str = ""):
    path = f"/api/insights?query={query}" if query else "/api/insights"
    data, err = await _api_get(path)
    if err:
        return JSONResponse({"error": err}, status_code=503)
    return data


@app.get("/api/history")
async def get_history():
    return {"count": len(_history), "runs": list(_history)}


@app.delete("/api/history")
async def clear_history():
    _history.clear()
    return {"cleared": True}


@app.get("/health")
async def health():
    return {
        "service": "cvg-rainfall-wizard-portal",
        "version": PORTAL_VERSION,
        "status": "ok",
        "api_target": RFW_API_URL,
        "ts": time.time(),
    }
