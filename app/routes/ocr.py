"""
app/routes/ocr.py

OCR prescription upload route.
Accepts uploaded printed prescription images, runs Tesseract OCR + text cleaning
+ RapidFuzz matching, and returns structured candidate medicines with confidence scores.
"""
from flask import Blueprint, request, jsonify, render_template
from app.services.ocr_engine import process_prescription_image

ocr_bp = Blueprint("ocr", __name__)


@ocr_bp.route("/ocr/upload", methods=["POST"])
def upload_ocr():
    """
    Handle prescription image upload via AJAX.
    Returns JSON of extracted drugs with confidence metrics.
    """
    if "image" not in request.files and "prescription_image" not in request.files:
        return jsonify({"status": "error", "message": "No prescription image file provided."}), 400

    file = request.files.get("image") or request.files.get("prescription_image")
    if not file or file.filename == "":
        return jsonify({"status": "error", "message": "No file selected."}), 400

    try:
        image_bytes = file.read()
        ocr_result = process_prescription_image(image_bytes)

        return jsonify({
            "status":        "ok",
            "raw_text":      ocr_result["raw_text"],
            "candidates":    ocr_result["candidates"],
            "matched_drugs": ocr_result["matched_drugs"],
            "total_found":   len(ocr_result["matched_drugs"]),
        }), 200

    except Exception as exc:
        print(f"[ocr_route] Error processing image: {exc}")
        return jsonify({
            "status":  "error",
            "message": f"Failed to process image: {str(exc)}",
        }), 500
