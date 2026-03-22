# -*- coding: utf-8 -*-
# =============================================================================
# (c) Clearview Geographic LLC -- All Rights Reserved | Est. 2018
# Proprietary Software -- Internal Use Only
# Protected under US and International copyright, trade secret,
# trademark, cybersecurity, and intellectual property law.
# This Product is developed under CVG Agentic Development Framework (ADF).
# Unauthorized use, replication, or modification is strictly prohibited.
# -----------------------------------------------------------------------------
# Author      : Alex Zelenski, GISP
# Organization: Clearview Geographic, LLC
# Contact     : azelenski@clearviewgeographic.com  |  386-957-2314
# License     : Proprietary -- CVG-ADF
# =============================================================================
"""
web.py -- Jinja2 + FastAPI template-rendering routes for the CVG Rainfall Wizard.

This module preserves the original Jinja2 helper functions (render_template,
render_index, render_result) AND adds FastAPI route handlers for the public
web UI (GET / and POST /runoff).

Routes (FastAPI via create_web_app()):
  GET  /          -> index.html  (NOAA PFDS + CN Runoff form)
  POST /runoff    -> result.html (computed results)

Jinja2 helpers (original API preserved):
  render_template(template_name, context) -> str
  render_index(context=None) -> str
  render_result(result_dict, context=None) -> str
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Jinja2 template helpers (original web.py functionality preserved)
# ---------------------------------------------------------------------------
try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    _JINJA2_OK = True
except ImportError:
    _JINJA2_OK = False

from .paths import TEMPLATES_DIR
from . import __version__


def _get_env() -> Optional["Environment"]:
    """Return a Jinja2 Environment backed by the templates directory."""
    if not _JINJA2_OK or not TEMPLATES_DIR.exists():
        return None
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )

def render_template(template_name: str, context: Dict[str, Any]) -> str:
    """Render a Jinja2 template and return the HTML string."""
    env = _get_env()
    if env is None:
        return "<p>Template rendering unavailable.</p>"
    ctx = {
        "tool_version": __version__,
        "tool_name": "CVG Rainfall Wizard",
        "copyright": "\u00a9 Clearview Geographic LLC",
        "version": __version__,
        **context,
    }
    try:
        return env.get_template(template_name).render(**ctx)
    except Exception as exc:
        log.error("Template render failed (%s): %s", template_name, exc)
        return f"<p>Template error: {exc}</p>"


def render_index(context: Optional[Dict] = None) -> str:
    """Render index.html (main wizard form)."""
    return render_template("index.html", context or {})


def render_result(result_dict: Dict, context: Optional[Dict] = None) -> str:
    """Render result.html (analysis output page)."""
    return render_template("result.html", {"result": result_dict, **(context or {})})


# ---------------------------------------------------------------------------
# FastAPI web application
# ---------------------------------------------------------------------------
try:
    from fastapi import FastAPI, Request, Form
    from fastapi.responses import HTMLResponse, RedirectResponse
    from fastapi.templating import Jinja2Templates
    _FASTAPI_OK = True
except ImportError:
    _FASTAPI_OK = False

_TEMPLATES: Optional[Any] = None


def _get_templates() -> Optional[Any]:
    """Return FastAPI Jinja2Templates instance (lazy init)."""
    global _TEMPLATES
    if not _FASTAPI_OK:
        return None
    if _TEMPLATES is None:
        _TEMPLATES = Jinja2Templates(directory=str(TEMPLATES_DIR))
    return _TEMPLATES


def create_web_app() -> Any:
    """Create and return a FastAPI app with the Rainfall Wizard web UI routes.

    Merges the public web UI routes (GET / and POST /runoff) into a FastAPI app.
    The returned app can be mounted into the main web_api app or run standalone.

    Returns:
        FastAPI application instance, or raises ImportError if FastAPI is unavailable.
    """
    if not _FASTAPI_OK:
        raise ImportError("fastapi is required: pip install fastapi jinja2")

    templates = _get_templates()
    app = FastAPI(
        title="CVG Rainfall Wizard Web",
        version=__version__,
        description="NOAA PFDS + NRCS TR-55 Rainfall and Runoff Analysis Web UI\n\xa9 Clearview Geographic LLC",
    )

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def landing(request: Request):
        """Marketing landing page — product overview for the Rainfall Wizard."""
        return templates.TemplateResponse("landing.html", {
            "request": request,
            "version": __version__,
        })

    @app.get("/wizard", response_class=HTMLResponse, include_in_schema=False)
    async def index(request: Request):
        """Serve the main rainfall wizard form (index.html)."""
        return templates.TemplateResponse("index.html", {
            "request": request,
            "version": __version__,
        })

    @app.post("/runoff", response_class=HTMLResponse, include_in_schema=False)
    async def runoff(
        request: Request,
        lat: float = Form(...),
        lon: float = Form(...),
        return_period_yr: int = Form(100),
        duration_hr: float = Form(24.0),
        curve_number: Optional[float] = Form(None),
        drainage_area_acres: Optional[float] = Form(None),
        project_name: Optional[str] = Form(None),
        noaa_station: Optional[str] = Form(None),
        slr_scenario: Optional[str] = Form(None),
        planning_year: Optional[int] = Form(None),
    ):
        """Compute NOAA PFDS rainfall depth + optional TR-55 runoff and render result.html."""
        from .pfds import fetch_pfds_depths
        from .runoff import compute_runoff, cn_runoff_depth

        rainfall_in: Optional[float] = None
        runoff_in:   Optional[float] = None
        peak_flow_cfs: Optional[float] = None
        idf_table: Optional[Dict] = None
        error: Optional[str] = None

        # --- Fetch NOAA PFDS depth ------------------------------------------
        try:
            pfds_result = fetch_pfds_depths(
                lat=lat, lon=lon,
                duration_hr=duration_hr,
            )
            rainfall_in = pfds_result.get_depth_inches(return_period_yr)
            if rainfall_in is None:
                error = f"No PFDS data for {return_period_yr}-yr at ({lat:.4f}, {lon:.4f})"
        except Exception as exc:
            error = str(exc)
            log.warning("PFDS fetch failed: %s", exc)

        # --- TR-55 CN Runoff --------------------------------------------
        if rainfall_in is not None and curve_number is not None:
            try:
                rr = compute_runoff(rainfall_in, curve_number)
                runoff_in = round(rr.runoff_depth_in, 3)
                # Simple peak flow estimate: Q/12 * A * 43560 / (Tc * 3600)
                # Use duration_hr as an approximation for Tc
                if drainage_area_acres and runoff_in:
                    vol_ft3 = (runoff_in / 12.0) * drainage_area_acres * 43560.0
                    peak_flow_cfs = round(vol_ft3 / (duration_hr * 3600.0), 2)
            except Exception as exc:
                log.warning("Runoff compute failed: %s", exc)
                if not error:
                    error = str(exc)

        # --- Build IDF table (best-effort) ----------------------------------
        try:
            from .noaa import get_pfds_cached
            resp = get_pfds_cached(lat, lon)
            rows: Dict[str, Dict] = {}
            for est in resp.estimates:
                rows.setdefault(est.get("duration_code", ""), {})[str(est.get("return_period", ""))] = est.get("depth_in")
            idf_table = {"rows": rows, "return_periods": [2, 5, 10, 25, 50, 100, 200, 500, 1000]}
        except Exception:
            pass  # IDF table is optional

        return templates.TemplateResponse("result.html", {
            "request":           request,
            "lat":               lat,
            "lon":               lon,
            "return_period_yr":  return_period_yr,
            "duration_hr":       duration_hr,
            "curve_number":      curve_number,
            "drainage_area_acres": drainage_area_acres,
            "project_name":      project_name or "",
            "rainfall_in":       round(rainfall_in, 3) if rainfall_in is not None else None,
            "runoff_in":         runoff_in,
            "peak_flow_cfs":     peak_flow_cfs,
            "idf_table":         idf_table,
            "error":             error,
            "version":           __version__,
        })

    @app.get("/health")
    async def health():
        """Liveness probe for Caddy health checks and Docker healthcheck."""
        return {"status": "ok", "service": "CVG Rainfall Wizard", "version": __version__}

    return app


# ---------------------------------------------------------------------------
# Module-level app instance (for uvicorn/gunicorn direct import)
# ---------------------------------------------------------------------------
if _FASTAPI_OK:
    try:
        app = create_web_app()
    except Exception as _e:
        log.warning("Could not create web app at import time: %s", _e)
        app = None
else:
    app = None
