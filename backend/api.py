import json
import os
import shutil
import sys
import threading
from typing import Any

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from main import RUN_STATE_PATH, run_pipeline
from matcher.domain_config import clear_domain_config_cache, load_domain_config
from resume_tailor.tailor import create_tailor_draft, update_draft_status
from storage.db import init_db, list_tailor_drafts, load_latest_decisions, load_latest_profile, save_profile

app = FastAPI(title="CareerAgent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

RESUMES_DIR = "resumes"
DATA_DIR = "data"


class AgentRunRequest(BaseModel):
    resume_path: str = "my_resume.pdf"
    sources: list[str] = Field(default_factory=lambda: ["remotive", "remoteok", "arbeitnow", "jsearch"])
    target_jobs: int = 25
    location: str = ""
    remote: bool = True
    past_24h: bool = False
    adzuna_country: str = "us"
    skip_parse: bool = True
    skip_scrape: bool = False
    custom_queries: list[str] = Field(default_factory=list)
    sector: str = ""
    workplace_type: str = ""
    domain_config_path: str = ""
    use_db: bool = True


class TailorRequest(BaseModel):
    job: dict


class TailorStatusRequest(BaseModel):
    draft_id: int
    status: str
    notes: str = ""


class DomainConfigUpdate(BaseModel):
    path: str = ""
    config: dict = Field(default_factory=dict)


class ParseResumeRequest(BaseModel):
    resume_path: str
    domain_config_path: str = ""


run_lock = threading.Lock()
run_thread: threading.Thread | None = None
run_status = {"stage": "idle", "message": "Agent is idle."}


def load(path: str) -> Any:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    return None


def save(path: str, payload: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)


def save_status(event: dict) -> None:
    global run_status
    run_status = event
    save(RUN_STATE_PATH, event)


def run_agent_background(payload: AgentRunRequest) -> None:
    try:
        run_pipeline(
            resume_path=payload.resume_path,
            source_names=payload.sources,
            target_jobs=payload.target_jobs,
            location=payload.location,
            remote=payload.remote,
            past_24h=payload.past_24h,
            adzuna_country=payload.adzuna_country,
            skip_parse=payload.skip_parse,
            skip_scrape=payload.skip_scrape,
            custom_queries=payload.custom_queries or None,
            sector=payload.sector,
            workplace_type=payload.workplace_type,
            domain_config_path=payload.domain_config_path,
            use_db=payload.use_db,
            callback=save_status,
        )
    except Exception as exc:
        save_status({"stage": "failed", "message": str(exc)})
    finally:
        if run_lock.locked():
            run_lock.release()


@app.on_event("startup")
def startup() -> None:
    try:
        init_db()
    except Exception as exc:
        print(f"DB init warning: {exc}")


@app.get("/api/profile")
def get_profile():
    return load(os.path.join(DATA_DIR, "profile.json")) or load_latest_profile() or {}


@app.get("/api/decisions")
def get_decisions():
    return load_latest_decisions() or load(os.path.join(DATA_DIR, "decisions.json")) or {}


@app.get("/api/jobs")
def get_jobs():
    return load(os.path.join(DATA_DIR, "scored_jobs.json")) or []


@app.get("/api/summary")
def get_summary():
    decisions = get_decisions()
    if not decisions:
        return {}

    all_jobs = (decisions.get("apply", []) + decisions.get("maybe", []) + decisions.get("skip", []))
    top_score = max((job.get("final_score", job.get("match_score", 0)) for job in all_jobs), default=0)

    return {
        **decisions.get("summary", {}),
        "top_score": top_score,
        "skill_advice": decisions.get("skill_advice", {}),
        "apply": decisions.get("apply", []),
        "maybe": decisions.get("maybe", []),
        "skip": decisions.get("skip", []),
    }


@app.get("/api/domain-config")
def get_domain_config(path: str = ""):
    profile = get_profile()
    return load_domain_config(profile, path or None)


@app.post("/api/domain-config")
def save_domain_config(payload: DomainConfigUpdate):
    """Save a domain config and point the active profile at it.

    - Empty config payloads are rejected to prevent accidental clobbering of presets.
    - Curated preset files are write-protected; saves redirect to active.json instead.
    """
    if not payload.config:
        raise HTTPException(status_code=400, detail="Domain config payload is empty.")

    curated = {
        "config/candidates/ai_ml_engineer.json",
        "config/candidates/software_engineer.json",
        "config/domain_config.default.json",
    }
    os.makedirs("config/candidates", exist_ok=True)
    requested = (payload.path or "").replace("\\", "/")
    if not requested or requested in curated:
        target = os.path.join("config", "candidates", "active.json")
    else:
        target = payload.path

    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    with open(target, "w", encoding="utf-8") as file:
        json.dump(payload.config, file, indent=2, ensure_ascii=False)
    clear_domain_config_cache()

    profile = get_profile()
    profile["domain_config_path"] = target
    save(os.path.join(DATA_DIR, "profile.json"), profile)
    save_profile(profile)

    return {"path": target, "config": payload.config}


@app.post("/api/profile/parse")
def parse_profile(payload: ParseResumeRequest):
    if not payload.resume_path:
        raise HTTPException(status_code=400, detail="resume_path is required.")
    if not os.path.exists(payload.resume_path):
        raise HTTPException(status_code=404, detail=f"Resume not found: {payload.resume_path}")

    from resume_parser.parser import parse_resume

    profile = parse_resume(payload.resume_path)
    if payload.domain_config_path:
        profile["domain_config_path"] = payload.domain_config_path
    save(os.path.join(DATA_DIR, "profile.json"), profile)
    save_profile(profile)
    return profile


@app.post("/api/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes are supported.")

    os.makedirs(RESUMES_DIR, exist_ok=True)
    safe_name = os.path.basename(file.filename)
    destination = os.path.join(RESUMES_DIR, safe_name)

    with open(destination, "wb") as out_file:
        shutil.copyfileobj(file.file, out_file)

    return {"resume_path": destination, "filename": safe_name}


@app.post("/api/run-agent")
def start_agent(payload: AgentRunRequest):
    global run_thread, run_status

    if not run_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Agent is already running.")

    run_status = {"stage": "starting", "message": "Agent run starting.", "sources": payload.sources}
    save(RUN_STATE_PATH, run_status)
    run_thread = threading.Thread(target=run_agent_background, args=(payload,), daemon=True)
    run_thread.start()
    return run_status


@app.get("/api/run-agent/status")
def get_agent_status():
    if run_lock.locked():
        return run_status
    persisted = load(RUN_STATE_PATH)
    return persisted or run_status


@app.get("/api/sources")
def list_sources():
    return {
        "sources": [
            {
                "id": "remotive",
                "label": "Remotive",
                "description": "Public remote-jobs API. No API key. Best for tech & remote roles.",
                "production_safe": True,
                "needs_api_key": False,
            },
            {
                "id": "remoteok",
                "label": "RemoteOK",
                "description": "Public remote-jobs feed. No API key. Strong for tech/AI roles.",
                "production_safe": True,
                "needs_api_key": False,
            },
            {
                "id": "arbeitnow",
                "label": "Arbeitnow",
                "description": "European + remote jobs API. No key required.",
                "production_safe": True,
                "needs_api_key": False,
            },
            {
                "id": "adzuna",
                "label": "Adzuna",
                "description": "Official Adzuna search API. Needs ADZUNA_APP_ID + ADZUNA_APP_KEY in .env.",
                "production_safe": True,
                "needs_api_key": True,
            },
            {
                "id": "jsearch",
                "label": "JSearch (Indeed/Google Jobs via RapidAPI)",
                "description": "Aggregator covering Indeed/LinkedIn/Google Jobs. Needs RAPIDAPI_KEY.",
                "production_safe": True,
                "needs_api_key": True,
            },
            {
                "id": "manual",
                "label": "Manual jobs (data/manual_jobs.json)",
                "description": "Paste jobs into data/manual_jobs.json for offline testing.",
                "production_safe": True,
                "needs_api_key": False,
            },
            {
                "id": "existing",
                "label": "Existing jobs cache (data/jobs.json)",
                "description": "Re-score the last collected batch without scraping again.",
                "production_safe": True,
                "needs_api_key": False,
            },
            {
                "id": "council_boards",
                "label": "Council / government boards (prototype)",
                "description": "Reads URLs from config/job_boards.json. Region-agnostic prototype.",
                "production_safe": False,
                "needs_api_key": False,
            },
            {
                "id": "linkedin_local",
                "label": "LinkedIn (local browser session, experimental)",
                "description": "Local Playwright prototype. Needs a saved LinkedIn session. Not for production.",
                "production_safe": False,
                "needs_api_key": False,
            },
        ]
    }


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/tailor/draft")
def tailor_draft(payload: TailorRequest):
    profile = get_profile()
    if not profile:
        raise HTTPException(status_code=400, detail="No profile found. Upload resume and run agent first.")
    return create_tailor_draft(profile, payload.job)


@app.get("/api/tailor/drafts")
def tailor_drafts(status: str | None = None):
    return list_tailor_drafts(status)


@app.post("/api/tailor/status")
def tailor_status(payload: TailorStatusRequest):
    try:
        return update_draft_status(payload.draft_id, payload.status, payload.notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
