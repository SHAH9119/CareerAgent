import argparse
import json
import os
from datetime import datetime, timezone
from typing import Callable


DATA_DIR = "data"
PROFILE_PATH = os.path.join(DATA_DIR, "profile.json")
JOBS_PATH = os.path.join(DATA_DIR, "jobs.json")
SCORED_JOBS_PATH = os.path.join(DATA_DIR, "scored_jobs.json")
DECISIONS_PATH = os.path.join(DATA_DIR, "decisions.json")
RUN_STATE_PATH = os.path.join(DATA_DIR, "agent_run.json")


ProgressCallback = Callable[[dict], None]


def read_json(path: str, default):
    if not os.path.exists(path):
        return default

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)


def emit(stage: str, message: str, callback: ProgressCallback | None = None, **extra) -> None:
    event = {
        "stage": stage,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **extra,
    }
    print(f"[{stage}] {message}")
    write_json(RUN_STATE_PATH, event)

    if callback:
        callback(event)


def fallback_queries(profile: dict) -> list[str]:
    titles = profile.get("job_titles") or []
    skills = profile.get("skills") or []

    queries = []
    if titles:
        queries.extend(titles[:3])
    if skills:
        queries.append(" ".join(skills[:3]))

    return queries[:3] or ["Software Engineer"]


def run_pipeline(
    resume_path: str = "my_resume.pdf",
    source_names: list[str] | None = None,
    target_jobs: int = 25,
    location: str = "Pakistan",
    remote: bool = True,
    past_24h: bool = False,
    adzuna_country: str = "us",
    skip_parse: bool = False,
    skip_scrape: bool = False,
    callback: ProgressCallback | None = None,
) -> dict:
    """Run the full agent pipeline and persist every stage to data/*.json."""
    source_names = source_names or ["existing"]

    write_json(
        RUN_STATE_PATH,
        {
            "stage": "starting",
            "message": "Agent run queued.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sources": source_names,
        },
    )

    try:
        if skip_parse:
            emit("profile", "Loading existing profile.", callback)
            profile = read_json(PROFILE_PATH, {})
            if not profile:
                raise FileNotFoundError("data/profile.json does not exist. Run without skip_parse first.")
        else:
            emit("profile", f"Parsing resume from {resume_path}.", callback)
            from resume_parser.parser import parse_resume

            profile = parse_resume(resume_path)
            write_json(PROFILE_PATH, profile)

        if skip_scrape:
            emit("jobs", "Loading existing jobs.", callback)
            jobs = read_json(JOBS_PATH, [])
        else:
            if set(source_names).issubset({"existing", "manual", "json"}):
                emit("jobs", "Loading existing jobs.", callback)
                jobs = read_json(JOBS_PATH, [])
            else:
                emit("queries", "Generating search plan.", callback)
                from scraper.scraper import generate_search_plan

                queries = generate_search_plan(profile) or fallback_queries(profile)
                emit("queries", f"Search plan ready: {', '.join(queries)}.", callback, queries=queries)

                emit("jobs", f"Collecting jobs from {', '.join(source_names)}.", callback)
                from scraper.sources import JobSearchPreferences, collect_jobs

                preferences = JobSearchPreferences(
                    location=location,
                    remote=remote,
                    past_24h=past_24h,
                    target_jobs=target_jobs,
                )
                jobs = collect_jobs(
                    queries=queries,
                    preferences=preferences,
                    source_names=source_names,
                    adzuna_country=adzuna_country,
                )
                write_json(JOBS_PATH, jobs)

        if not jobs:
            raise RuntimeError("No jobs were collected. Try source=existing with data/jobs.json or configure an API source.")

        emit("matching", f"Scoring {len(jobs)} jobs.", callback, job_count=len(jobs))
        from matcher.matcher import match_jobs

        scored_jobs = match_jobs(profile, jobs)
        write_json(SCORED_JOBS_PATH, scored_jobs)

        emit("decision", "Assigning decisions and skill advice.", callback)
        from decision.engine import run_decision_engine

        decisions = run_decision_engine(profile, scored_jobs)
        write_json(DECISIONS_PATH, decisions)

        result = {
            "stage": "succeeded",
            "message": "Agent run completed.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": decisions.get("summary", {}),
            "sources": source_names,
        }
        write_json(RUN_STATE_PATH, result)
        if callback:
            callback(result)
        return result
    except Exception as exc:
        error = {
            "stage": "failed",
            "message": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sources": source_names,
        }
        write_json(RUN_STATE_PATH, error)
        if callback:
            callback(error)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AI Job Application Agent pipeline.")
    parser.add_argument("--resume", default="my_resume.pdf", help="Path to the resume PDF.")
    parser.add_argument("--source", action="append", dest="sources", help="Job source: existing, adzuna, linkedin_local.")
    parser.add_argument("--target", type=int, default=25, help="Maximum jobs to collect and score.")
    parser.add_argument("--location", default="Pakistan", help="Preferred location.")
    parser.add_argument("--remote", action="store_true", help="Prefer remote jobs.")
    parser.add_argument("--past-24h", action="store_true", help="Prefer jobs posted in the last 24 hours where supported.")
    parser.add_argument("--adzuna-country", default="us", help="Adzuna country code, for example us, gb, ca, au, in.")
    parser.add_argument("--skip-parse", action="store_true", help="Use data/profile.json instead of parsing the resume.")
    parser.add_argument("--skip-scrape", action="store_true", help="Use data/jobs.json instead of fetching jobs.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_pipeline(
        resume_path=args.resume,
        source_names=args.sources or ["existing"],
        target_jobs=args.target,
        location=args.location,
        remote=args.remote,
        past_24h=args.past_24h,
        adzuna_country=args.adzuna_country,
        skip_parse=args.skip_parse,
        skip_scrape=args.skip_scrape,
    )
