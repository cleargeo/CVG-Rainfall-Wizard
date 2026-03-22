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
report.py — JSON and PDF report generation for the Rainfall Wizard.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__

log = logging.getLogger(__name__)

REPORT_SCHEMA_VERSION = "1.0.0"
CVG_HEADER = (
    "© Clearview Geographic LLC — Proprietary | "
    "Author: Alex Zelenski, GISP | "
    "azelenski@clearviewgeographic.com | 386-957-2314 | clearviewgeographic.com"
)
NOAA_ATLAS14_REF = (
    "Perica, S. et al. (2011–2019). NOAA Atlas 14 Precipitation-Frequency Atlas "
    "of the United States. NOAA, National Weather Service. Silver Spring, MD. "
    "https://hdsc.nws.noaa.gov/pfds/"
)
TR55_REF = (
    "USDA-NRCS (1986). Urban Hydrology for Small Watersheds. "
    "Technical Release 55 (TR-55), 2nd Edition."
)

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )
    _REPORTLAB_OK = True
except ImportError:
    _REPORTLAB_OK = False


def build_json_report(result, config, extra: Optional[Dict] = None) -> Dict[str, Any]:
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "tool": "CVG Rainfall Wizard",
        "tool_version": __version__,
        "generated_utc": datetime.utcnow().isoformat() + "Z",
        "copyright": CVG_HEADER,
        "references": [NOAA_ATLAS14_REF, TR55_REF],
        "run": result.to_dict(),
        "config": vars(config) if not hasattr(config, "to_dict") else config.to_dict(),
    }
    if extra:
        report.update(extra)
    return report


def write_json_report(result, config, output_path: str | Path, extra: Optional[Dict] = None) -> None:
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    report = build_json_report(result, config, extra)
    with p.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    log.info("JSON report → %s", p)


def write_pdf_report(result, config, output_path: str | Path) -> bool:
    if not _REPORTLAB_OK:
        log.warning("reportlab not installed — PDF skipped.")
        return False

    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(p), pagesize=letter,
                            rightMargin=0.75*inch, leftMargin=0.75*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<b>CVG Rainfall Wizard — Depth Grid Analysis Report</b>", styles["Title"]))
    story.append(Paragraph(CVG_HEADER, styles["Normal"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.darkblue))
    story.append(Spacer(1, 0.1*inch))

    story.append(Paragraph("<b>Run Summary</b>", styles["Heading2"]))
    summary = [
        ["Project", getattr(config, "project_name", "—")],
        ["Run ID", result.run_id],
        ["Generated (UTC)", datetime.utcnow().strftime("%Y-%m-%d %H:%M")],
        ["Tool Version", __version__],
    ]
    story.append(_table(summary))
    story.append(Spacer(1, 0.1*inch))

    story.append(Paragraph("<b>Rainfall Parameters</b>", styles["Heading2"]))
    rain_data = [
        ["Latitude", f"{getattr(config, 'lat', 0.0):.4f}°"],
        ["Longitude", f"{getattr(config, 'lon', 0.0):.4f}°"],
        ["Return Period", f"{result.return_period_yr}-year"],
        ["Duration", f"{result.duration_hr:.1f} hr"],
        ["Storm Type", result.storm_type or "—"],
        ["Design Rainfall (in)", f"{result.rainfall_depth_in:.3f}"],
        ["Curve Number (CN)", f"{result.cn:.0f}"],
        ["Runoff Depth (in)", f"{result.runoff_depth_in:.3f}"],
        ["Runoff Fraction", f"{result.runoff_fraction*100:.1f}%"],
    ]
    story.append(_table(rain_data))
    story.append(Spacer(1, 0.1*inch))

    story.append(Paragraph("<b>Grid Statistics</b>", styles["Heading2"]))
    grid_data = [
        ["Inundated Cells", f"{result.inundated_cells:,}"],
        ["Total Valid Cells", f"{result.total_cells:,}"],
        ["Inundated Area (%)", f"{result.inundated_pct:.1f}%"],
        ["Inundated Area (m²)", f"{result.inundated_area_m2:,.0f}"],
        ["Max Depth (ft)", f"{result.max_depth_ft:.2f}"],
        ["Mean Depth (ft)", f"{result.mean_depth_ft:.2f}"],
        ["Elapsed (s)", f"{result.elapsed_sec:.1f}"],
    ]
    story.append(_table(grid_data))
    story.append(Spacer(1, 0.1*inch))

    if result.qa_flags:
        story.append(Paragraph("<b>QA Flags</b>", styles["Heading2"]))
        for f in result.qa_flags:
            story.append(Paragraph(f"• {f}", styles["Normal"]))
        story.append(Spacer(1, 0.1*inch))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph("<b>References</b>", styles["Heading3"]))
    story.append(Paragraph(NOAA_ATLAS14_REF, styles["Normal"]))
    story.append(Paragraph(TR55_REF, styles["Normal"]))

    doc.build(story)
    log.info("PDF report → %s", p)
    return True


def _table(data: List[List[str]]) -> "Table":
    t = Table(data, colWidths=[2.5*inch, 4.5*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E3F2FD")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def write_reports(result, config, output_dir: str | Path) -> Dict[str, str]:
    from .paths import get_report_path
    rp = result.return_period_yr
    dur = result.duration_hr
    prefix = getattr(config, "project_name", "rainfall")
    out_dir = Path(output_dir)
    out: Dict[str, str] = {}

    json_path = get_report_path(prefix, rp, dur, out_dir, "json")
    write_json_report(result, config, json_path)
    out["json"] = str(json_path)

    pdf_path = get_report_path(prefix, rp, dur, out_dir, "pdf")
    if write_pdf_report(result, config, pdf_path):
        out["pdf"] = str(pdf_path)

    return out
