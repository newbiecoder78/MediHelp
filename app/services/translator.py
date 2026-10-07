"""
app/services/translator.py

Provides human-curated translations in English, Hindi (hi), Tamil (ta), and Telugu (te)
for patient-facing drug-drug and drug-food interaction alerts.

Structured templates ensure clinical accuracy without relying on unpredictable raw machine translation.
"""
import json
import os
from typing import Any

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "alert_translations.json")


def _load_translations() -> dict:
    try:
        with open(_DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"[translator] Error loading alert translations: {exc}")
        return {"ui": {}, "generic_templates": {}, "specific_pairs": {}}


_TRANSLATIONS = _load_translations()


def get_ui_strings(lang: str = "en") -> dict[str, str]:
    """Return UI label dictionary for the given language code."""
    ui = _TRANSLATIONS.get("ui", {})
    return ui.get(lang, ui.get("en", {}))


def _make_drug_pair_key(drug_a: str, drug_b: str) -> str:
    """Create normalized alphabetical pair key e.g. 'aspirin_warfarin' or 'warfarin_aspirin'."""
    a = drug_a.strip().lower()
    b = drug_b.strip().lower()
    return "_".join(sorted([a, b]))


def _make_food_pair_key(drug: str, food: str) -> str:
    """Create key for drug-food pair e.g. 'warfarin_grapefruit'."""
    d = drug.strip().lower()
    f = food.strip().lower()
    return f"{d}_{f}"


def get_drug_interaction_description(
    drug_a: str,
    drug_b: str,
    severity: str,
    original_description: str,
    lang: str = "en"
) -> str:
    """
    Get localized description for a drug-drug interaction.
    1. Check specific curated pair translation
    2. Fallback to generic template for that severity in that language
    3. Fallback to original description
    """
    if lang == "en":
        return original_description

    pair_key = _make_drug_pair_key(drug_a, drug_b)
    specific = _TRANSLATIONS.get("specific_pairs", {}).get(pair_key)

    if specific and lang in specific:
        return specific[lang]

    # Also check direct order without sort
    direct_key = f"{drug_a.strip().lower()}_{drug_b.strip().lower()}"
    specific_direct = _TRANSLATIONS.get("specific_pairs", {}).get(direct_key)
    if specific_direct and lang in specific_direct:
        return specific_direct[lang]

    # Fallback to structured generic template
    sev_templates = _TRANSLATIONS.get("generic_templates", {}).get(severity.lower(), {})
    if lang in sev_templates:
        return sev_templates[lang].format(
            drug_a=drug_a.title(),
            drug_b=drug_b.title(),
            severity=severity.upper()
        )

    return original_description


def get_food_interaction_description(
    drug: str,
    food: str,
    severity: str,
    original_description: str,
    lang: str = "en"
) -> str:
    """Get localized description for a drug-food interaction."""
    if lang == "en":
        return original_description

    food_key = _make_food_pair_key(drug, food)
    specific = _TRANSLATIONS.get("specific_pairs", {}).get(food_key)

    if specific and lang in specific:
        return specific[lang]

    # Fallback template
    food_template_key = f"food_{severity.lower()}"
    sev_templates = _TRANSLATIONS.get("generic_templates", {}).get(food_template_key, {})
    if lang in sev_templates:
        return sev_templates[lang].format(
            drug=drug.title(),
            food=food.title()
        )

    return original_description


def translate_results(result: dict[str, Any], lang: str = "en") -> dict[str, Any]:
    """
    Apply translation transformations to a full results dictionary.
    Updates interaction and food_interaction descriptions and attaches UI strings.
    """
    if not result:
        return result

    translated_result = dict(result)
    translated_result["current_lang"] = lang
    translated_result["ui"] = get_ui_strings(lang)

    # Translate drug-drug interactions
    if "interactions" in translated_result:
        translated_ixs = []
        for ix in translated_result["interactions"]:
            ix_copy = dict(ix)
            ix_copy["description"] = get_drug_interaction_description(
                drug_a=ix.get("drug_a_name", ""),
                drug_b=ix.get("drug_b_name", ""),
                severity=ix.get("severity", "low"),
                original_description=ix.get("description", ""),
                lang=lang
            )
            translated_ixs.append(ix_copy)
        translated_result["interactions"] = translated_ixs

    # Translate food interactions
    if "food_interactions" in translated_result:
        translated_food_ixs = []
        for fix in translated_result["food_interactions"]:
            fix_copy = dict(fix)
            fix_copy["description"] = get_food_interaction_description(
                drug=fix.get("drug_name", fix.get("drug", "")),
                food=fix.get("food_name", fix.get("food", "")),
                severity=fix.get("severity", "medium"),
                original_description=fix.get("description", ""),
                lang=lang
            )
            translated_food_ixs.append(fix_copy)
        translated_result["food_interactions"] = translated_food_ixs

    return translated_result
