"""
scripts/warm_graph.py

Pre-demo script: queries RxNav for every drug on your sample prescriptions
and caches all results in Supabase + updates fallback_interactions.json.

Run 30 minutes before judging:
    python scripts/warm_graph.py

After running, the app can survive complete internet outage during the demo.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv()

# ── Edit this list to match your demo prescription drugs ──────────────────────
DEMO_DRUGS = [
    "warfarin", "aspirin", "paracetamol", "ibuprofen",
    "metformin", "atorvastatin", "amlodipine", "lisinopril",
    "omeprazole", "pantoprazole", "metronidazole", "ciprofloxacin",
    "azithromycin", "amoxicillin", "telmisartan", "levothyroxine",
]

FALLBACK_PATH = os.path.join(
    os.path.dirname(__file__), "..", "app", "data", "fallback_interactions.json"
)


def warm():
    from app.services.rxnav import get_rxcui, get_interactions

    print("🔥 Warming cache for demo drugs...")

    # Step 1: Resolve all RxCUIs
    rxcui_map = {}
    for drug in DEMO_DRUGS:
        result = get_rxcui(drug)
        if result:
            rxcui_map[drug] = result["rxcui"]
            print(f"  ✅ {drug} → RxCUI {result['rxcui']} [{result['source']}]")
        else:
            print(f"  ⚠️  {drug} → could not resolve")

    # Step 2: Fetch all pairwise interactions
    rxcui_list = list(rxcui_map.values())
    print(f"\nFetching interactions for {len(rxcui_list)} drugs...")
    interactions = get_interactions(rxcui_list)
    print(f"  ✅ Found {len(interactions)} interactions")

    # Step 3: Update local fallback JSON (append new, skip duplicates)
    existing = []
    if os.path.exists(FALLBACK_PATH):
        with open(FALLBACK_PATH, encoding="utf-8") as f:
            existing = json.load(f)

    existing_keys = {
        (r.get("drug_a_rxcui"), r.get("drug_b_rxcui"))
        for r in existing if not r.get("_comment")
    }

    new_entries = [
        ix for ix in interactions
        if (ix.get("drug_a_rxcui"), ix.get("drug_b_rxcui")) not in existing_keys
        and (ix.get("drug_b_rxcui"), ix.get("drug_a_rxcui")) not in existing_keys
    ]

    updated = existing + new_entries
    with open(FALLBACK_PATH, "w", encoding="utf-8") as f:
        json.dump(updated, f, indent=2)

    print(f"\n  ✅ Added {len(new_entries)} new entries to fallback_interactions.json")
    print(f"  Total fallback entries: {len(updated)}")
    print("\n🎯 Cache is warm. The demo can now survive without internet.")


if __name__ == "__main__":
    warm()
