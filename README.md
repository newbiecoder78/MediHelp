# MediHelp

A prescription safety checker that detects drug-drug and drug-food interactions, with multilingual voice alerts designed for elderly patients in India.

## Problem Statement

Elderly patients in India often take multiple medications prescribed by different doctors. Dangerous drug interactions go undetected because no single system checks them. MediHelp scans printed prescriptions via OCR, checks interactions using RxNav, and explains risks in the patient's local language with voice output.

## Tech Stack

- **Backend**: Flask, Python 3.11
- **Pharmacological Ontology**: RxNav / RxNorm REST API (NLM)
- **Computer Vision**: Tesseract OCR
- **Speech Synthesis**: gTTS (Google Text-to-Speech)
- **Knowledge Graph**: NetworkX
- **Fuzzy Token Matching**: RapidFuzz
- **Templating**: Jinja2 & Vanilla CSS

## Local Setup

```bash
# Clone the repository
git clone https://github.com/newbiecoder78/medihelp.git
cd medihelp

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and set FLASK_SECRET_KEY

# Pre-generate and cache audio files for zero-latency playback
python scripts/precache_audio.py

# Launch development server
flask run
```

## Environment Variables

Create a `.env` file in the project root with the following:

FLASK_SECRET_KEY=your-secret-key-here
RXNAV_TIMEOUT_SECONDS=3
OCR_FUZZY_THRESHOLD=80


Never commit `.env` to git. A `.env.example` file with placeholder values is included in the repository.

## Docker Setup

```bash
# Build Docker image
docker build -t medihelp .

# Run container on port 5000
docker run -p 5000:5000 medihelp
```

## Application Routes

| Endpoint | Method | Description |
|---|:---:|---|
| `/ping` | GET | Health check and keep-alive endpoint (returns `pong` 200) |
| `/patient` | GET | Patient prescription entry portal (text input, preset regimens, OCR image upload) |
| `/patient/check` | POST | Interaction evaluator: returns identified generic entities, drug-drug and drug-food alerts |
| `/doctor` | GET | Clinician portal: RxNorm ontology details, interaction mechanisms, and safer alternatives |
| `/patient/audio/<alert_key>/<lang>` | GET | Audio endpoint serving localized speech alerts in MP3 format |
| `/audio/tts` | GET | Dynamic audio synthesis endpoint with fallback to disk cache |
| `/ocr/upload` | POST | Prescription image processor extracting medication names with confidence scores |

## Supported Languages

- English (`en`)
- Hindi (`hi`)
- Tamil (`ta`)
- Telugu (`te`)

## Testing

Run the automated test suite:

```bash
python -m pytest tests/ -v
```

All 28 tests cover brand name translation, combination drug splitting, NetworkX graph compilation, severity aggregation, and clinical alternative recommendations.

## Keep-Alive Configuration

Render free tier sleeps after 15 minutes of inactivity. To prevent cold starts during demos or judging:

**Option A — cron-job.org (recommended)**
1. Go to [cron-job.org](https://cron-job.org) and create a free account
2. Create a new job with URL: `https://<your-app>.onrender.com/ping`
3. Set schedule: every 10 minutes
4. Enable during your judging window, disable after

**Option B — UptimeRobot**
1. Go to [uptimerobot.com](https://uptimerobot.com) and create a free account
2. Add monitor: HTTP(s), URL: `https://<your-app>.onrender.com/ping`
3. Set interval: 5 minutes

## Roadmap

- **Phase 5 — End-to-End Testing**: Validate against diverse real-world printed clinic prescriptions, test all 4 languages, test voice output, fix edge cases.
- **Edge Case Coverage**: Empty input, unrecognized drug, single drug entry, RxNav timeout fallback.
- **Demo Rehearsal**: Offline contingency validation with pre-cached audio assets ensuring zero internet dependency during presentation.