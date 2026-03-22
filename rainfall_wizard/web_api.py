# -*- coding: utf-8 -*-
# =============================================================================
# (c) Clearview Geographic LLC -- All Rights Reserved | Est. 2018
# Proprietary Software -- Internal Use Only
# Protected under US and International copyright, trade secret,
# trademark, cybersecurity, and intellectual property law.
# This Product is developed under CVG's Agentic Development Framework (ADF).
# Unauthorized use, replication, or modification is strictly prohibited.
# -----------------------------------------------------------------------------
# Author      : Alex Zelenski, GISP
# Organization: Clearview Geographic, LLC
# Contact     : azelenski@clearviewgeographic.com  |  386-957-2314
# License     : Proprietary -- CVG-ADF
# =============================================================================
"""
web_api.py — FastAPI application for the CVG Rainfall Wizard.

Endpoints:
  GET  /                 — Health check / version
  GET  /api/pfds         — Fetch NOAA Atlas 14 data for a point
  POST /api/run          — Run depth grid analysis
  GET  /api/insights     — Search knowledge base
  GET  /api/idf          — Get IDF table for a point / return period
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    _FASTAPI_OK = True
except ImportError:
    _FASTAPI_OK = False


if _FASTAPI_OK:

    class RunRequest(BaseModel):
        lat: float
        lon: float
        duration_hr: float = 24.0
        return_period_yr: int = 100
        curve_number: float = 75.0
        dem_path: str
        dem_unit: str = "m"
        output_path: str = ""
        project_name: str = "rainfall_api_run"
        ia_ratio: float = 0.2

    def create_app() -> "FastAPI":
        from . import __version__
        app = FastAPI(
            title="CVG Rainfall Wizard API",
            description=(
                "NOAA Atlas 14 Rainfall Frequency + NRCS CN Depth Grid Tool\n"
                "© Clearview Geographic LLC"
            ),
            version=__version__,
            contact={"name": "Alex Zelenski, GISP", "email": "azelenski@clearviewgeographic.com"},
        )
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
        _register_routes(app)
        return app

    def _register_routes(app: "FastAPI") -> None:

        @app.get("/")
        async def root():
            from . import __version__
            return {
                "tool": "CVG Rainfall Wizard",
                "version": __version__,
                "status": "ok",
                "copyright": "© Clearview Geographic LLC",
            }

        @app.get("/api/pfds")
        async def pfds(
            lat: float = Query(..., description="Latitude"),
            lon: float = Query(..., description="Longitude"),
            duration_hr: float = Query(24.0, description="Duration in hours"),
            return_period_yr: int = Query(100, description="Return period in years"),
        ):
            from .noaa import get_pfds_cached, STANDARD_RETURN_PERIODS_YR
            try:
                resp = get_pfds_cached(lat, lon)
            except Exception as e:
                raise HTTPException(status_code=503, detail=f"PFDS fetch failed: {e}")

            pfe = resp.get(duration_hr, return_period_yr)
            if pfe is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"No data for duration={duration_hr}hr, rp={return_period_yr}yr at ({lat},{lon})"
                )
            return pfe.to_dict()

        @app.get("/api/pfds/table")
        async def pfds_table(
            lat: float = Query(...),
            lon: float = Query(...),
        ):
            from .noaa import get_pfds_cached
            try:
                resp = get_pfds_cached(lat, lon)
            except Exception as e:
                raise HTTPException(status_code=503, detail=str(e))
            return {
                "lat": lat, "lon": lon,
                "state": resp.state, "county": resp.county,
                "atlas": resp.atlas_series,
                "estimates": [e.to_dict() for e in resp.estimates],
            }

        @app.post("/api/run")
        async def run(payload: RunRequest):
            from .config import RainfallConfig
            from .processing import run_rainfall_analysis
            from .report import build_json_report

            cfg = RainfallConfig(
                lat=payload.lat, lon=payload.lon,
                duration_hr=payload.duration_hr,
                return_period_yr=payload.return_period_yr,
                curve_number=payload.curve_number,
                dem_path=payload.dem_path,
                dem_unit=payload.dem_unit,
                output_path=payload.output_path,
                project_name=payload.project_name,
            )
            try:
                result = run_rainfall_analysis(cfg, resume=False)
                return build_json_report(result, cfg)
            except FileNotFoundError as e:
                raise HTTPException(status_code=422, detail=str(e))
            except Exception as e:
                log.exception("Run failed")
                raise HTTPException(status_code=500, detail=str(e))

        @app.get("/api/runoff")
        async def runoff(
            rainfall_in: float = Query(...),
            cn: float = Query(75.0),
            ia_ratio: float = Query(0.2),
        ):
            from .runoff import compute_runoff
            result = compute_runoff(rainfall_in, cn, ia_ratio)
            return result.to_dict()

        @app.get("/api/insights")
        async def insights(q: str = Query("")):
            from .insights import search_insights
            return [e.to_dict() for e in search_insights(q)]

        @app.get("/api/insights/{topic}")
        async def insight_topic(topic: str):
            from .insights import get_guidance
            entry = get_guidance(topic)
            if not entry:
                raise HTTPException(status_code=404, detail=f"Topic not found: {topic}")
            return entry.to_dict()

        @app.get(
            "/api/wizards/status",
            summary="Status of all CVG Wizard subsystems",
            tags=["ops"],
        )
        async def wizards_status():
            import sys, os, datetime
            def _probe(pkg, path):
                try:
                    root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), path)
                    if root not in sys.path:
                        sys.path.insert(0, root)
                    mod = __import__(pkg)
                    return {"available": True, "version": getattr(mod, "__version__", "unknown"), "error": None}
                except Exception as exc:
                    return {"available": False, "version": None, "error": str(exc)}
            try:
                from rainfall_wizard import __version__ as _v
            except Exception:
                _v = "unknown"
            return {
                "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "wizards": {
                    "rainfall_wizard": {"available": True, "version": _v, "error": None, "default_port": 8002,
                        "endpoints": ["GET /", "GET /health", "GET /api/pfds", "GET /api/pfds/table",
                                      "GET /api/runoff", "POST /api/run", "GET /api/insights",
                                      "GET /api/insights/{topic}", "GET /api/storms/active",
                                      "GET /api/idf", "GET /api/wizards/status"]},
                    "storm_surge_wizard": {**_probe("storm_surge_wizard", "CVG_Storm Surge Wizard"), "default_port": 8080},
                    "slr_wizard": {**_probe("slr_wizard", "CVG_SLR Wizard"), "default_port": 8001},
                },
            }

        # ── /health ──────────────────────────────────────────────────────────

        @app.get("/health", summary="Liveness probe", tags=["ops"])
        async def health():
            """Return service status and version (used by Caddy health_uri checks)."""
            import datetime
            from rainfall_wizard import __version__ as _v
            return {
                "status": "ok",
                "service": "CVG Rainfall Wizard",
                "version": _v,
                "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }

        # ── /api/storms/active ────────────────────────────────────────────────

        @app.get(
            "/api/storms/active",
            summary="Active NHC tropical storms",
            tags=["nhc"],
        )
        async def active_storms(timeout: float = 20.0):
            """Proxy the NHC CurrentStorms.json feed — returns active storms or empty list.

            Active tropical storms directly influence precipitation intensification.
            Use this endpoint to contextualize your NOAA PFDS rainfall analysis with
            current NHC advisories.
            """
            import urllib.request, json as _json
            NHC_URL = "https://www.nhc.noaa.gov/CurrentStorms.json"
            try:
                req = urllib.request.Request(NHC_URL, headers={"User-Agent": "CVG-Rainfall-Wizard/1.0"})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = _json.loads(resp.read())
                raw = data.get("activeStorms", [])
                storms = []
                for s in (raw if isinstance(raw, list) else []):
                    storms.append({
                        "id":             s.get("id"),
                        "name":           s.get("name"),
                        "classification": s.get("classification"),
                        "intensity":      s.get("intensity"),
                        "lat":            s.get("lat"),
                        "lon":            s.get("lon"),
                        "advisory_url":   s.get("advisoryUrl") or s.get("advisoryurl"),
                    })
                return storms
            except Exception as exc:
                log.warning("NHC feed unavailable: %s", exc)
                return []

        # ── /api/idf ─────────────────────────────────────────────────────────

        @app.get(
            "/api/idf",
            summary="Full IDF table for a lat/lon point",
            tags=["pfds"],
        )
        async def idf(
            lat: float = Query(..., description="Latitude"),
            lon: float = Query(..., description="Longitude"),
        ):
            """Return a full Intensity-Duration-Frequency (IDF) table for a point.

            Fetches all available NOAA Atlas 14 return periods and durations,
            returned as a nested dict: ``{duration_hr: {return_period_yr: depth_in}}``.
            """
            from .noaa import get_pfds_cached
            try:
                resp = get_pfds_cached(lat, lon)
            except Exception as e:
                raise HTTPException(status_code=503, detail=f"PFDS fetch failed: {e}")

            # Build IDF table: duration_hr → {return_period: depth_in}
            table: dict = {}
            for est in resp.estimates:
                dur = est.get("duration_hr") or est.get("duration_code", "")
                rp  = str(est.get("return_period") or est.get("return_period_yr", ""))
                dep = est.get("depth_in") or est.get("mean_in")
                if dur and rp and dep is not None:
                    table.setdefault(str(dur), {})[rp] = round(dep, 3) if isinstance(dep, float) else dep

            return {
                "lat": lat,
                "lon": lon,
                "state": resp.state if hasattr(resp, "state") else None,
                "county": resp.county if hasattr(resp, "county") else None,
                "atlas": resp.atlas_series if hasattr(resp, "atlas_series") else "NOAA Atlas 14",
                "idf_table": table,
                "source": "NOAA PFDS / Atlas 14",
            }


else:
    def create_app():
        raise ImportError("fastapi required: pip install fastapi pydantic")
