"""
app/services/ocr_engine.py

Tesseract OCR extraction, text cleaning, and fuzzy drug matching pipeline
for PRINTED prescriptions.

Workflow:
  1. extract_text: Image preprocessing (grayscale, contrast) + Tesseract OCR
  2. clean_ocr_text: Strip dosage ('500mg'), frequency ('1-0-1', 'BD'), and Rx boilerplate
  3. fuzzy_match_drugs: RapidFuzz matching against Indian brands & generic names with confidence scores
"""
import io
import json
import os
import re
import shutil
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
from rapidfuzz import process, fuzz
from app.config import Config

# Configure Tesseract binary path
if os.environ.get("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = os.environ.get("TESSERACT_CMD")
elif shutil.which("tesseract"):
    pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract")
elif os.name == "nt":
    _common_win_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    ]
    for p in _common_win_paths:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            break

# Local tessdata directory containing traineddata models (e.g. eng, osd)
_TESSDATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "tessdata"))
if os.path.exists(_TESSDATA_DIR):
    os.environ["TESSDATA_PREFIX"] = _TESSDATA_DIR

# Load reference drug vocabulary (brands + generics)
_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "brand_to_generic.json")


def _get_drug_vocabulary() -> tuple[dict[str, str], list[str]]:
    try:
        with open(_DATA_PATH, encoding="utf-8") as f:
            data = json.load(f)
        brand_map = {k.lower(): v.lower() for k, v in data.items() if not k.startswith("_")}
    except Exception:
        brand_map = {}

    vocab = set(brand_map.keys())
    for v in brand_map.values():
        for part in v.split("+"):
            vocab.add(part.strip().lower())

    # Add other common generic drugs
    common_generics = [
        "warfarin", "aspirin", "paracetamol", "ibuprofen", "metformin",
        "atorvastatin", "rosuvastatin", "amlodipine", "lisinopril", "telmisartan",
        "ciprofloxacin", "metronidazole", "levothyroxine", "pantoprazole",
        "omeprazole", "amoxicillin", "azithromycin", "tetracycline", "digoxin"
    ]
    vocab.update(common_generics)

    return brand_map, list(vocab)


_BRAND_MAP, _DRUG_VOCAB = _get_drug_vocabulary()


def preprocess_image(image: Image.Image) -> Image.Image:
    """Enhance printed text contrast for OCR clarity."""
    try:
        # Convert to grayscale
        gray = image.convert("L")
        # Increase contrast
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(2.0)
        return enhanced
    except Exception:
        return image


def extract_text(image_input: io.BytesIO | bytes | Image.Image | str) -> str:
    """
    Extract raw text from a prescription image using Tesseract OCR.
    """
    try:
        if os.path.exists(_TESSDATA_DIR):
            os.environ["TESSDATA_PREFIX"] = _TESSDATA_DIR

        if isinstance(image_input, (bytes, bytearray)):
            image = Image.open(io.BytesIO(image_input))
        elif isinstance(image_input, io.BytesIO):
            image = Image.open(image_input)
        elif isinstance(image_input, str):
            image = Image.open(image_input)
        else:
            image = image_input

        processed = preprocess_image(image)
        text = pytesseract.image_to_string(processed, config="--psm 6")
        if not text.strip():
            text = pytesseract.image_to_string(processed, config="--psm 4")
        return text
    except Exception as exc:
        print(f"[ocr_engine] OCR extraction failed: {exc}")
        return ""


def clean_ocr_text(raw_text: str) -> list[str]:
    """
    Clean OCR text by removing dosages, frequencies, and Rx boilerplate.
    Returns candidate drug name tokens.
    """
    if not raw_text:
        return []

    # Regex patterns to strip
    # 1. Dosage patterns (e.g. 500mg, 10 ml, 250 mcg, 5 mg, 1 tab)
    dosage_pattern = re.compile(
        r"\b\d+(\.\d+)?\s*(mg|ml|mcg|gm|g|iu|tablets?|capsules?|drops?|pills?|tab|cap|tabs|caps)\b",
        re.IGNORECASE
    )

    # 2. Frequency patterns (e.g. 1-0-1, 1-1-1, BD, TDS, OD, QID, HS, SOS, PO, PRN)
    freq_pattern = re.compile(
        r"\b([012]-[012]-[012]|[012]x\d|od|bd|tds|qid|hs|sos|prn|po|stat|qds|bbf|pc|ac|bid|tid)\b",
        re.IGNORECASE
    )

    # 3. Common Rx boilerplate tokens & headers
    boilerplate_pattern = re.compile(
        r"\b(rx|dr\.|doctor|patient|age|sex|date|clinic|hospital|signature|reg|no\.|no|name|address|ph|phone|mob|tel|tabs?|caps?|syrup|syp|inj|tablet|capsule|days|daily|once|twice|thrice|morning|night|after|food|before)\b",
        re.IGNORECASE
    )

    candidates = []
    lines = raw_text.splitlines()

    for line in lines:
        cleaned_line = line.strip()
        if not cleaned_line:
            continue

        # Remove numbers and bullet symbols at start of line like "1. ", "1)", "- "
        cleaned_line = re.sub(r"^\s*(\d+[\.\)\-:]|\-|\*|•)\s*", "", cleaned_line)

        # Strip dosage, frequencies, boilerplate
        cleaned_line = dosage_pattern.sub(" ", cleaned_line)
        cleaned_line = freq_pattern.sub(" ", cleaned_line)
        cleaned_line = boilerplate_pattern.sub(" ", cleaned_line)

        # Remove stray special characters and isolated digits
        cleaned_line = re.sub(r"[^\w\s\+\-]", " ", cleaned_line)
        cleaned_line = re.sub(r"\b\d+\b", " ", cleaned_line)
        cleaned_line = re.sub(r"\s+", " ", cleaned_line).strip()

        # Split words or short multi-word phrases
        if len(cleaned_line) >= 3:
            tokens = [t.strip() for t in cleaned_line.split() if len(t.strip()) >= 3]
            for token in tokens:
                # Strip leading joined prefixes like Tab/Cap/Inj/Syp/Rx
                token = re.sub(r"^(tab|cap|inj|syp|rx)", "", token, flags=re.IGNORECASE)
                # Strip trailing joined dosage numbers/units like 500mg/75mg
                token = re.sub(r"\d+(mg|ml|mcg|gm|g|iu)?$", "", token, flags=re.IGNORECASE)
                token = token.strip("-+ ")

                # Discard noise words & prescription headers
                if len(token) >= 3 and token.lower() not in {"prescription", "preseription", "doctor", "patient", "clinic", "hospital"}:
                    if token.isalpha() or "-" in token or "+" in token:
                        candidates.append(token)

    # Deduplicate while preserving order
    seen = set()
    unique_candidates = []
    for c in candidates:
        low = c.lower()
        if low not in seen:
            seen.add(low)
            unique_candidates.append(c)

    return unique_candidates


def fuzzy_match_drugs(
    candidates: list[str],
    threshold: int | None = None
) -> list[dict]:
    """
    Fuzzy match candidate tokens against the known drug vocabulary.

    Returns list of dicts:
    {
      "raw": str,
      "matched": str,
      "generic": str,
      "score": int,
      "confidence": "high" | "medium" | "unmatched",
      "is_valid": bool
    }
    """
    if threshold is None:
        threshold = getattr(Config, "OCR_FUZZY_THRESHOLD", 80)

    results = []

    for cand in candidates:
        cand_clean = cand.strip().lower()
        if not cand_clean or len(cand_clean) < 3:
            continue

        # Extract best match from vocabulary
        match_res = process.extractOne(
            cand_clean,
            _DRUG_VOCAB,
            scorer=fuzz.WRatio
        )

        if match_res and match_res[1] >= threshold:
            matched_name = match_res[0]
            score = int(match_res[1])
            # Determine generic mapping
            generic_name = _BRAND_MAP.get(matched_name, matched_name)
            confidence = "high" if score >= 90 else "medium"

            results.append({
                "raw":        cand,
                "matched":    matched_name,
                "generic":    generic_name,
                "score":      score,
                "confidence": confidence,
                "is_valid":   True,
            })
        else:
            score = int(match_res[1]) if match_res else 0
            results.append({
                "raw":        cand,
                "matched":    cand,
                "generic":    cand.lower(),
                "score":      score,
                "confidence": "unmatched",
                "is_valid":   False,
            })

    return results


def process_prescription_image(image_bytes: bytes) -> dict:
    """
    End-to-end OCR pipeline for uploaded image bytes.
    """
    raw_text = extract_text(image_bytes)
    candidates = clean_ocr_text(raw_text)
    matched_drugs = fuzzy_match_drugs(candidates)

    return {
        "raw_text":      raw_text,
        "candidates":    candidates,
        "matched_drugs": matched_drugs,
    }
