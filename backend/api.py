import json
import os
import re
import shutil
import sys
import threading
from typing import Any

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.rate_limit import check_rate_limit, client_key, env_limit
from backend.security import CurrentUser, create_access_token, validate_email, validate_password
from main import RUN_STATE_PATH, run_pipeline
from matcher.domain_config import clear_domain_config_cache, load_domain_config
from resume_tailor.tailor import create_tailor_draft, update_draft_status
from storage.db import (
    create_user,
    init_db,
    list_tailor_drafts,
    load_latest_decisions,
    load_latest_profile,
    load_scored_jobs,
    load_user_api_keys,
    save_profile,
    save_user_api_keys,
    verify_user,
)

app = FastAPI(title="CareerAgent API")

cors_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

RESUMES_DIR = "resumes"
DATA_DIR = "data"
MAX_TARGET_JOBS = env_limit("MAX_TARGET_JOBS_PER_RUN", 30)
MAX_CUSTOM_QUERIES = env_limit("MAX_CUSTOM_QUERIES", 6)
PLATFORM_API_ENV = {
    "RAPIDAPI_KEY": os.getenv("RAPIDAPI_KEY", ""),
    "ADZUNA_APP_ID": os.getenv("ADZUNA_APP_ID", ""),
    "ADZUNA_APP_KEY": os.getenv("ADZUNA_APP_KEY", ""),
    "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
}


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


class ApiKeysUpdate(BaseModel):
    rapidapi_key: str = ""
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    groq_api_key: str = ""


class AuthRequest(BaseModel):
    email: str
    password: str
    name: str = ""


class ParseResumeRequest(BaseModel):
    resume_path: str
    domain_config_path: str = ""


run_lock = threading.Lock()
run_thread: threading.Thread | None = None
run_status = {"stage": "idle", "message": "Agent is idle."}
run_status_by_user: dict[int, dict] = {}


def load(path: str) -> Any:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    return None


def save(path: str, payload: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)


@app.middleware("http")
async def api_rate_limit(request: Request, call_next):
    if request.method != "OPTIONS" and request.url.path.startswith("/api/"):
        check_rate_limit(
            client_key(request, scope="api"),
            env_limit("RATE_LIMIT_API_PER_MINUTE", 180),
            60,
        )
    return await call_next(request)


def save_status(event: dict, user_id: int | None = None) -> None:
    global run_status
    if user_id is not None:
        run_status_by_user[user_id] = event
    else:
        run_status = event
    save(RUN_STATE_PATH, event)


def _sanitize_queries(queries: list[str]) -> list[str]:
    """Strip dangerous characters from user-provided search queries."""
    clean = []
    for q in queries[:MAX_CUSTOM_QUERIES]:
        sanitized = re.sub(r"[<>{}$`\\;|&!#%()\[\]]", "", q).strip()[:200]
        if sanitized:
            clean.append(sanitized)
    return clean


def _apply_user_api_keys(user_id: int) -> None:
    keys = load_user_api_keys(user_id, masked=False)
    mapping = {
        "RAPIDAPI_KEY": "rapidapi_key",
        "ADZUNA_APP_ID": "adzuna_app_id",
        "ADZUNA_APP_KEY": "adzuna_app_key",
        "GROQ_API_KEY": "groq_api_key",
    }
    for env_key, key_name in mapping.items():
        value = keys.get(key_name) or PLATFORM_API_ENV.get(env_key) or ""
        if value:
            os.environ[env_key] = value
        elif env_key in os.environ:
            del os.environ[env_key]


def run_agent_background(payload: AgentRunRequest, user_id: int) -> None:
    try:
        _apply_user_api_keys(user_id)
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
            custom_queries=_sanitize_queries(payload.custom_queries) or None,
            sector=payload.sector,
            workplace_type=payload.workplace_type,
            domain_config_path=payload.domain_config_path,
            use_db=payload.use_db,
            user_id=user_id,
            profile_override=load_latest_profile(user_id) if payload.skip_parse else None,
            callback=lambda event: save_status(event, user_id=user_id),
        )
    except Exception as exc:
        save_status({"stage": "failed", "message": str(exc)}, user_id=user_id)
    finally:
        if run_lock.locked():
            run_lock.release()


@app.on_event("startup")
def startup() -> None:
    try:
        init_db()
    except Exception as exc:
        print(f"DB init warning: {exc}")

    # Load user-saved API keys into env
    saved_keys = load(KEYS_PATH) or {}
    for env_key, config_key in [
        ("RAPIDAPI_KEY", "rapidapi_key"),
        ("ADZUNA_APP_ID", "adzuna_app_id"),
        ("ADZUNA_APP_KEY", "adzuna_app_key"),
        ("GROQ_API_KEY", "groq_api_key"),
    ]:
        if saved_keys.get(config_key) and not os.getenv(env_key):
            os.environ[env_key] = saved_keys[config_key]


@app.post("/api/auth/signup")
def signup(payload: AuthRequest, request: Request):
    check_rate_limit(client_key(request, scope="signup"), env_limit("RATE_LIMIT_SIGNUP_PER_HOUR", 6), 3600)
    email = validate_email(payload.email)
    password = validate_password(payload.password)
    try:
        user = create_user(email, password, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"token": create_access_token(user), "user": user}


@app.post("/api/auth/login")
def login(payload: AuthRequest, request: Request):
    check_rate_limit(client_key(request, scope="login"), env_limit("RATE_LIMIT_LOGIN_PER_MINUTE", 8), 60)
    email = validate_email(payload.email)
    user = verify_user(email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return {"token": create_access_token(user), "user": user}


@app.get("/api/auth/me")
def me(user: CurrentUser):
    return {"user": user}


@app.get("/api/profile")
def get_profile(user: CurrentUser):
    return load_latest_profile(user["id"]) or {}


@app.get("/api/decisions")
def get_decisions(user: CurrentUser):
    return load_latest_decisions(user["id"]) or {}


@app.get("/api/jobs")
def get_jobs(user: CurrentUser):
    return load_scored_jobs(user["id"]) or []


@app.get("/api/summary")
def get_summary(user: CurrentUser):
    decisions = load_latest_decisions(user["id"]) or {}
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
def get_domain_config(user: CurrentUser, path: str = ""):
    profile = load_latest_profile(user["id"]) or {}
    return load_domain_config(profile, path or None)


@app.post("/api/domain-config")
def save_domain_config(payload: DomainConfigUpdate, user: CurrentUser):
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
    user_config_dir = os.path.join("config", "users", str(user["id"]))
    os.makedirs(user_config_dir, exist_ok=True)
    requested = (payload.path or "").replace("\\", "/")
    if not requested or requested in curated or not requested.startswith(f"config/users/{user['id']}/"):
        target = os.path.join(user_config_dir, "domain_config.json")
    else:
        target = requested

    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    with open(target, "w", encoding="utf-8") as file:
        json.dump(payload.config, file, indent=2, ensure_ascii=False)
    clear_domain_config_cache()

    profile = load_latest_profile(user["id"]) or {}
    profile["domain_config_path"] = target
    save(os.path.join(DATA_DIR, "profile.json"), profile)
    save_profile(profile, user_id=user["id"])

    return {"path": target, "config": payload.config}


@app.post("/api/profile/parse")
def parse_profile(payload: ParseResumeRequest, request: Request, user: CurrentUser):
    check_rate_limit(client_key(request, user["id"], "parse"), env_limit("RATE_LIMIT_PARSE_PER_HOUR", 10), 3600)
    if not payload.resume_path:
        raise HTTPException(status_code=400, detail="resume_path is required.")
    if not os.path.exists(payload.resume_path):
        raise HTTPException(status_code=404, detail=f"Resume not found: {payload.resume_path}")

    from resume_parser.parser import parse_resume

    profile = parse_resume(payload.resume_path)
    if payload.domain_config_path:
        profile["domain_config_path"] = payload.domain_config_path
    save(os.path.join(DATA_DIR, "profile.json"), profile)
    save_profile(profile, user_id=user["id"])
    return profile


@app.post("/api/upload-resume")
async def upload_resume(request: Request, user: CurrentUser, file: UploadFile = File(...)):
    check_rate_limit(client_key(request, user["id"], "upload"), env_limit("RATE_LIMIT_UPLOAD_PER_HOUR", 12), 3600)
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes are supported.")

    user_resume_dir = os.path.join(RESUMES_DIR, str(user["id"]))
    os.makedirs(user_resume_dir, exist_ok=True)
    safe_name = os.path.basename(file.filename)
    destination = os.path.join(user_resume_dir, safe_name)

    with open(destination, "wb") as out_file:
        shutil.copyfileobj(file.file, out_file)

    return {"resume_path": destination, "filename": safe_name}


@app.post("/api/run-agent")
def start_agent(payload: AgentRunRequest, request: Request, user: CurrentUser):
    global run_thread, run_status

    check_rate_limit(client_key(request, user["id"], "run-agent"), env_limit("RATE_LIMIT_RUNS_PER_HOUR", 5), 3600)
    if payload.target_jobs > MAX_TARGET_JOBS:
        raise HTTPException(status_code=400, detail=f"target_jobs cannot exceed {MAX_TARGET_JOBS} on this deployment.")
    payload.custom_queries = _sanitize_queries(payload.custom_queries)

    if not run_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Agent is already running.")

    user_status = {"stage": "starting", "message": "Agent run starting.", "sources": payload.sources}
    run_status_by_user[user["id"]] = user_status
    save(RUN_STATE_PATH, user_status)
    run_thread = threading.Thread(target=run_agent_background, args=(payload, user["id"]), daemon=True)
    run_thread.start()
    return user_status


@app.get("/api/run-agent/status")
def get_agent_status(user: CurrentUser):
    if run_lock.locked():
        return run_status_by_user.get(user["id"], {"stage": "running", "message": "Another run is currently active."})
    persisted = load(RUN_STATE_PATH)
    return run_status_by_user.get(user["id"]) or persisted or run_status


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


KEYS_PATH = os.path.join("config", "api_keys.json")
KEY_PATTERN = r"^[A-Za-z0-9_\-\.]+$"


def _mask(value: str) -> str:
    if not value or len(value) < 8:
        return "***" if value else ""
    return value[:4] + "..." + value[-4:]


def _sanitize_key(value: str) -> str:
    import re
    cleaned = value.strip()[:128]
    if cleaned and not re.match(KEY_PATTERN, cleaned):
        raise HTTPException(status_code=400, detail=f"Invalid key format. Only alphanumeric, dash, underscore, dot allowed.")
    return cleaned


@app.get("/api/keys")
def get_api_keys(user: CurrentUser):
    """Return masked per-user keys so the UI can show what's configured."""
    keys = load_user_api_keys(user["id"], masked=True)
    env_rapid = os.getenv("RAPIDAPI_KEY", "")
    env_adzuna_id = os.getenv("ADZUNA_APP_ID", "")
    env_adzuna_key = os.getenv("ADZUNA_APP_KEY", "")
    env_groq = os.getenv("GROQ_API_KEY", "")
    return {
        "rapidapi_key": _mask(keys.get("rapidapi_key") or env_rapid),
        "adzuna_app_id": _mask(keys.get("adzuna_app_id") or env_adzuna_id),
        "adzuna_app_key": _mask(keys.get("adzuna_app_key") or env_adzuna_key),
        "groq_api_key": _mask(keys.get("groq_api_key") or env_groq),
    }


@app.post("/api/keys")
def save_api_keys(payload: ApiKeysUpdate, request: Request, user: CurrentUser):
    """Save user-provided API keys to local SQLite. Validates format."""
    check_rate_limit(client_key(request, user["id"], "keys"), env_limit("RATE_LIMIT_KEYS_PER_HOUR", 20), 3600)
    keys = {}
    if payload.rapidapi_key:
        keys["rapidapi_key"] = _sanitize_key(payload.rapidapi_key)
    if payload.adzuna_app_id:
        keys["adzuna_app_id"] = _sanitize_key(payload.adzuna_app_id)
    if payload.adzuna_app_key:
        keys["adzuna_app_key"] = _sanitize_key(payload.adzuna_app_key)
    if payload.groq_api_key:
        keys["groq_api_key"] = _sanitize_key(payload.groq_api_key)

    masked = save_user_api_keys(user["id"], keys)
    _apply_user_api_keys(user["id"])

    return {"status": "saved", "keys": masked}


@app.post("/api/tailor/draft")
def tailor_draft(payload: TailorRequest, request: Request, user: CurrentUser):
    check_rate_limit(client_key(request, user["id"], "tailor"), env_limit("RATE_LIMIT_TAILOR_PER_HOUR", 12), 3600)
    _apply_user_api_keys(user["id"])
    profile = load_latest_profile(user["id"]) or {}
    if not profile:
        raise HTTPException(status_code=400, detail="No profile found. Upload resume and run agent first.")
    return create_tailor_draft(profile, payload.job, user_id=user["id"])


@app.get("/api/tailor/drafts")
def tailor_drafts(user: CurrentUser, status: str | None = None):
    return list_tailor_drafts(status, user_id=user["id"])


@app.post("/api/tailor/status")
def tailor_status(payload: TailorStatusRequest, user: CurrentUser):
    try:
        return update_draft_status(payload.draft_id, payload.status, payload.notes, user_id=user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
