"""
scripts/seed_supabase.py

One-time script to populate the Supabase `brand_mappings` table from
the local brand_to_generic.json file.

Run once after creating Supabase tables:
    python scripts/seed_supabase.py

Requires: SUPABASE_URL and SUPABASE_KEY in .env
"""
import json
import os
import sys

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.config import get_supabase_client

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "app", "data", "brand_to_generic.json")


def seed():
    db = get_supabase_client()
    if not db:
        print("❌ Could not connect to Supabase. Check your .env file.")
        sys.exit(1)

    with open(DATA_PATH, encoding="utf-8") as f:
        brand_map = json.load(f)

    rows = [
        {
            "brand_name":   brand.lower(),
            "generic_name": generic,
            "rxcui":        None,
            "region":       "IN",
        }
        for brand, generic in brand_map.items()
        if not brand.startswith("_")  # skip _comment key
    ]

    print(f"Seeding {len(rows)} brand mappings into Supabase...")

    # Upsert in batches of 50
    batch_size = 50
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        try:
            db.table("brand_mappings").upsert(
                batch,
                on_conflict="brand_name,region"
            ).execute()
            print(f"  ✅ Batch {i // batch_size + 1}: {len(batch)} rows upserted")
        except Exception as exc:
            print(f"  ❌ Batch {i // batch_size + 1} failed: {exc}")

    print("Done.")


if __name__ == "__main__":
    seed()
