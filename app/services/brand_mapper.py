"""
app/services/brand_mapper.py

Maps Indian brand names to their generic drug equivalents.

Pipeline:
  1. Exact match (case-insensitive) on brand_to_generic.json
  2. Fuzzy match via RapidFuzz if exact match fails (threshold ≥ 80)
  3. Return original name unchanged if no match found

For combo drugs (generic contains "+"), splits the result into
individual generic components so each can be looked up in RxNav.
"""
import json
import os
from rapidfuzz import process, fuzz

# ── Load the brand mapping once at module import ──────────────────────────────
_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "brand_to_generic.json")

def _load_brand_map() -> dict[str, str]:
    with open(_DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    # Remove the _comment key if present
    return {k: v for k, v in data.items() if not k.startswith("_")}

_BRAND_MAP: dict[str, str] = _load_brand_map()
_BRAND_KEYS: list[str] = list(_BRAND_MAP.keys())
_GENERIC_VALUES: set[str] = {
    part.strip().lower()
    for v in _BRAND_MAP.values()
    for part in v.split("+")
}

# Fuzzy match threshold — below this score we treat the name as-is
_FUZZY_THRESHOLD = 80


def map_brand_to_generic(name: str) -> tuple[str, bool]:
    """
    Map a brand name to its generic equivalent.

    Args:
        name: Drug name as entered by the user (any case).

    Returns:
        (generic_name, was_mapped)
        - generic_name: lowercase generic name, or original name if unmapped
        - was_mapped: True if a brand→generic mapping was applied
    """
    clean = name.strip().lower()

    # If the input is already a known generic name, pass through unmapped
    if clean in _GENERIC_VALUES:
        return clean, False

    # 1. Exact match on brand name
    if clean in _BRAND_MAP:
        return _BRAND_MAP[clean], True

    # 2. Fuzzy match against brand keys
    result = process.extractOne(clean, _BRAND_KEYS, scorer=fuzz.WRatio)
    if result and result[1] >= _FUZZY_THRESHOLD:
        matched_key = result[0]
        mapped_generic = _BRAND_MAP[matched_key]
        if mapped_generic.lower() == clean:
            return clean, False
        return mapped_generic, True

    # 3. No match — return as-is (may still be a valid generic name)
    return clean, False


def split_combo_drug(generic_name: str) -> list[str]:
    """
    Split a combo generic (e.g. "ibuprofen+paracetamol") into components.
    Returns a list with one element if it's not a combo drug.
    """
    return [part.strip() for part in generic_name.split("+")]


def resolve_drug_names(raw_names: list[str]) -> list[dict]:
    """
    Full resolution pipeline for a list of raw drug name strings.

    Args:
        raw_names: list of user-entered drug names

    Returns:
        list of dicts, one per resolved drug component:
        {
          "input":    original string entered by user,
          "generic":  resolved generic name (lowercase),
          "mapped":   True if a brand mapping was applied,
          "is_combo": True if the drug was split into components,
          "component_of": original input string (for combo components)
        }
    """
    resolved = []
    for raw in raw_names:
        if not raw.strip():
            continue
        generic, mapped = map_brand_to_generic(raw)
        components = split_combo_drug(generic)
        is_combo = len(components) > 1

        for component in components:
            resolved.append({
                "input":        raw.strip(),
                "generic":      component,
                "mapped":       mapped,
                "is_combo":     is_combo,
                "component_of": raw.strip() if is_combo else None,
            })

    return resolved
