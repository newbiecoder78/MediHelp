"""
app/services/graph_engine.py

NetworkX knowledge graph for drug-drug and drug-food interactions.

Node schema:
    Drug node  → id = rxcui or "drug:<name>" (str), type="drug", name=str, drug_class=str
    Food node  → id = "food:<name>", type="food", name=str, display=str

Edge schema:
    Drug-Drug  → type="drug_drug", severity="high|medium|low", description=str, source=str
    Drug-Food  → type="drug_food", severity="high|medium|low", description=str, recommendation=str, source="curated"
"""
import json
import os
import networkx as nx
from typing import Optional

_FOOD_DATA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "drug_food_interactions.json"
)


def load_food_interactions() -> list[dict]:
    """Load curated drug-food interaction dataset."""
    try:
        with open(_FOOD_DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"[graph_engine] Error loading drug-food interactions: {exc}")
        return []


def add_food_interactions(G: nx.Graph, food_interactions: list[dict] | None = None) -> nx.Graph:
    """
    Add food nodes and drug-food edges to the existing NetworkX graph.
    """
    if food_interactions is None:
        food_interactions = load_food_interactions()

    for item in food_interactions:
        drug_name = item.get("drug", "").strip().lower()
        drug_rxcui = str(item.get("drug_rxcui", "")).strip()
        food_key = item.get("food", "").strip().lower()
        food_display = item.get("food_display", food_key.title())
        severity = item.get("severity", "medium")
        description = item.get("description", "")
        recommendation = item.get("recommendation", "")
        source = item.get("source", "curated")

        if not drug_name or not food_key:
            continue

        food_node_id = f"food:{food_key}"

        # Ensure food node exists
        if not G.has_node(food_node_id):
            G.add_node(
                food_node_id,
                type="food",
                name=food_key,
                display=food_display,
            )

        # Connect to drug by RxCUI if node exists or by RxCUI directly
        target_drug_nodes = []
        if drug_rxcui and G.has_node(drug_rxcui):
            target_drug_nodes.append(drug_rxcui)
        elif drug_rxcui:
            # Create the drug node by rxcui if missing
            G.add_node(drug_rxcui, type="drug", name=drug_name, drug_class="")
            target_drug_nodes.append(drug_rxcui)

        # Also find any node with matching drug name
        for node_id, attrs in list(G.nodes(data=True)):
            if attrs.get("type") == "drug" and attrs.get("name", "").lower() == drug_name:
                if node_id not in target_drug_nodes:
                    target_drug_nodes.append(node_id)

        # If still no matching drug node in graph, create a named drug node
        if not target_drug_nodes:
            named_node_id = f"drug:{drug_name}"
            G.add_node(named_node_id, type="drug", name=drug_name, drug_class="")
            target_drug_nodes.append(named_node_id)

        for d_node in target_drug_nodes:
            G.add_edge(
                d_node,
                food_node_id,
                type="drug_food",
                severity=severity,
                description=description,
                recommendation=recommendation,
                food_name=food_key,
                food_display=food_display,
                drug_name=drug_name,
                source=source,
            )

    return G


def build_graph(
    interactions: list[dict],
    drug_meta: dict[str, dict] | None = None,
    include_food: bool = True,
    food_interactions: list[dict] | None = None,
) -> nx.Graph:
    """
    Build a NetworkX undirected graph from a list of interaction dicts
    and optional food interactions.
    """
    G = nx.Graph()
    drug_meta = drug_meta or {}

    for interaction in interactions:
        rxcui_a = str(interaction.get("drug_a_rxcui", ""))
        rxcui_b = str(interaction.get("drug_b_rxcui", ""))
        name_a  = interaction.get("drug_a_name", rxcui_a)
        name_b  = interaction.get("drug_b_name", rxcui_b)

        if not rxcui_a or not rxcui_b:
            continue

        # Add/update drug nodes
        if not G.has_node(rxcui_a):
            G.add_node(
                rxcui_a,
                type="drug",
                name=drug_meta.get(rxcui_a, {}).get("name", name_a),
                drug_class=drug_meta.get(rxcui_a, {}).get("drug_class", ""),
            )
        if not G.has_node(rxcui_b):
            G.add_node(
                rxcui_b,
                type="drug",
                name=drug_meta.get(rxcui_b, {}).get("name", name_b),
                drug_class=drug_meta.get(rxcui_b, {}).get("drug_class", ""),
            )

        # Add interaction edge
        G.add_edge(
            rxcui_a,
            rxcui_b,
            type="drug_drug",
            severity=interaction.get("severity", "low"),
            description=interaction.get("description", ""),
            source=interaction.get("source", "rxnav"),
        )

    if include_food:
        add_food_interactions(G, food_interactions)

    return G


def get_interactions_for_drugs(G: nx.Graph, rxcui_list: list[str]) -> list[dict]:
    """
    Return all drug-drug interaction edges between the given set of RxCUI nodes.
    """
    rxcui_set = {str(r) for r in rxcui_list}
    results = []

    for u, v, data in G.edges(data=True):
        if data.get("type") == "drug_drug" and u in rxcui_set and v in rxcui_set:
            results.append({
                "drug_a_rxcui": u,
                "drug_a_name":  G.nodes[u].get("name", u),
                "drug_b_rxcui": v,
                "drug_b_name":  G.nodes[v].get("name", v),
                "severity":     data.get("severity", "low"),
                "description":  data.get("description", ""),
                "source":       data.get("source", ""),
            })

    # Sort by severity: high → medium → low
    severity_order = {"high": 0, "medium": 1, "low": 2}
    results.sort(key=lambda x: severity_order.get(x["severity"], 3))

    return results


def get_food_interactions_for_drugs(
    G: nx.Graph,
    rxcui_list: list[str],
    drug_names: list[str] | None = None
) -> list[dict]:
    """
    Return all drug-food interaction edges connected to the patient's active drugs.
    """
    rxcui_set = {str(r) for r in rxcui_list if r}
    name_set = {n.strip().lower() for n in (drug_names or []) if n.strip()}
    results = []
    seen = set()

    for u, v, data in G.edges(data=True):
        if data.get("type") != "drug_food":
            continue

        # Determine which node is the drug and which is the food
        drug_node = u if G.nodes[u].get("type") == "drug" else v
        food_node = v if G.nodes[v].get("type") == "food" else u

        drug_node_name = G.nodes[drug_node].get("name", "").lower()
        is_match = (
            drug_node in rxcui_set
            or drug_node_name in name_set
            or any(drug_node_name == name for name in name_set)
        )

        if is_match:
            food_display = data.get("food_display") or G.nodes[food_node].get("display", G.nodes[food_node].get("name", ""))
            pair_key = (drug_node_name, G.nodes[food_node].get("name", ""))
            if pair_key not in seen:
                seen.add(pair_key)
                results.append({
                    "drug_name":      drug_node_name,
                    "drug_rxcui":     drug_node if drug_node.isdigit() else "",
                    "food_name":      G.nodes[food_node].get("name", ""),
                    "food_display":   food_display,
                    "severity":       data.get("severity", "medium"),
                    "description":    data.get("description", ""),
                    "recommendation": data.get("recommendation", ""),
                    "source":         data.get("source", "curated"),
                })

    severity_order = {"high": 0, "medium": 1, "low": 2}
    results.sort(key=lambda x: severity_order.get(x["severity"], 3))
    return results


def get_severity_summary(interactions: list[dict], food_interactions: list[dict] | None = None) -> dict:
    """
    Count interactions by severity level (including food interactions count).
    """
    summary = {"high": 0, "medium": 0, "low": 0, "food_total": 0}
    for ix in interactions:
        sev = ix.get("severity", "low")
        if sev in summary:
            summary[sev] += 1

    if food_interactions:
        summary["food_total"] = len(food_interactions)
        for fix in food_interactions:
            fsev = fix.get("severity", "medium")
            if fsev in summary:
                summary[fsev] += 1

    summary["total"] = summary["high"] + summary["medium"] + summary["low"]
    return summary


def get_graph_json(G: nx.Graph) -> dict:
    """
    Export the graph as node-link JSON for D3.js visualization.
    """
    return nx.node_link_data(G)


def suggest_alternatives(G: nx.Graph, rxcui: str, drug_class: str) -> list[dict]:
    """
    Suggest safer alternative drugs from the same class.
    """
    candidates = []
    for node_id, attrs in G.nodes(data=True):
        if node_id == rxcui:
            continue
        if attrs.get("type") == "drug" and attrs.get("drug_class") == drug_class:
            interaction_count = G.degree(node_id)
            candidates.append({
                "rxcui":             node_id,
                "name":              attrs.get("name", node_id),
                "drug_class":        drug_class,
                "interaction_count": interaction_count,
            })
    candidates.sort(key=lambda x: x["interaction_count"])
    return candidates[:3]
