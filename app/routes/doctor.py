"""
app/routes/doctor.py

Clinician / Doctor-facing decision support view.
Displays structured clinical interaction matrices, RxNorm ontological metadata,
mechanism descriptions, and evidence-based safer therapeutic alternatives.
"""
from flask import Blueprint, render_template, request, session
from app.services.interaction_checker import check_drugs
from app.services.graph_engine import get_clinical_alternatives, get_drug_class

doctor_bp = Blueprint("doctor", __name__)


@doctor_bp.route("/doctor", methods=["GET", "POST"])
def view():
    if request.method == "POST":
        drugs_input = request.form.get("drugs", "").strip()
    else:
        drugs_input = request.args.get("drugs", "").strip()

    # Fallback to session if navigated directly from patient results
    if not drugs_input:
        drugs_input = session.get("last_drugs", "").strip()

    if not drugs_input:
        return render_template("doctor_view.html", result=None, has_data=False)

    # Run full interaction check
    result = check_drugs(drugs_input, lang="en")
    active_generics = [d["generic"] for d in result.get("resolved_drugs", []) if d.get("generic")]

    # Augment drug-drug interactions with alternative options
    flagged_drugs_set = set()
    for ix in result.get("interactions", []):
        name_a = ix.get("drug_a_name", "")
        name_b = ix.get("drug_b_name", "")
        flagged_drugs_set.add(name_a.lower())
        flagged_drugs_set.add(name_b.lower())
        ix["alt_a"] = get_clinical_alternatives(name_a, active_generics, reason=ix.get("description", ""))
        ix["alt_b"] = get_clinical_alternatives(name_b, active_generics, reason=ix.get("description", ""))

    # Augment food interactions with alternative options
    for fix in result.get("food_interactions", []):
        drug_name = fix.get("drug_name", "")
        flagged_drugs_set.add(drug_name.lower())
        fix["alt_drug"] = get_clinical_alternatives(drug_name, active_generics, reason=fix.get("description", ""))

    # Augment resolved drugs list with therapeutic classes and safety status
    for d in result.get("resolved_drugs", []):
        generic = d.get("generic", "")
        d["drug_class"] = get_drug_class(generic)
        d["is_flagged"] = generic.lower() in flagged_drugs_set
        d["alternative"] = get_clinical_alternatives(generic, active_generics)

    # Save to session so returning or switching preserves state
    session["last_drugs"] = drugs_input

    return render_template(
        "doctor_view.html",
        result=result,
        has_data=True,
        drugs_input=drugs_input,
    )
