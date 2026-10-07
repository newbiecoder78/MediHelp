"""
app/config.py — Central application configuration.

All environment variables and application constants are loaded here.
No external database is used; data is persisted in local JSON stores.
"""
import os
from dotenv import load_dotenv

load_dotenv()  # reads .env file in project root


class Config:
    # ── Flask ────────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")
    DEBUG = os.environ.get("FLASK_ENV", "production") == "development"

    # ── RxNav ────────────────────────────────────────────────────────────────
    RXNAV_BASE_URL = os.environ.get(
        "RXNAV_BASE_URL", "https://rxnav.nlm.nih.gov/REST"
    )
    RXNAV_TIMEOUT_SECONDS = int(os.environ.get("RXNAV_TIMEOUT_SECONDS", "5"))

    # ── OCR Configuration ────────────────────────────────────────────────────
    OCR_FUZZY_THRESHOLD = int(os.environ.get("OCR_FUZZY_THRESHOLD", "80"))
