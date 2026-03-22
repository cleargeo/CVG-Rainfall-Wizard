# -*- coding: utf-8 -*-
# Clearview Geographic LLC — Proprietary and Confidential
"""Tests for rainfall_wizard.insights module."""

from __future__ import annotations

import pytest

from rainfall_wizard.insights import (
    InsightEntry,
    get_guidance,
    list_topics,
    search_insights,
)


# ---------------------------------------------------------------------------
# InsightEntry
# ---------------------------------------------------------------------------

class TestInsightEntry:
    """Unit tests for InsightEntry dataclass."""

    def test_construction(self):
        entry = InsightEntry(
            topic="test_topic",
            title="Test Title",
            body="Test body content.",
            tags=["tag1", "tag2"],
            source="Test Source",
            url="https://example.com",
        )
        assert entry.topic == "test_topic"
        assert entry.title == "Test Title"
        assert entry.body == "Test body content."
        assert "tag1" in entry.tags
        assert entry.source == "Test Source"
        assert entry.url == "https://example.com"

    def test_to_dict_round_trip(self):
        entry = InsightEntry(
            topic="atlas14",
            title="NOAA Atlas 14",
            body="Precipitation frequency data.",
            tags=["noaa", "pfds"],
            source="NOAA",
            url="https://hdsc.nws.noaa.gov/pfds/",
        )
        d = entry.to_dict()
        assert d["topic"] == "atlas14"
        assert d["title"] == "NOAA Atlas 14"
        assert d["body"] == "Precipitation frequency data."
        assert "noaa" in d["tags"]
        assert d["source"] == "NOAA"
        assert d["url"] == "https://hdsc.nws.noaa.gov/pfds/"

    def test_to_dict_has_all_keys(self):
        entry = InsightEntry(topic="t", title="T", body="B")
        d = entry.to_dict()
        for key in ("topic", "title", "body", "tags", "source", "url"):
            assert key in d, f"Missing key: {key}"

    def test_tags_default_empty_list(self):
        entry = InsightEntry(topic="t", title="T", body="B")
        assert entry.tags == []

    def test_matches_by_topic(self):
        entry = InsightEntry(topic="curve_number", title="CN Method", body="Details.")
        assert entry.matches("curve_number")

    def test_matches_by_title(self):
        entry = InsightEntry(topic="t", title="NOAA Atlas 14 Overview", body="Details.")
        assert entry.matches("atlas 14")

    def test_matches_by_body(self):
        entry = InsightEntry(topic="t", title="T", body="NRCS TR-55 runoff method.")
        assert entry.matches("tr-55")

    def test_matches_by_tag(self):
        entry = InsightEntry(topic="t", title="T", body="B", tags=["pfds", "atlas14"])
        assert entry.matches("pfds")

    def test_matches_case_insensitive(self):
        entry = InsightEntry(topic="CURVE_NUMBER", title="Curve Number", body="B")
        assert entry.matches("curve_number")

    def test_no_match(self):
        entry = InsightEntry(topic="weather", title="Weather", body="Rain.", tags=["rain"])
        assert not entry.matches("earthquake")


# ---------------------------------------------------------------------------
# search_insights
# ---------------------------------------------------------------------------

class TestSearchInsights:
    """Tests for search_insights()."""

    def test_empty_query_returns_default(self):
        results = search_insights("")
        assert len(results) >= 1

    def test_search_atlas14_returns_entry(self):
        results = search_insights("atlas14")
        assert len(results) >= 1
        assert any("atlas14" in e.topic.lower() or "atlas14" in e.tags for e in results)

    def test_search_design_storm_returns_entry(self):
        # "design storm" appears in storm_type entry title: "SCS Design Storm Types"
        results = search_insights("design storm")
        assert len(results) >= 1

    def test_search_scs_returns_entry(self):
        # "scs" is a tag on the storm_type entry
        results = search_insights("scs")
        assert len(results) >= 1

    def test_search_curve_number_returns_entry(self):
        results = search_insights("curve number")
        assert len(results) >= 1

    def test_search_idf_returns_entry(self):
        results = search_insights("idf")
        assert len(results) >= 1

    def test_search_compound_returns_entry(self):
        results = search_insights("compound")
        assert len(results) >= 1

    def test_search_noaa_returns_results(self):
        results = search_insights("noaa")
        assert len(results) >= 1

    def test_max_results_respected(self):
        results = search_insights("", max_results=3)
        assert len(results) <= 3

    def test_nonsense_query_returns_empty(self):
        results = search_insights("xyzzy_nomatch_9999")
        assert len(results) == 0


# ---------------------------------------------------------------------------
# get_guidance
# ---------------------------------------------------------------------------

class TestGetGuidance:
    """Tests for get_guidance() using actual KB topic keys and tags."""

    def test_get_atlas14_guidance(self):
        result = get_guidance("atlas14")
        assert result is not None
        assert "atlas14" in result.topic.lower() or "atlas14" in result.tags

    def test_get_return_period_guidance(self):
        result = get_guidance("return_period")
        assert result is not None

    def test_get_curve_number_guidance(self):
        # Topic key is "curve_number" in the KB
        result = get_guidance("curve_number")
        assert result is not None

    def test_get_storm_type_guidance(self):
        # Topic key is "storm_type" in the KB
        result = get_guidance("storm_type")
        assert result is not None

    def test_get_idf_curve_guidance(self):
        # Topic key is "idf_curve" in the KB
        result = get_guidance("idf_curve")
        assert result is not None

    def test_get_compound_flood_guidance(self):
        # Topic key is "compound_flood" in the KB
        result = get_guidance("compound_flood")
        assert result is not None

    def test_get_guidance_by_tag_cn(self):
        # "cn" is a tag on the curve_number entry
        result = get_guidance("cn")
        assert result is not None

    def test_get_guidance_by_tag_scs(self):
        # "scs" is a tag on the storm_type entry
        result = get_guidance("scs")
        assert result is not None

    def test_get_guidance_by_tag_idf(self):
        # "idf" is a tag on the idf_curve entry
        result = get_guidance("idf")
        assert result is not None

    def test_get_guidance_by_tag_compound(self):
        # "compound" is a tag on the compound_flood entry
        result = get_guidance("compound")
        assert result is not None

    def test_get_nonexistent_topic_returns_none(self):
        result = get_guidance("nonexistent_topic_xyz")
        assert result is None

    @pytest.mark.parametrize("topic", [
        "atlas14",
        "return_period",
        "curve_number",
        "storm_type",
        "idf_curve",
        "climate_change",
        "compound_flood",
    ])
    def test_all_kb_topics_return_non_none(self, topic):
        result = get_guidance(topic)
        assert result is not None, f"get_guidance('{topic}') returned None"


# ---------------------------------------------------------------------------
# list_topics
# ---------------------------------------------------------------------------

class TestListTopics:
    """Tests for list_topics()."""

    def test_returns_list(self):
        topics = list_topics()
        assert isinstance(topics, list)

    def test_contains_expected_topics(self):
        topics = list_topics()
        expected = {"atlas14", "return_period", "curve_number", "storm_type",
                    "idf_curve", "climate_change", "compound_flood"}
        for t in expected:
            assert t in topics, f"Expected topic '{t}' not found in list_topics()"

    def test_no_duplicates(self):
        topics = list_topics()
        assert len(topics) == len(set(topics))
