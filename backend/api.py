from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import json
import os
import threading

from main import RUN_STATE_PATH, run_pipeline

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AgentRunRequest(BaseModel):
    resume_path: str = "my_resume.pdf"
    sources: list[str] = Field(default_factory=lambda: ["existing"])
    target_jobs: int = 25
    location: str = "Pakistan"
    remote: bool = True
    past_24h: bool = False
    adzuna_country: str = "us"
    skip_parse: bool = True
    skip_scrape: bool = False


run_lock = threading.Lock()
run_thread: threading.Thread | None = None
run_status = {
    "stage": "idle",
    "message": "Agent is idle.",
}

def load(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_status(event: dict) -> None:
    global run_status
    run_status = event


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
            callback=save_status,
        )
    except Exception as exc:
        save_status({"stage": "failed", "message": str(exc)})
    finally:
        if run_lock.locked():
            run_lock.release()

@app.get("/api/profile")
def get_profile():
    return load("data/profile.json") or {}

@app.get("/api/decisions")
def get_decisions():
    return load("data/decisions.json") or {}

@app.get("/api/jobs")
def get_jobs():
    return load("data/scored_jobs.json") or []

@app.get("/api/summary")
def get_summary():
    decisions = load("data/decisions.json")
    if not decisions:
        return {}
    
    all_jobs = (
        decisions.get("apply", []) +
        decisions.get("maybe", []) +
        decisions.get("skip",  [])
    )
    top_score = max((j.get("match_score", 0) for j in all_jobs), default=0)
    
    return {
        **decisions.get("summary", {}),
        "top_score": top_score,
        "skill_advice": decisions.get("skill_advice", {}),
        "apply":  decisions.get("apply",  []),
        "maybe":  decisions.get("maybe",  []),
        "skip":   decisions.get("skip",   []),
    }


@app.post("/api/run-agent")
def start_agent(payload: AgentRunRequest):
    global run_thread, run_status

    if not run_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Agent is already running.")

    run_status = {"stage": "starting", "message": "Agent run starting."}
    run_thread = threading.Thread(target=run_agent_background, args=(payload,), daemon=True)
    run_thread.start()

    return run_status


@app.get("/api/run-agent/status")
def get_agent_status():
    persisted = load(RUN_STATE_PATH)
    return persisted or run_status
