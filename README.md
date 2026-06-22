# CareerAgent

AI job-application assistant. Parses your resume, collects jobs from public APIs,
scores how well each one fits, splits them into Apply / Maybe / Skip, and drafts
tailored resumes for the ones worth applying to.

The whole pipeline is country-agnostic: it ships with sensible defaults and pulls
its scoring rules from layered config files instead of hard-coded role assumptions.

## Features

- **Resume parsing** (PDF -> structured profile) using Groq LLMs.
- **Job collection** from production-safe sources without scraping LinkedIn:
  - `remotive` and `remoteok` (no API keys, great for tech / remote roles).
  - `arbeitnow` (Europe + remote, no key).
  - `adzuna` (official API, needs `ADZUNA_APP_ID` + `ADZUNA_APP_KEY`).
  - `jsearch` (Indeed / Google Jobs aggregator via RapidAPI, needs `RAPIDAPI_KEY`).
  - `manual` (drop jobs into `data/manual_jobs.json` for offline / curated runs).
  - `existing` (re-score the last collected jobs without scraping again).
  - LinkedIn scraping is included as an opt-in, local-only prototype.
- **Semantic + heuristic matching**: sentence-transformer cosine similarity
  combined with domain, seniority, requirement, and job-quality signals.
- **Decision engine**: thresholds you can tune from the dashboard.
- **Resume tailoring**: per-job tailored draft with draft -> review -> approved
  workflow stored in SQLite.
- **React + Vite dashboard** for the whole flow (jobs, fit, tailoring, settings).
- **Auth + abuse limits**: email/password signup, bearer-token sessions, per-user API-key settings, target-job caps, and endpoint rate limits.

## Setup

```powershell
pip install -r requirements.txt
cd frontend
npm install
cd ..
```

Copy `.env.example` to `.env` and set the secrets you have:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...        # required for resume parsing, fit analysis, and tailoring
GROQ_API_KEY_2=gsk_...      # optional fallback key
AUTH_SECRET=change-me       # required before public deployment
DATABASE_URL=               # optional Supabase/Postgres URL; empty uses local SQLite

ADZUNA_APP_ID=              # optional, only needed if you select the Adzuna source
ADZUNA_APP_KEY=
RAPIDAPI_KEY=               # optional, only needed if you select JSearch
```

Users can also add their own RapidAPI, Adzuna, and Groq keys from the Settings
page after signup. Those keys are stored per user in the configured database and
are masked in the UI.

For Supabase database mode, use the database connection string from Supabase:

```env
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.bshplcsjqfjhgqyiscuk.supabase.co:5432/postgres
```

Keep this in backend environment variables only. Do not put the database password
in frontend code, screenshots, README examples, or GitHub.

## Run the app

Two terminals.

Terminal 1 (backend):

```powershell
$env:PYTHONIOENCODING="utf-8"
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

Terminal 2 (frontend):

```powershell
cd frontend
npm run dev
```

Open http://localhost:5173 (or whatever port Vite reports) in your browser.

Create an account, then use Settings for API keys and the Dashboard to upload a
resume/run the agent.

## Deployment (free tier demo)

CareerAgent ships with configs for a **Vercel frontend + Render backend** demo stack.

### 1. Push to GitHub

The repo is at [github.com/SHAH9119/CareerAgent](https://github.com/SHAH9119/CareerAgent).

### 2. Deploy backend (Render — free)

1. Go to [render.com](https://render.com) → **New** → **Blueprint** → connect this repo.
2. Render reads `render.yaml` and creates the `careeragent-api` web service.
3. Set these env vars in the Render dashboard:
   - `GROQ_API_KEY` — your Groq key (or let users add their own in Settings)
   - `CORS_ORIGINS` — your Vercel URL, e.g. `https://career-agent.vercel.app`
   - `DATABASE_URL` — optional Supabase Postgres URL for persistent multi-user storage
4. Copy the Render service URL (e.g. `https://careeragent-api.onrender.com`).

**Note:** First request after idle may take 30–60s (free tier cold start). The matcher downloads `all-MiniLM-L6-v2` on first run (~90 MB).

### 3. Deploy frontend (Vercel — free)

1. Go to [vercel.com](https://vercel.com) → **Add New Project** → import this repo.
2. Set **Root Directory** to `frontend`.
3. Add env var: `VITE_API_URL=https://your-render-url.onrender.com/api`
4. Deploy. Vercel uses `frontend/vercel.json` for SPA routing.

### 4. Wire CORS

Update Render `CORS_ORIGINS` to your final Vercel domain and redeploy if needed.

### Docker (optional)

```powershell
docker build -t careeragent .
docker run -p 8000:8000 -e AUTH_SECRET=change-me -e GROQ_API_KEY=gsk_... careeragent
```

### Demo vs production SaaS

1. **Demo deployment**: Render + Vercel, SQLite or Supabase Postgres, conservative rate limits, users bring their own API keys.
2. **Production SaaS**: managed encryption for user keys, email verification/password reset, background job queue (Redis/Celery), billing/quotas.

Important env values before public launch:

```env
AUTH_SECRET=long-random-production-secret
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.example.supabase.co:5432/postgres
CORS_ORIGINS=https://your-app.vercel.app
MAX_TARGET_JOBS_PER_RUN=25
RATE_LIMIT_RUNS_PER_HOUR=5
RATE_LIMIT_TAILOR_PER_HOUR=10
```

## Domain rules (no code edits)

Rules are layered:

1. `config/domain_config.default.json` - country-agnostic defaults.
2. Optional candidate template in `config/candidates/<role>.json`. Two ship in
   the box: `ai_ml_engineer.json` and `software_engineer.json`.
3. Anything you save from the Settings tab lands in
   `config/candidates/active.json` (curated presets are write-protected).

## CLI usage (optional)

```powershell
# Use saved profile + saved jobs (fast)
python main.py --skip-parse --source existing

# Pull fresh jobs from public APIs - no LinkedIn
python main.py --skip-parse --source remotive --source remoteok --source arbeitnow `
  --target 25 --queries "Machine Learning Engineer" "Computer Vision" "Python Developer"

# Use the Adzuna API (needs keys in .env)
python main.py --skip-parse --source adzuna --target 30 --location "Karachi, Pakistan"
```

## Smoke tests

```powershell
# Backend HTTP endpoints (run while uvicorn is up)
python test_e2e.py

# Public job-source connectivity
python test_sources.py

# Headless UI walkthrough (writes screenshots to data/ui_screens/)
python test_frontend.py
```

## Project layout

```
backend/api.py          FastAPI app, run lock, tailor + domain endpoints
main.py                 Pipeline orchestrator (parse -> scrape -> match -> decide)
resume_parser/          PDF -> profile JSON (Groq)
scraper/                Job sources + the LinkedIn local prototype
matcher/                Semantic + heuristic fit scoring
decision/               Apply / Maybe / Skip + skill advice
resume_tailor/          Tailored-resume drafts
storage/                SQLite mirror of the JSON pipeline outputs
frontend/               Vite + React dashboard
config/                 Default + per-candidate domain rules
```
