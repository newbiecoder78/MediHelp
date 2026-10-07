# ─────────────────────────────────────────────────────────────────────────────
# MediHelp — Drug Interaction Checker
# Dockerfile
# Installs system deps (Tesseract) + Python deps, runs via Gunicorn.
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# System dependencies: Tesseract OCR (Phase 2) + OpenGL stub (Pillow)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

EXPOSE 5000

# gunicorn timeout=120 to handle slow first RxNav calls
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "--workers", "2", "wsgi:app"]
