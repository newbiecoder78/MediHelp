# ─────────────────────────────────────────────────────────────────────────────
# MediHelp — Drug Interaction Checker
# Dockerfile
# Installs system deps (Tesseract OCR) + Python deps, runs via Gunicorn.
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# System dependencies: Tesseract OCR + C libraries for image processing
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

# Copy application source (includes app/data/tessdata and app/static/audio)
COPY wsgi.py .
COPY app/ ./app/

# Environment defaults
ENV PORT=5000
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

# Run gunicorn bound to 0.0.0.0:$PORT
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --timeout 120 --workers 2 wsgi:app"]
