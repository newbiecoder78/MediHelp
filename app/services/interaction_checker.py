"""
app/services/interaction_checker.py

Orchestrates the full pipeline from raw drug name input to structured results.

Pipeline:
  1. brand_mapper  → resolve brand names to generics, split combos
  2. rxnav         → resolve each generic to RxCUI
  3. rxnav         → fetch drug-drug interactions for the RxCUI set
  4. graph_engine  → build NetworkX graph, query drug-drug and drug-food interactions
  5. translator    → localize alerts to selected language (EN / HI / TA / TE)
  6. Return structured result dict
"""
from .brand_mapper import resolve_drug_names
from .rxnav import get_rxcui, get_interactions
from .graph_engine import (
    build_graph,
    get_interactions_for_drugs,
    get_food_interactions_for_drugs,
    get_severity_summary,
    get_graph_json,
)
from .translator import translate_results, get_ui_strings


def parse_drug_input(raw_input: str) -> list[str]:
    """
    Parse a comma- or newline-separated drug name string into a clean list.
    """
    separators = [",", "\n", ";", "\r\n"]
    parts = [raw_input]
    for sep in separators:
        new_parts = []
        for part in parts:
            new_parts.extend(part.split(sep))
        parts = new_parts

    return [p.strip() for p in parts if p.strip()]


def check_drugs(raw_input: str, lang: str = "en") -> dict:
    """
    Main orchestrator: takes raw user input and returns a full interaction report
    including both drug-drug and drug-food interactions in the specified language.
    """
    errors = []

    # ── Step 1: Parse input ──────────────────────────────────────────────────
    input_list = parse_drug_input(raw_input)
    if not input_list:
        empty_res = {
            "input_drugs":       [],
            "resolved_drugs":    [],
            "interactions":      [],
            "food_interactions": [],
            "severity_summary":  {"high": 0, "medium": 0, "low": 0, "food_total": 0, "total": 0},
            "graph_json":        {},
            "unresolved_drugs":  [],
            "errors":            ["No drug names were entered."],
            "current_lang":      lang,
            "ui":                get_ui_strings(lang),
        }
        return empty_res

    # ── Step 2: Brand mapping → generic names ────────────────────────────────
    resolved_metas = resolve_drug_names(input_list)

    # ── Step 3: RxCUI resolution ─────────────────────────────────────────────
    resolved_drugs = []
    rxcui_to_meta = {}  # rxcui → resolved drug dict
    unresolved = []
    generic_names = []

    for meta in resolved_metas:
        generic = meta["generic"]
        generic_names.append(generic)
        rxcui_result = get_rxcui(generic)

        drug_entry = {
            "input":    meta["input"],
            "generic":  generic,
            "rxcui":    None,
            "mapped":   meta["mapped"],
            "resolved": False,
            "is_combo": meta["is_combo"],
        }

        if rxcui_result:
            drug_entry["rxcui"]    = str(rxcui_result["rxcui"])
            drug_entry["resolved"] = True
            rxcui_to_meta[str(rxcui_result["rxcui"])] = drug_entry
        else:
            unresolved.append(generic)
            errors.append(
                f"Could not verify '{meta['input']}' ({generic}) — "
                "it may not be in the RxNorm database. Please check the spelling."
            )

        resolved_drugs.append(drug_entry)

    # ── Step 4: Fetch drug-drug interactions ──────────────────────────────────
    rxcui_list = [d["rxcui"] for d in resolved_drugs if d["rxcui"]]
    raw_interactions = []

    if len(rxcui_list) >= 2:
        raw_interactions = get_interactions(rxcui_list)
    elif len(rxcui_list) == 1:
        # Single drug won't have drug-drug interactions, but can still have drug-food interactions!
        pass

    # ── Step 5: Build knowledge graph + query interactions ────────────────────
    drug_meta_dict = {
        rxcui: {"name": meta["generic"], "drug_class": ""}
        for rxcui, meta in rxcui_to_meta.items()
    }
    # Also add non-rxcui generic names so food interactions can attach
    for drug in resolved_drugs:
        if drug["generic"]:
            drug_meta_dict[drug["generic"]] = {"name": drug["generic"], "drug_class": ""}

    G = build_graph(raw_interactions, drug_meta=drug_meta_dict, include_food=True)

    interactions = get_interactions_for_drugs(G, rxcui_list)
    food_interactions = get_food_interactions_for_drugs(G, rxcui_list, drug_names=generic_names)

    severity_summary = get_severity_summary(interactions, food_interactions)

    graph_json = get_graph_json(G) if G.number_of_nodes() > 0 else {}

    raw_result = {
        "raw_input":         raw_input,
        "input_drugs":       input_list,
        "resolved_drugs":    resolved_drugs,
        "interactions":      interactions,
        "food_interactions": food_interactions,
        "severity_summary":  severity_summary,
        "graph_json":        graph_json,
        "unresolved_drugs":  unresolved,
        "errors":            errors,
    }

    # ── Step 6: Apply translation ─────────────────────────────────────────────
    return translate_results(raw_result, lang=lang)
