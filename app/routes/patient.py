"""
app/routes/patient.py

Patient-facing routes:
  GET  /          → redirect to /patient
  GET  /patient   → drug input form
  POST /patient/check → run interaction check, render results
"""
from flask import Blueprint, render_template, request, redirect, url_for
from app.services.interaction_checker import check_drugs
from app.services.translator import get_ui_strings

patient_bp = Blueprint("patient", __name__)


@patient_bp.route("/")
def index():
    return redirect(url_for("patient.input_form"))


@patient_bp.route("/patient")
def input_form():
    lang = request.args.get("lang", "en")
    ui = get_ui_strings(lang)
    return render_template("patient_input.html", lang=lang, ui=ui)


@patient_bp.route("/patient/check", methods=["GET", "POST"])
def check():
    if request.method == "POST":
        raw_input = request.form.get("drugs", "").strip()
        lang = request.form.get("lang", "en")
    else:
        raw_input = request.args.get("drugs", "").strip()
        lang = request.args.get("lang", "en")

    if not raw_input:
        return render_template(
            "patient_input.html",
            error="Please enter at least one medicine name.",
            lang=lang,
            ui=get_ui_strings(lang),
        )

    result = check_drugs(raw_input, lang=lang)
    return render_template("patient_results.html", result=result, lang=lang)

