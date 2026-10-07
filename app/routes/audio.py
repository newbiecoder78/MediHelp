"""
app/routes/audio.py

Voice output route for patient-facing alerts.
Streams pre-cached MP3 audio files or dynamically generates speech via gTTS
in English, Hindi (hi), Tamil (ta), and Telugu (te).
"""
import hashlib
import io
import os
from flask import Blueprint, request, send_file, jsonify, current_app
from gtts import gTTS

audio_bp = Blueprint("audio", __name__)

_AUDIO_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "audio")
os.makedirs(_AUDIO_DIR, exist_ok=True)

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
        # In case of network error, return 500
        return jsonify({"error": f"Audio synthesis unavailable: {str(exc)}"}), 500


@audio_bp.route("/audio/file/<filename>", methods=["GET"])
def get_cached_file(filename: str):
    """Directly serve a pre-cached audio file from static/audio directory."""
    safe_filename = os.path.basename(filename)
    filepath = os.path.join(_AUDIO_DIR, safe_filename)
    if os.path.exists(filepath):
        return send_file(filepath, mimetype="audio/mpeg", as_attachment=False)
    return jsonify({"error": "Audio file not found"}), 404
