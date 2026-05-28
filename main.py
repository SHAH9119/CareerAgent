import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Callable

# Force UTF-8 stdout/stderr on Windows so emoji / non-ASCII job titles don't
# break the pipeline when the run is launched from cmd / PowerShell.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


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
    role_level = profile.get("desired_role_level") or ""

    queries = []
    if titles:
        queries.extend(titles[:3])
    if skills:
        prefix = role_level if role_level and role_level not in {"mid-level", "senior"} else ""
        queries.append(f"{prefix} {' '.join(skills[:2])}".strip())

    return queries[:3] or ["Software Engineer"]


def run_pipeline(
    resume_path: str = "my_resume.pdf",
    source_names: list[str] | None = None,
    target_jobs: int = 25,
    location: str = "",
    remote: bool = True,
    past_24h: bool = False,
    adzuna_country: str = "us",
    skip_parse: bool = False,
    skip_scrape: bool = False,
    custom_queries: list[str] | None = None,
    sector: str = "",
    workplace_type: str = "",
    domain_config_path: str = "",
    use_db: bool = True,
    callback: ProgressCallback | None = None,
) -> dict:
    """Run the full agent pipeline and persist every stage to data/*.json."""
    source_names = source_names or ["remotive", "remoteok", "arbeitnow", "jsearch"]

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

        if domain_config_path:
            profile["domain_config_path"] = domain_config_path

        if not skip_parse or domain_config_path:
            write_json(PROFILE_PATH, profile)

        if skip_scrape or set(source_names).issubset({"existing", "json"}):
            emit("jobs", "Loading existing jobs.", callback)
            jobs = read_json(JOBS_PATH, [])
            # Always re-apply the prefilter so updated config rules take effect
            from scraper.sources import JobSearchPreferences, prefilter_jobs

            _prefs = JobSearchPreferences(
                location=location,
                remote=remote,
                desired_role_level=profile.get("desired_role_level", ""),
                years_of_experience=profile.get("years_of_experience", 0) or 0,
                profile=profile,
                domain_config_path=domain_config_path or profile.get("domain_config_path", ""),
            )
            jobs = prefilter_jobs(jobs, _prefs)
        else:
            emit("queries", "Generating search plan.", callback)
            from scraper.scraper import generate_search_plan

            queries = custom_queries or generate_search_plan(profile) or fallback_queries(profile)
            emit("queries", f"Search plan ready: {', '.join(queries)}.", callback, queries=queries)

            emit("jobs", f"Collecting jobs from {', '.join(source_names)}.", callback)
            from scraper.sources import JobSearchPreferences, collect_jobs

            preferences = JobSearchPreferences(
                location=location,
                remote=remote,
                past_24h=past_24h,
                target_jobs=target_jobs,
                desired_role_level=profile.get("desired_role_level", ""),
                years_of_experience=profile.get("years_of_experience", 0) or 0,
                custom_queries=custom_queries,
                sector=sector,
                workplace_type=workplace_type,
                profile=profile,
                domain_config_path=domain_config_path or profile.get("domain_config_path", ""),
            )
            jobs = collect_jobs(
                queries=queries,
                preferences=preferences,
                source_names=source_names,
                adzuna_country=adzuna_country,
                profile=profile,
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
        write_json(SCORED_JOBS_PATH, scored_jobs)  # re-persist with decision fields
        write_json(DECISIONS_PATH, decisions)

        if use_db:
            from storage.db import sync_pipeline_results

            sync_pipeline_results(profile, jobs, scored_jobs, decisions, read_json(RUN_STATE_PATH, {}))

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
    parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        help=(
            "Job source: remotive, remoteok, arbeitnow, adzuna, jsearch, manual, "
            "existing, council_boards, linkedin_local. Pass --source multiple times."
        ),
    )
    parser.add_argument("--target", type=int, default=25, help="Maximum jobs to collect and score.")
    parser.add_argument("--location", default="", help="Preferred location (free text). Leave empty for remote-only.")
    parser.add_argument("--remote", action="store_true", help="Prefer remote jobs.")
    parser.add_argument("--past-24h", action="store_true", help="Prefer jobs posted in the last 24 hours where supported.")
    parser.add_argument("--adzuna-country", default="us", help="Adzuna country code, for example us, gb, ca, au, in.")
    parser.add_argument("--skip-parse", action="store_true", help="Use data/profile.json instead of parsing the resume.")
    parser.add_argument("--skip-scrape", action="store_true", help="Use data/jobs.json instead of fetching jobs.")
    parser.add_argument("--queries", nargs="+", help="Custom search queries (overrides the LLM-generated plan).")
    parser.add_argument("--sector", default="", help="Sector filter: private, local_government, state_government, federal_government.")
    parser.add_argument("--workplace", default="", help="Workplace filter: remote, hybrid, on-site.")
    parser.add_argument("--domain-config", default="", help="Path to per-candidate domain config JSON.")
    parser.add_argument("--no-db", action="store_true", help="Skip SQLite sync (JSON only).")
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
        custom_queries=args.queries,
        sector=args.sector,
        workplace_type=args.workplace,
        domain_config_path=args.domain_config,
        use_db=not args.no_db,
    )
