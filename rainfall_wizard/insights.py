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
insights.py — Knowledge base and guidance lookup for the Rainfall Wizard.

Covers NOAA Atlas 14, NRCS TR-55, design storm selection, CN methods,
IDF interpretation, and stormwater engineering best practices.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class InsightEntry:
    topic: str
    title: str
    body: str
    tags: List[str] = field(default_factory=list)
    source: str = ""
    url: str = ""

    def matches(self, query: str) -> bool:
        q = query.lower()
        return (
            q in self.topic.lower()
            or q in self.title.lower()
            or q in self.body.lower()
            or any(q in t for t in self.tags)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {"topic": self.topic, "title": self.title, "body": self.body,
                "tags": self.tags, "source": self.source, "url": self.url}


_KB: List[InsightEntry] = [
    InsightEntry(
        topic="atlas14",
        title="NOAA Atlas 14 Overview",
        body=(
            "NOAA Atlas 14 (Perica et al. 2011–2019) is the official NOAA source "
            "for precipitation frequency estimates (PFEs) across the United States.  "
            "It supersedes TP-40 (1961) and HYDRO-35 (1977) for all regions.\n\n"
            "Atlas 14 provides:\n"
            "  • Partial-duration series (PDS) and annual-maximum series (AMS)\n"
            "  • Durations: 5 min to 60 days\n"
            "  • Return periods: 1 to 1,000 years\n"
            "  • 90% confidence intervals for each estimate\n\n"
            "Data are available via the NOAA PFDS online tool at:\n"
            "  https://hdsc.nws.noaa.gov/pfds/"
        ),
        tags=["atlas14", "noaa", "pfds", "precipitation", "frequency", "pfe"],
        source="NOAA Atlas 14",
        url="https://hdsc.nws.noaa.gov/pfds/",
    ),
    InsightEntry(
        topic="return_period",
        title="Return Period vs. Annual Exceedance Probability (AEP)",
        body=(
            "A '100-year storm' is NOT a storm that occurs once every 100 years.  "
            "It is a rainfall event with a 1% Annual Exceedance Probability (AEP) — "
            "meaning it has a 1% chance of being equaled or exceeded in any given year.\n\n"
            "Common return periods and their AEP equivalents:\n"
            "  • 2-yr   = 50% AEP\n"
            "  • 10-yr  = 10% AEP\n"
            "  • 25-yr  =  4% AEP\n"
            "  • 50-yr  =  2% AEP\n"
            "  • 100-yr =  1% AEP  (FEMA base flood; BFE definition)\n"
            "  • 500-yr = 0.2% AEP  (FEMA Zone X shaded; critical facilities)\n\n"
            "NOTE: Climate change is increasing rainfall intensities across most of the "
            "US.  Historical Atlas 14 values may underestimate future design storms."
        ),
        tags=["return_period", "aep", "100yr", "fema", "bfe", "probability"],
        source="NOAA Atlas 14; FEMA NFIP",
    ),
    InsightEntry(
        topic="curve_number",
        title="NRCS Curve Number (CN) Method",
        body=(
            "The NRCS Curve Number (CN) method (TR-55, 1986) is the most widely used "
            "lumped-parameter runoff estimation method in US stormwater practice.\n\n"
            "Key concepts:\n"
            "  S = 1000/CN − 10       (potential maximum retention, inches)\n"
            "  Ia = 0.2S              (initial abstraction = depression storage + ET)\n"
            "  Q = (P − Ia)² / (P − Ia + S)  when P > Ia\n\n"
            "CN ranges by land use (HSG B/C):\n"
            "  • Dense forest / wetlands    : CN 30–55\n"
            "  • Pasture / open space       : CN 61–74\n"
            "  • Low-density residential    : CN 70–80\n"
            "  • Commercial / impervious    : CN 88–95\n"
            "  • Fully paved               : CN 98\n\n"
            "Urban/high-imperviousness areas: use Ia = 0.05S instead of 0.2S for better\n"
            "agreement with observed data (NRCS 2004 update)."
        ),
        tags=["cn", "curve_number", "runoff", "tr55", "nrcs", "impervious"],
        source="USDA-NRCS TR-55 (1986) / TR-20",
    ),
    InsightEntry(
        topic="storm_type",
        title="SCS Design Storm Types",
        body=(
            "The NRCS (formerly SCS) defines four dimensionless 24-hr design storm "
            "distributions for the US, based on geographic region:\n"
            "  • Type I   — Pacific coast (low-intensity, long-duration)\n"
            "  • Type IA  — Pacific Northwest / Hawaii (lowest intensity)\n"
            "  • Type II  — Most of CONUS east of Rockies (most severe; use for SE/Gulf)\n"
            "  • Type III — Gulf Coast, Atlantic coastal Louisiana (high-intensity,\n"
            "               flat topography, slow soil drainage)\n\n"
            "For Florida and Gulf Coast states: Type II and Type III are commonly\n"
            "specified by local design standards.  When in doubt, use Type II as\n"
            "conservative; Type III produces slightly less peak but more total volume."
        ),
        tags=["storm_type", "scs", "type2", "type3", "hyetograph", "design_storm"],
        source="USDA-NRCS TR-55 (1986)",
    ),
    InsightEntry(
        topic="idf_curve",
        title="IDF Curve Interpretation and Use",
        body=(
            "An IDF (Intensity-Duration-Frequency) curve relates rainfall intensity "
            "(in/hr) to storm duration (min or hr) for a specific return period.\n\n"
            "Key uses:\n"
            "  • Rational method: Q = CiA  (peak discharge, cfs)\n"
            "  • Design of inlets, culverts, detention ponds\n"
            "  • Alternating block hyetograph construction\n\n"
            "IDF values decrease with duration (inverse relationship):\n"
            "  Longer duration → lower intensity → more total depth\n\n"
            "Retrieve directly from NOAA PFDS by dividing Atlas 14 depth (in) by\n"
            "duration (hr) for each return period.\n\n"
            "Chen (1983) three-parameter fit:  i = a / (t + b)^c\n"
            "is widely used to parameterize IDF curves for analytical use."
        ),
        tags=["idf", "intensity", "duration", "frequency", "rational_method", "chen"],
        source="NOAA Atlas 14; Chen (1983)",
    ),
    InsightEntry(
        topic="climate_change",
        title="Climate Change and Rainfall Frequency",
        body=(
            "Historical precipitation records, including NOAA Atlas 14, are based on "
            "data predating widespread climate change impacts.  Research shows:\n"
            "  • 100-yr event intensity has increased 15–40% in parts of the SE US\n"
            "    since Atlas 14 publication periods (Risser & Wehner 2017; ASCE 7-22)\n"
            "  • Short-duration extreme events (1–3 hr) are increasing faster than\n"
            "    longer durations\n"
            "  • NOAA is developing Atlas 15 to incorporate observed trends and\n"
            "    near-term future projections (expected ~2025–2027)\n\n"
            "Current best practice:\n"
            "  Apply a multiplier of 1.1–1.3× to Atlas 14 depths for critical\n"
            "  infrastructure with design life >50 years.  Check local/state guidance\n"
            "  (FL FDEP, GA EPD, FHWA HEC-17) for jurisdiction-specific requirements."
        ),
        tags=["climate_change", "non_stationary", "atlas15", "future_rainfall", "frequency"],
        source="NOAA; ASCE 7-22; Risser & Wehner (2017)",
    ),
    InsightEntry(
        topic="compound_flood",
        title="Compound Flooding: Rainfall + Storm Surge + SLR",
        body=(
            "In coastal areas, heavy rainfall coinciding with storm surge or high tides "
            "produces compound flood events.  Key considerations:\n"
            "  • Coastal drainage outlets can be submerged by tide/surge, blocking\n"
            "    discharge and causing inland ponding to increase significantly\n"
            "  • Sea level rise elevates the baseline water level, reducing\n"
            "    gravity-drainage capacity\n"
            "  • NOAA / FEMA research shows compound events have increased in frequency\n"
            "    along the US Atlantic and Gulf coasts\n\n"
            "Do NOT add independent return-period depths for surge + rainfall.\n"
            "Use joint-probability analysis (e.g., FEMA CFA, USACE CARP) or\n"
            "physically-based hydrodynamic models (HEC-RAS 2D, ADCIRC+SWAN)."
        ),
        tags=["compound", "surge", "slr", "coastal", "joint_probability"],
        source="NOAA/FEMA Compound Flooding Research; Sweet et al. (2022)",
    ),
]


def search_insights(query: str, max_results: int = 5) -> List[InsightEntry]:
    if not query.strip():
        return _KB[:max_results]
    return [e for e in _KB if e.matches(query)][:max_results]


def get_guidance(topic: str) -> Optional[InsightEntry]:
    for e in _KB:
        if topic.lower() in e.topic.lower() or topic.lower() in [t.lower() for t in e.tags]:
            return e
    return None


def list_topics() -> List[str]:
    return [e.topic for e in _KB]
