"""
app/services/rxnav.py

RxNav/RxNorm API client with Supabase caching and multi-layer fallback.

Fallback order for every operation:
  L1 — Supabase cache (always checked first)
  L2 — Live RxNav API call (timeout = RXNAV_TIMEOUT seconds)
  L3 — Local fallback_interactions.json (for interaction lookups)
  L4 — Graceful None/empty return (caller shows "could not verify" message)
"""
import json
import os
import requests
from datetime import datetime, timezone
from app.config import Config

# ── Config ────────────────────────────────────────────────────────────────────
_RXNAV_BASE = getattr(Config, "RXNAV_BASE_URL", os.environ.get("RXNAV_BASE_URL", "https://rxnav.nlm.nih.gov/REST"))
_TIMEOUT = getattr(Config, "RXNAV_TIMEOUT_SECONDS", int(os.environ.get("RXNAV_TIMEOUT_SECONDS", "5")))
_CACHE_MAX_AGE_HOURS = 24  # re-fetch from API after this many hours

# ── Fallback data path ────────────────────────────────────────────────────────
_FALLBACK_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "fallback_interactions.json"
)

def _load_fallback() -> list[dict]:
    try:
        with open(_FALLBACK_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return [d for d in data if d.get("drug_a_rxcui") and d.get("drug_b_rxcui")]
    except Exception:
        return []


# ── Database helper (Graceful offline/local mode) ─────────────────────────────
def _get_db():
    """Return database client if available, else None."""
    return getattr(Config, "supabase_client", None)


def _cache_is_fresh(cached_at_str: str) -> bool:
    """Return True if the cached_at timestamp is within the max cache age."""
    try:
        cached_at = datetime.fromisoformat(cached_at_str.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
        return age_hours < _CACHE_MAX_AGE_HOURS
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# RxCUI lookup
# ─────────────────────────────────────────────────────────────────────────────

def get_rxcui(drug_name: str) -> dict | None:
    """
    Resolve a generic drug name to its RxCUI code.

    Returns:
        {
          "rxcui":   "1191",
          "name":    "aspirin",
          "source":  "cache" | "api" | None
        }
        or None if the drug could not be resolved.
    """
    name_lower = drug_name.strip().lower()

    # ── L1: Supabase cache ────────────────────────────────────────────────────
    db = _get_db()
    if db:
        try:
            row = (
                db.table("brand_mappings")
                .select("rxcui, generic_name")
                .eq("brand_name", name_lower)
                .not_.is_("rxcui", "null")
                .limit(1)
                .execute()
            )
            if row.data:
                return {
                    "rxcui":  row.data[0]["rxcui"],
                    "name":   row.data[0]["generic_name"],
                    "source": "cache",
                }
        except Exception as exc:
            print(f"[rxnav] Supabase rxcui lookup failed: {exc}")

    # ── L2: RxNav API ─────────────────────────────────────────────────────────
    try:
        # First try exact match
        url = f"{_RXNAV_BASE}/rxcui.json"
        resp = requests.get(url, params={"name": drug_name, "search": "1"}, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        rxcui = (
            data.get("idGroup", {}).get("rxnormId", [None])[0]
        )

        # If exact match fails, try approximate
        if not rxcui:
            url2 = f"{_RXNAV_BASE}/approximateTerm.json"
            resp2 = requests.get(url2, params={"term": drug_name, "maxEntries": "1"}, timeout=_TIMEOUT)
            resp2.raise_for_status()
            data2 = resp2.json()
            candidates = data2.get("approximateGroup", {}).get("candidate", [])
            if candidates:
                rxcui = candidates[0].get("rxcui")

        if rxcui:
            result = {"rxcui": str(rxcui), "name": name_lower, "source": "api"}

            # Cache in Supabase brand_mappings table
            if db:
                try:
                    db.table("brand_mappings").upsert(
                        {
                            "brand_name":   name_lower,
                            "generic_name": name_lower,
                            "rxcui":        str(rxcui),
                            "region":       "IN",
                        },
                        on_conflict="brand_name,region",
                    ).execute()
                except Exception as exc:
                    print(f"[rxnav] Supabase rxcui cache write failed: {exc}")

            return result

    except requests.exceptions.Timeout:
        print(f"[rxnav] Timeout resolving RxCUI for '{drug_name}'")
    except Exception as exc:
        print(f"[rxnav] RxCUI lookup error for '{drug_name}': {exc}")

    # ── L3: Local Curated RxCUI Fallback ──────────────────────────────────────
    COMMON_RXCUIS = {
        "paracetamol": "161",
        "acetaminophen": "161",
        "aspirin": "1191",
        "ibuprofen": "5640",
        "warfarin": "11289",
        "metformin": "235743",
        "atorvastatin": "83367",
        "rosuvastatin": "301542",
        "simvastatin": "36567",
        "lovastatin": "6472",
        "fluvastatin": "41127",
        "amlodipine": "17767",
        "lisinopril": "29046",
        "ciprofloxacin": "2551",
        "metronidazole": "6922",
        "levothyroxine": "10582",
        "telmisartan": "31676",
        "pantoprazole": "40790",
        "omeprazole": "7646",
        "amoxicillin": "723",
        "azithromycin": "18631",
    }
    if name_lower in COMMON_RXCUIS:
        return {"rxcui": COMMON_RXCUIS[name_lower], "name": name_lower, "source": "fallback"}

    # ── L4: Could not resolve ─────────────────────────────────────────────────
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Drug-drug interaction lookup
# ─────────────────────────────────────────────────────────────────────────────

def get_interactions(rxcui_list: list[str]) -> list[dict]:
    """
    Fetch drug-drug interactions for a list of RxCUI codes.

    Returns list of interaction dicts:
        {
          "drug_a_rxcui":  str,
          "drug_a_name":   str,
          "drug_b_rxcui":  str,
          "drug_b_name":   str,
          "severity":      "high" | "medium" | "low",
          "description":   str,
          "source":        str
        }
    """
    if len(rxcui_list) < 2:
        return []

    # ── L1: Supabase cache ────────────────────────────────────────────────────
    db = _get_db()
    cached_results = []
    uncached_pairs = set()

    if db:
        try:
            rows = (
                db.table("drug_interactions")
                .select("*")
                .in_("drug_a_rxcui", rxcui_list)
                .in_("drug_b_rxcui", rxcui_list)
                .execute()
            )
            for row in rows.data:
                if _cache_is_fresh(row.get("cached_at", "")):
                    cached_results.append({
                        "drug_a_rxcui": row["drug_a_rxcui"],
                        "drug_a_name":  row["drug_a_name"],
                        "drug_b_rxcui": row["drug_b_rxcui"],
                        "drug_b_name":  row["drug_b_name"],
                        "severity":     row["severity"],
                        "description":  row["description"],
                        "source":       row.get("source", "rxnav"),
                    })
        except Exception as exc:
            print(f"[rxnav] Supabase interaction lookup failed: {exc}")

    # If we got fresh cache hits, return them
    if cached_results:
        return cached_results

    # ── L2: RxNav API ─────────────────────────────────────────────────────────
    try:
        rxcui_str = "+".join(rxcui_list)
        url = f"{_RXNAV_BASE}/interaction/list.json"
        resp = requests.get(url, params={"rxcuis": rxcui_str}, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        interactions = []
        full_interaction_groups = data.get("fullInteractionTypeGroup", []) or []

        for group in full_interaction_groups:
            for full_type in group.get("fullInteractionType", []):
                for pair in full_type.get("interactionPair", []):
                    concepts = pair.get("interactionConcept", [])
                    if len(concepts) < 2:
                        continue

                    drug_a = concepts[0].get("minConceptItem", {})
                    drug_b = concepts[1].get("minConceptItem", {})
                    description = pair.get("description", "")
                    severity_raw = pair.get("severity", "").lower()

                    # Map RxNav severity strings to our schema
                    if "high" in severity_raw or "contraindicated" in severity_raw:
                        severity = "high"
                    elif "moderate" in severity_raw or "medium" in severity_raw:
                        severity = "medium"
                    else:
                        severity = "low"

                    interaction = {
                        "drug_a_rxcui": drug_a.get("rxcui", ""),
                        "drug_a_name":  drug_a.get("name", "").lower(),
                        "drug_b_rxcui": drug_b.get("rxcui", ""),
                        "drug_b_name":  drug_b.get("name", "").lower(),
                        "severity":     severity,
                        "description":  description,
                        "source":       "rxnav",
                    }
                    interactions.append(interaction)

                    # Cache in Supabase
                    if db:
                        try:
                            db.table("drug_interactions").upsert(
                                {
                                    **interaction,
                                    "cached_at": datetime.now(timezone.utc).isoformat(),
                                },
                                on_conflict="drug_a_rxcui,drug_b_rxcui",
                            ).execute()
                        except Exception as exc:
                            print(f"[rxnav] Supabase interaction cache write failed: {exc}")

        return interactions

    except requests.exceptions.Timeout:
        print(f"[rxnav] Timeout fetching interactions for {rxcui_list}")
    except Exception as exc:
        print(f"[rxnav] Interaction lookup error: {exc}")

    # ── L3: Local fallback JSON ───────────────────────────────────────────────
    print("[rxnav] Using local fallback interactions data")
    fallback = _load_fallback()
    rxcui_set = set(rxcui_list)
    results = []
    seen_pairs = set()

    for f in fallback:
        a = f.get("drug_a_rxcui")
        b = f.get("drug_b_rxcui")
        if a in rxcui_set and b in rxcui_set:
            pair_key = tuple(sorted([f.get("drug_a_name", a), f.get("drug_b_name", b)]))
            if pair_key not in seen_pairs:
                seen_pairs.add(pair_key)
                results.append(f)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Drug properties (for clinician decision support)
# ─────────────────────────────────────────────────────────────────────────────

def get_drug_properties(rxcui: str) -> dict:
    """
    Fetch drug properties (name, drug class) from RxNav.
    Returns a dict with keys: name, drug_class, rxcui.
    Returns an empty dict on failure.
    """
    try:
        url = f"{_RXNAV_BASE}/rxcui/{rxcui}/properties.json"
        resp = requests.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        props = resp.json().get("properties", {})
        return {
            "rxcui":      rxcui,
            "name":       props.get("name", "").lower(),
            "drug_class": props.get("synonym", ""),
        }
    except Exception:
        return {}
