"""
app/routes/audio.py

Voice output route for patient-facing alerts.
Streams pre-cached MP3 audio files or dynamically generates speech via gTTS
in English, Hindi (hi), Tamil (ta), and Telugu (te).
"""
import hashlib
import io
import json
import os
from flask import Blueprint, request, send_file, jsonify, current_app
from gtts import gTTS

audio_bp = Blueprint("audio", __name__)

_AUDIO_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "audio")
os.makedirs(_AUDIO_DIR, exist_ok=True)

_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "alert_translations.json")

# Valid gTTS language mappings
_SUPPORTED_LANGS = {
    "en": "en",
    "hi": "hi",
    "ta": "ta",
    "te": "te",
}


def _get_hash_filename(text: str, lang: str) -> str:
    """Generate a deterministic filename from text content and language."""
    clean_text = text.strip().lower()
    h = hashlib.md5(f"{clean_text}_{lang}".encode("utf-8")).hexdigest()[:16]
    return f"tts_{lang}_{h}.mp3"


@audio_bp.route("/patient/audio/<alert_key>/<lang>", methods=["GET"])
def get_patient_alert_audio(alert_key: str, lang: str):
    """
    Serve pre-cached or dynamically synthesized MP3 audio for a specific alert key.
    URL Path: /patient/audio/<alert_key>/<lang>
    """
    clean_key = alert_key.strip().lower()
    clean_lang = lang.strip().lower()
    gtts_lang = _SUPPORTED_LANGS.get(clean_lang, "en")

    # 1. Look for pre-cached alert file
    key_filename = f"alert_{clean_key}_{clean_lang}.mp3"
    key_filepath = os.path.join(_AUDIO_DIR, key_filename)
    if os.path.exists(key_filepath):
        return send_file(key_filepath, mimetype="audio/mpeg", as_attachment=False)

    # 2. Look up translation text from alert_translations.json if available
    text_to_speak = ""
    try:
        if os.path.exists(_DATA_PATH):
            with open(_DATA_PATH, encoding="utf-8") as f:
                translations = json.load(f)
            specific_pairs = translations.get("specific_pairs", {})
            if clean_key in specific_pairs:
                text_to_speak = specific_pairs[clean_key].get(clean_lang) or specific_pairs[clean_key].get("en", "")
    except Exception:
        pass

    if not text_to_speak:
        # Check query string text fallback
        text_to_speak = request.args.get("text", "").strip()

    if not text_to_speak:
        return jsonify({"error": f"No audio or translation available for alert key '{clean_key}'."}), 404

    # 3. Dynamic gTTS synthesis
    try:
        tts = gTTS(text=text_to_speak, lang=gtts_lang, slow=False)
        tts.save(key_filepath)
        return send_file(key_filepath, mimetype="audio/mpeg", as_attachment=False)
    except Exception as exc:
        return jsonify({"error": f"Audio synthesis failed: {str(exc)}"}), 500


@audio_bp.route("/audio/tts", methods=["GET"])
def get_tts_audio():
    """
    Generate or retrieve cached TTS audio stream.
    Query params:
      - text: string to speak
      - lang: 'en', 'hi', 'ta', 'te'
      - key: optional pair key (e.g. 'warfarin_aspirin')
    """
    text = request.args.get("text", "").strip()
    lang = request.args.get("lang", "en").strip().lower()
    key = request.args.get("key", "").strip().lower()

    if not text and not key:
        return jsonify({"error": "No text provided"}), 400

    gtts_lang = _SUPPORTED_LANGS.get(lang, "en")

    # 1. Check if specific pair-key cached file exists
    if key:
        key_filename = f"alert_{key}_{lang}.mp3"
        key_filepath = os.path.join(_AUDIO_DIR, key_filename)
        if os.path.exists(key_filepath):
            return send_file(key_filepath, mimetype="audio/mpeg", as_attachment=False)

    # 2. Check if content hash cached file exists
    hash_filename = _get_hash_filename(text, lang)
    hash_filepath = os.path.join(_AUDIO_DIR, hash_filename)
    if os.path.exists(hash_filepath):
        return send_file(hash_filepath, mimetype="audio/mpeg", as_attachment=False)

    # 3. Dynamic gTTS generation + disk cache
    try:
        tts = gTTS(text=text, lang=gtts_lang, slow=False)
        tts.save(hash_filepath)
        return send_file(hash_filepath, mimetype="audio/mpeg", as_attachment=False)
    except Exception as exc:
        print(f"[audio_route] Live gTTS generation failed: {exc}")
        return jsonify({"error": f"Audio synthesis unavailable: {str(exc)}"}), 500


@audio_bp.route("/audio/file/<filename>", methods=["GET"])
def get_cached_file(filename: str):
    """Directly serve a pre-cached audio file from static/audio directory."""
    safe_filename = os.path.basename(filename)
    filepath = os.path.join(_AUDIO_DIR, safe_filename)
    if os.path.exists(filepath):
        return send_file(filepath, mimetype="audio/mpeg", as_attachment=False)
    return jsonify({"error": "Audio file not found"}), 404
