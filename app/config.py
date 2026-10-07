"""
app/config.py — loads environment variables and initialises the Supabase client.

All configuration lives here. Other modules import `current_app.config`
or import `supabase_client` directly from this module.
"""
import os
from dotenv import load_dotenv

load_dotenv()  # reads .env file in project root


class Config:
    # ── Flask ────────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")
    DEBUG = os.environ.get("FLASK_ENV", "production") == "development"

    # ── Supabase ─────────────────────────────────────────────────────────────
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

    # ── RxNav ────────────────────────────────────────────────────────────────
    RXNAV_BASE_URL = os.environ.get(
        "RXNAV_BASE_URL", "https://rxnav.nlm.nih.gov/REST"
    )
    RXNAV_TIMEOUT = int(os.environ.get("RXNAV_TIMEOUT_SECONDS", "5"))


# ── Supabase client (module-level singleton) ─────────────────────────────────
# Imported directly by services that need DB access.
# Returns None if env vars are missing (graceful degradation in dev).
def get_supabase_client():
    """Return a Supabase client, or None if credentials are missing."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as exc:
        print(f"[config] Could not create Supabase client: {exc}")
        return None


supabase_client = get_supabase_client()
