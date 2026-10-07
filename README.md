# MediHelp 💊

**Drug Interaction Checker for Elderly Patients**

MediHelp helps patients on multiple medicines identify dangerous drug-drug and drug-food interactions. It supports Indian brand names, multilingual alerts (EN/HI/TA/TE), prescription OCR, and voice output — making it accessible to elderly patients who may not know their medicines' generic names.

> Built for a 24-hour hackathon. Phase 1 is complete (text input + RxNav + brand mapping + NetworkX).

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask (Python 3.11) + Gunicorn |
| Knowledge Graph | NetworkX |
| Database / Cache | Supabase (Postgres) |
| Drug Data | RxNav/RxNorm API (NLM) |
| OCR | Tesseract (Phase 2) |
| Voice | gTTS (Phase 3) |
| Deployment | Render (Docker) |

---

## Project Structure

```
medihelp/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── config.py            # env vars + Supabase client
│   ├── routes/
│   │   ├── health.py        # /ping, /health
│   │   └── patient.py       # patient-facing routes
│   ├── services/
│   │   ├── brand_mapper.py  # Indian brand → generic + fuzzy match
│   │   ├── rxnav.py         # RxNav API client + 4-layer fallback
│   │   ├── graph_engine.py  # NetworkX knowledge graph
│   │   └── interaction_checker.py  # pipeline orchestrator
│   ├── data/
│   │   ├── brand_to_generic.json       # curated brand map (~50 entries)
│   │   └── fallback_interactions.json  # offline fallback data
│   └── templates/
│       ├── base.html
│       ├── patient_input.html
│       └── patient_results.html
├── scripts/
│   ├── seed_supabase.py   # populate brand_mappings table
│   └── warm_graph.py      # pre-demo cache warm-up
├── tests/
│   ├── test_brand_mapper.py
│   └── test_graph_engine.py
├── Dockerfile
├── requirements.txt
├── wsgi.py
└── .env.example
```

---

## Supabase Setup

### Create tables in your Supabase SQL editor:

```sql
-- 1. Brand name mappings (Indian brand → generic, with cached RxCUI)
CREATE TABLE brand_mappings (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brand_name   TEXT NOT NULL,
  generic_name TEXT NOT NULL,
  rxcui        TEXT,
  region       TEXT NOT NULL DEFAULT 'IN',
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX brand_mappings_brand_region_idx
  ON brand_mappings (brand_name, region);

-- 2. Drug-drug interaction cache (from RxNav API or curated)
CREATE TABLE drug_interactions (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  drug_a_rxcui   TEXT NOT NULL,
  drug_a_name    TEXT NOT NULL,
  drug_b_rxcui   TEXT NOT NULL,
  drug_b_name    TEXT NOT NULL,
  severity       TEXT NOT NULL CHECK (severity IN ('high', 'medium', 'low')),
  description    TEXT,
  source         TEXT NOT NULL DEFAULT 'rxnav',
  cached_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX drug_interactions_pair_idx
  ON drug_interactions (drug_a_rxcui, drug_b_rxcui);

-- 3. Drug-food interactions (curated dataset — Phase 2)
CREATE TABLE drug_food_interactions (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  drug_name   TEXT NOT NULL,
  drug_rxcui  TEXT,
  food_name   TEXT NOT NULL,
  severity    TEXT NOT NULL CHECK (severity IN ('high', 'medium', 'low')),
  description TEXT,
  source      TEXT NOT NULL DEFAULT 'curated'
);

-- 4. OCR results cache (Phase 2)
CREATE TABLE ocr_results (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  image_hash      TEXT NOT NULL UNIQUE,
  raw_text        TEXT,
  extracted_drugs JSONB,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Alert translations for multilingual support (Phase 2)
CREATE TABLE alert_translations (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  alert_key  TEXT NOT NULL,
  lang       TEXT NOT NULL CHECK (lang IN ('en', 'hi', 'ta', 'te')),
  text       TEXT NOT NULL,
  audio_path TEXT
);
CREATE UNIQUE INDEX alert_translations_key_lang_idx
  ON alert_translations (alert_key, lang);
```

### Enable Row Level Security (recommended):
```sql
-- Allow public reads (the app uses anon key)
ALTER TABLE brand_mappings       ENABLE ROW LEVEL SECURITY;
ALTER TABLE drug_interactions     ENABLE ROW LEVEL SECURITY;
ALTER TABLE drug_food_interactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE ocr_results           ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_translations    ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_all" ON brand_mappings       FOR ALL USING (true);
CREATE POLICY "allow_all" ON drug_interactions     FOR ALL USING (true);
CREATE POLICY "allow_all" ON drug_food_interactions FOR ALL USING (true);
CREATE POLICY "allow_all" ON ocr_results           FOR ALL USING (true);
CREATE POLICY "allow_all" ON alert_translations    FOR ALL USING (true);
```

---

## Local Setup

### Prerequisites
- Python 3.11+
- pip

### 1. Clone and enter the project
```bash
git clone https://github.com/yourname/medihelp.git
cd medihelp
```

### 2. Create a virtual environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
```bash
# Copy the example file
cp .env.example .env

# Edit .env and fill in your Supabase credentials:
# SUPABASE_URL=https://your-project-id.supabase.co
# SUPABASE_KEY=your-anon-key
# FLASK_SECRET_KEY=any-random-string
```

> **Note:** If you don't have Supabase credentials yet, the app will still
> run — it just won't cache results. RxNav API calls will still work,
> and the local fallback data will be used when needed.

### 5. Seed Supabase (optional but recommended)
```bash
python scripts/seed_supabase.py
```

### 6. Run the app
```bash
flask --app wsgi:app run --debug
```

Visit: **http://localhost:5000**

---

## Phase 1 Milestone Test

To verify Phase 1 is working, enter this in the medicine input box:

```
Ecosprin, Combiflam, Crocin
```

**Expected results:**
- **Ecosprin** → mapped to `aspirin` (shown with → arrow in UI)
- **Combiflam** → mapped to `ibuprofen + paracetamol` (split into two components)
- **Crocin** → mapped to `paracetamol`
- At least one interaction flagged: **Aspirin + Ibuprofen** (medium severity)
- The ✓ check mark appears next to each resolved drug

**Second test — known high-risk pair:**
```
Warfarin, Aspirin
```

**Expected:**
- Both resolve to RxCUIs via RxNav
- 🔴 **HIGH RISK** alert shown for Warfarin + Aspirin

---

## Running Tests

```bash
python -m pytest tests/ -v
```

Tests that run without Supabase or internet:
- `tests/test_brand_mapper.py` — 12 tests
- `tests/test_graph_engine.py` — 10 tests

---

## Docker

```bash
# Build
docker build -t medihelp .

# Run (with env vars)
docker run -p 5000:5000 \
  -e SUPABASE_URL=your_url \
  -e SUPABASE_KEY=your_key \
  -e FLASK_SECRET_KEY=your_secret \
  medihelp
```

---

## Deployment (Render)

1. Push repo to GitHub
2. Create new **Web Service** on [Render](https://render.com)
3. Select **Docker** as the environment
4. Add environment variables: `SUPABASE_URL`, `SUPABASE_KEY`, `FLASK_SECRET_KEY`
5. Deploy

### Keep-Alive Setup (prevents cold starts on free tier)

Render free tier sleeps after 15 minutes of inactivity, causing 30-50s cold starts. Prevent this during the judging window:

**Option A — cron-job.org (recommended)**
1. Go to https://cron-job.org → Create free account
2. New job: URL = `https://your-app.onrender.com/ping`, every 10 minutes
3. Enable only during your judging window

**Option B — UptimeRobot**
1. Go to https://uptimerobot.com → Create monitor
2. HTTP(s) monitor: `https://your-app.onrender.com/ping`, interval = 5 minutes

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Redirects to `/patient` |
| GET | `/patient` | Drug input form |
| POST | `/patient/check` | Run interaction check |
| GET | `/ping` | Keep-alive health check |
| GET | `/health` | Health check with app name |

---

## Data Sources

- **Drug interaction data**: [RxNorm/RxNav](https://rxnav.nlm.nih.gov/) — National Library of Medicine
- **Brand name mappings**: Curated manually for common Indian brands
- **Drug-food interactions**: Curated from clinical literature (Phase 2)

---

## Disclaimer

MediHelp is an informational tool only. It is not a substitute for professional medical advice, diagnosis, or treatment. Always consult a qualified healthcare provider before changing any medication.
