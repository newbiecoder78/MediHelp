"""
scripts/precache_audio.py

Pre-generates and caches audio files for all curated drug-drug and drug-food
interaction alerts across English (en), Hindi (hi), Tamil (ta), and Telugu (te).

Run once before demo/judging to ensure zero-latency offline audio playback:
    python scripts/precache_audio.py
"""
import hashlib
import json
import os
import sys
import time

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Ensure UTF-8 output on Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from gtts import gTTS

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "app", "data", "alert_translations.json")
FOOD_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "app", "data", "drug_food_interactions.json")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "static", "audio")


def _get_hash_filename(text: str, lang: str) -> str:
    clean_text = text.strip().lower()
    h = hashlib.md5(f"{clean_text}_{lang}".encode("utf-8")).hexdigest()[:16]
    return f"tts_{lang}_{h}.mp3"


def precache():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"🎙️  Pre-caching multilingual alert audio to: {OUTPUT_DIR}\n")

    with open(DATA_PATH, encoding="utf-8") as f:
        translations = json.load(f)

    specific_pairs = translations.get("specific_pairs", {})
    languages = ["en", "hi", "ta", "te"]

    total_generated = 0
    total_skipped = 0

    # 1. Cache specific curated drug-drug & drug-food pairs
    print(f"--- 1. Caching {len(specific_pairs)} Specific Alert Pairs ---")
    for pair_key, lang_dict in specific_pairs.items():
        for lang in languages:
            text = lang_dict.get(lang, "").strip()
            if not text:
                continue

            pair_filename = f"alert_{pair_key}_{lang}.mp3"
            pair_path = os.path.join(OUTPUT_DIR, pair_filename)

            hash_filename = _get_hash_filename(text, lang)
            hash_path = os.path.join(OUTPUT_DIR, hash_filename)

            if os.path.exists(pair_path) and os.path.exists(hash_path):
                total_skipped += 1
                continue

            try:
                tts = gTTS(text=text, lang=lang, slow=False)
                # Save primary pair file
                tts.save(pair_path)
                # Also save hash file if distinct
                if not os.path.exists(hash_path):
                    with open(pair_path, "rb") as f_in, open(hash_path, "wb") as f_out:
                        f_out.write(f_in.read())

                total_generated += 1
                print(f"  ✅ Cached [{lang.upper()}] {pair_key}")
                # Brief sleep to respect API rate limits
                time.sleep(0.3)
            except Exception as exc:
                print(f"  ❌ Error caching [{lang.upper()}] {pair_key}: {exc}")

    # 2. Cache sample generic template statements
    generic_templates = translations.get("generic_templates", {})
    print(f"\n--- 2. Caching Generic Risk Alert Templates ---")
    sample_replacements = [
        {"drug_a": "Warfarin", "drug_b": "Aspirin", "severity": "HIGH", "drug": "Warfarin", "food": "Grapefruit"},
        {"drug_a": "Atorvastatin", "drug_b": "Metformin", "severity": "MEDIUM", "drug": "Ciprofloxacin", "food": "Dairy"},
    ]

    for temp_key, lang_dict in generic_templates.items():
        for lang in languages:
            raw_temp = lang_dict.get(lang, "").strip()
            if not raw_temp:
                continue
            for sample in sample_replacements:
                try:
                    formatted_text = raw_temp.format(**sample)
                except Exception:
                    continue

                hash_filename = _get_hash_filename(formatted_text, lang)
                hash_path = os.path.join(OUTPUT_DIR, hash_filename)

                if os.path.exists(hash_path):
                    total_skipped += 1
                    continue

                try:
                    tts = gTTS(text=formatted_text, lang=lang, slow=False)
                    tts.save(hash_path)
                    total_generated += 1
                    print(f"  ✅ Cached generic template [{lang.upper()}] ({temp_key})")
                    time.sleep(0.3)
                except Exception as exc:
                    print(f"  ❌ Error caching generic [{lang.upper()}]: {exc}")

    print(f"\n✨ Pre-caching complete!")
    print(f"   Newly generated audio files: {total_generated}")
    print(f"   Existing files in cache:     {total_skipped}")
    print(f"   Total MP3 files in audio/:   {len(os.listdir(OUTPUT_DIR))}")


if __name__ == "__main__":
    precache()
