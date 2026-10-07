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
    """Return UI label dictionary for the given language code with English fallback."""
    ui = _TRANSLATIONS.get("ui", {})
    en_ui = ui.get("en", {})
    lang_ui = ui.get(lang, en_ui)
    # Merge on top of English so missing keys fall back to English
    merged = dict(en_ui)
    merged.update(lang_ui)
    return merged


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
    Get localized description for a drug-drug interaction with fallback chain:
    1. Specific curated pair in requested language
    2. Generic template in requested language
    3. Specific curated pair in English ('en')
    4. Generic template in English ('en')
    5. Original description
    """
    pair_key = _make_drug_pair_key(drug_a, drug_b)
    direct_key = f"{drug_a.strip().lower()}_{drug_b.strip().lower()}"
    specific = _TRANSLATIONS.get("specific_pairs", {}).get(pair_key) or _TRANSLATIONS.get("specific_pairs", {}).get(direct_key)

    if lang == "en":
        if specific and "en" in specific:
            return specific["en"]
        return original_description

    # 1. Target language specific pair
    if specific and lang in specific and specific[lang]:
        return specific[lang]

    # 2. Target language generic template
    sev_templates = _TRANSLATIONS.get("generic_templates", {}).get(severity.lower(), {})
    if lang in sev_templates and sev_templates[lang]:
        try:
            return sev_templates[lang].format(
                drug_a=drug_a.title(),
                drug_b=drug_b.title(),
                severity=severity.upper()
            )
        except Exception:
            pass

    # 3. English specific pair fallback
    if specific and "en" in specific and specific["en"]:
        return specific["en"]

    # 4. English generic template fallback
    if "en" in sev_templates and sev_templates["en"]:
        try:
            return sev_templates["en"].format(
                drug_a=drug_a.title(),
                drug_b=drug_b.title(),
                severity=severity.upper()
            )
        except Exception:
            pass

    # 5. Original description
    return original_description or f"Interaction between {drug_a.title()} and {drug_b.title()} ({severity.upper()} risk)."


def get_food_interaction_description(
    drug: str,
    food: str,
    severity: str,
    original_description: str,
    lang: str = "en"
) -> str:
    """
    Get localized description for a drug-food interaction with fallback chain:
    1. Specific curated pair in requested language
    2. Generic food template in requested language
    3. Specific curated pair in English ('en')
    4. Generic food template in English ('en')
    5. Original description
    """
    food_key = _make_food_pair_key(drug, food)
    specific = _TRANSLATIONS.get("specific_pairs", {}).get(food_key)

    if lang == "en":
        if specific and "en" in specific:
            return specific["en"]
        return original_description

    # 1. Target language specific pair
    if specific and lang in specific and specific[lang]:
        return specific[lang]

    # 2. Target language generic template
    food_template_key = f"food_{severity.lower()}"
    sev_templates = _TRANSLATIONS.get("generic_templates", {}).get(food_template_key, {})
    if lang in sev_templates and sev_templates[lang]:
        try:
            return sev_templates[lang].format(
                drug=drug.title(),
                food=food.title()
            )
        except Exception:
            pass

    # 3. English specific pair fallback
    if specific and "en" in specific and specific["en"]:
        return specific["en"]

    # 4. English generic template fallback
    if "en" in sev_templates and sev_templates["en"]:
        try:
            return sev_templates["en"].format(
                drug=drug.title(),
                food=food.title()
            )
        except Exception:
            pass

    # 5. Original description
    return original_description or f"Dietary precaution with {drug.title()} and {food.title()}."


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
