"""
tests/test_graph_engine.py

Unit tests for the NetworkX graph engine.
Run with: python -m pytest tests/test_graph_engine.py -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.services.graph_engine import (
    build_graph,
    get_interactions_for_drugs,
    get_severity_summary,
)

# ── Sample interaction data (mirrors fallback_interactions.json) ──────────────
SAMPLE_INTERACTIONS = [
    {
        "drug_a_rxcui": "202433",
        "drug_a_name":  "warfarin",
        "drug_b_rxcui": "1191",
        "drug_b_name":  "aspirin",
        "severity":     "high",
        "description":  "Warfarin + Aspirin increases bleeding risk.",
        "source":       "curated",
    },
    {
        "drug_a_rxcui": "202433",
        "drug_a_name":  "warfarin",
        "drug_b_rxcui": "5640",
        "drug_b_name":  "ibuprofen",
        "severity":     "high",
        "description":  "Warfarin + Ibuprofen increases bleeding risk.",
        "source":       "curated",
    },
    {
        "drug_a_rxcui": "1191",
        "drug_a_name":  "aspirin",
        "drug_b_rxcui": "5640",
        "drug_b_name":  "ibuprofen",
        "severity":     "medium",
        "description":  "Aspirin + Ibuprofen interfere with each other.",
        "source":       "curated",
    },
]


class TestBuildGraph:

    def test_correct_node_count(self):
        G = build_graph(SAMPLE_INTERACTIONS)
        # warfarin, aspirin, ibuprofen
        assert G.number_of_nodes() == 3

    def test_correct_edge_count(self):
        G = build_graph(SAMPLE_INTERACTIONS)
        assert G.number_of_edges() == 3

    def test_node_attributes(self):
        G = build_graph(SAMPLE_INTERACTIONS)
        assert G.nodes["202433"]["type"] == "drug"
        assert G.nodes["202433"]["name"] == "warfarin"

    def test_edge_severity(self):
        G = build_graph(SAMPLE_INTERACTIONS)
        edge = G["202433"]["1191"]
        assert edge["severity"] == "high"
        assert edge["type"] == "drug_drug"

    def test_empty_interactions_returns_empty_graph(self):
        G = build_graph([])
        assert G.number_of_nodes() == 0
        assert G.number_of_edges() == 0


class TestGetInteractionsForDrugs:

    def test_returns_all_interactions_for_drug_set(self):
        G = build_graph(SAMPLE_INTERACTIONS)
        results = get_interactions_for_drugs(G, ["202433", "1191", "5640"])
        assert len(results) == 3

    def test_returns_subset_for_partial_drug_set(self):
        G = build_graph(SAMPLE_INTERACTIONS)
        # Only warfarin + aspirin
        results = get_interactions_for_drugs(G, ["202433", "1191"])
        assert len(results) == 1
        assert results[0]["severity"] == "high"

    def test_returns_empty_for_single_drug(self):
        G = build_graph(SAMPLE_INTERACTIONS)
        results = get_interactions_for_drugs(G, ["202433"])
        assert results == []

    def test_sorted_high_first(self):
        G = build_graph(SAMPLE_INTERACTIONS)
        results = get_interactions_for_drugs(G, ["202433", "1191", "5640"])
        severities = [r["severity"] for r in results]
        # High should come before medium
        assert severities.index("high") < severities.index("medium")


class TestGetSeveritySummary:

    def test_counts_correctly(self):
        interactions = [
            {"severity": "high"},
            {"severity": "high"},
            {"severity": "medium"},
            {"severity": "low"},
        ]
        summary = get_severity_summary(interactions)
        assert summary["high"]   == 2
        assert summary["medium"] == 1
        assert summary["low"]    == 1
        assert summary["total"]  == 4

    def test_empty_interactions(self):
        summary = get_severity_summary([])
        assert summary["total"] == 0
