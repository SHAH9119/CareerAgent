import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable

from dotenv import load_dotenv

from matcher.domain_config import load_domain_config
from scraper.scraper import deduplicate_jobs, fetch_all_jobs
from scraper.utils import distribute_target

load_dotenv()

EXCLUDED_TITLE_TERMS_BY_LEVEL: dict[str, list[str]] = {}
WRONG_DOMAIN_TITLE_TERMS: list[str] = []


@dataclass
class JobSearchPreferences:
    location: str = ""
    remote: bool = True
    past_24h: bool = False
    target_jobs: int = 25
    desired_role_level: str = ""
    years_of_experience: int = 0
    custom_queries: list[str] | None = None
    sector: str = ""
    workplace_type: str = ""
    profile: dict | None = None
    domain_config_path: str = ""


class JobSource:
    name = "base"

    def search(self, queries: Iterable[str], preferences: JobSearchPreferences) -> list[dict]:
        raise NotImplementedError


class ExistingJobsSource(JobSource):
    name = "existing"

    def __init__(self, path: str = "data/jobs.json"):
        self.path = path

    def search(self, queries: Iterable[str], preferences: JobSearchPreferences) -> list[dict]:
        if not os.path.exists(self.path):
            return []

        with open(self.path, "r", encoding="utf-8") as file:
            jobs = json.load(file)

        for job in jobs:
            job.setdefault("source", self.name)

        return jobs


class AdzunaSource(JobSource):
    name = "adzuna"

    def __init__(self, country: str = "us"):
        self.country = country
        self.app_id = os.getenv("ADZUNA_APP_ID")
        self.app_key = os.getenv("ADZUNA_APP_KEY")

    def search(self, queries: Iterable[str], preferences: JobSearchPreferences) -> list[dict]:
        if not self.app_id or not self.app_key:
            print("Skipping Adzuna: ADZUNA_APP_ID or ADZUNA_APP_KEY is missing.")
            return []

        jobs = []
        queries = list(queries)
        quotas = distribute_target(preferences.target_jobs, len(queries))

        for query, quota in zip(queries, quotas):
            if quota > 0:
                jobs.extend(self._search_query(query, preferences, quota))

        return jobs

    def _search_query(self, query: str, preferences: JobSearchPreferences, per_query: int) -> list[dict]:
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "what": query,
            "results_per_page": min(per_query, 50),
            "content-type": "application/json",
        }

        if preferences.location and preferences.location.lower() not in {"remote", "worldwide"}:
            params["where"] = preferences.location

        if preferences.remote:
            params["what_and"] = "remote"

        url = (
            f"https://api.adzuna.com/v1/api/jobs/{self.country}/search/1?"
            + urllib.parse.urlencode(params)
        )

        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            print(f"Adzuna search failed for '{query}': {exc}")
            return []

        results = []
        for item in payload.get("results", []):
            results.append(
                {
                    "title": item.get("title", "Unknown"),
                    "company": (item.get("company") or {}).get("display_name", "Unknown"),
                    "location": (item.get("location") or {}).get("display_name", ""),
                    "url": item.get("redirect_url", ""),
                    "description": item.get("description", ""),
                    "source": self.name,
                    "source_job_id": item.get("id"),
                }
            )

        return results


class LinkedInLocalSource(JobSource):
    name = "linkedin_local"

    def search(self, queries: Iterable[str], preferences: JobSearchPreferences) -> list[dict]:
        jobs = []
        queries = list(queries)
        quotas = distribute_target(preferences.target_jobs, len(queries))
        filters = {
            "remote": preferences.remote,
            "past_24h": preferences.past_24h,
            "location": preferences.location,
            "desired_role_level": preferences.desired_role_level,
            "years_of_experience": preferences.years_of_experience,
        }

        for query, quota in zip(queries, quotas):
            if quota > 0:
                jobs.extend(fetch_all_jobs(query, target=quota, filters=filters))

        return prefilter_jobs(jobs, preferences)


def _is_non_english(text: str) -> bool:
    """Reject titles that are mostly non-Latin (Chinese, Arabic, etc.) or common non-English."""
    if not text:
        return True
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    if len(text) > 5 and ascii_chars / len(text) < 0.5:
        return True
    non_english_markers = ["ñ", "ção", "ões", "ción", "mente", "gerente", "jefe", "docente", "analista pleno"]
    return any(marker in text.lower() for marker in non_english_markers)


def prefilter_jobs(jobs: list[dict], preferences: JobSearchPreferences) -> list[dict]:
    """Aggressively drop jobs with no relevance to the candidate's domain."""
    role_level = (preferences.desired_role_level or "").lower()
    rules = load_domain_config(preferences.profile, preferences.domain_config_path)
    excluded_level_terms = rules.get("exclude_title_terms_by_level", EXCLUDED_TITLE_TERMS_BY_LEVEL).get(
        role_level, EXCLUDED_TITLE_TERMS_BY_LEVEL.get(role_level, [])
    )
    wrong_domain_terms = rules.get("wrong_domain_title_terms", WRONG_DOMAIN_TITLE_TERMS)
    primary_domain = rules.get("primary_domain", "")

    # Build a broad set of "relevant" terms from ALL tech domains the candidate cares about
    relevant_terms: list[str] = []
    domain_groups = rules.get("domain_groups", {})
    for domain_key in [primary_domain, "software_engineering", "data_analytics"]:
        relevant_terms.extend(domain_groups.get(domain_key, []))
    relevant_terms.extend(rules.get("target_title_terms", {}).get(primary_domain, []))
    relevant_terms.extend(rules.get("requirement_signal_terms", []))
    relevant_terms = list({term.lower() for term in relevant_terms if term and len(term) > 2})

    filtered = []

    for job in jobs:
        title = (job.get("title") or "").lower()
        description = (job.get("description") or "").lower()
        searchable = f"{title} {description}"

        # Skip non-English jobs
        if _is_non_english(job.get("title", "")):
            continue

        # Skip wrong seniority level
        if preferences.sector and job.get("sector") and job.get("sector") != preferences.sector:
            continue
        if preferences.workplace_type and job.get("workplace_type") and job.get("workplace_type") != preferences.workplace_type:
            continue
        if any(term in title for term in excluded_level_terms):
            continue

        # Skip explicitly wrong-domain titles
        if any(term in title for term in wrong_domain_terms):
            continue

        # POSITIVE RELEVANCE CHECK: job must mention at least ONE tech-relevant term
        # in title or description. This kills "Dairy Queen", "Road Ranger" etc.
        has_relevance = any(term in searchable for term in relevant_terms)
        if not has_relevance:
            continue

        filtered.append(job)

    skipped = len(jobs) - len(filtered)
    if skipped:
        print(f"  Prefilter skipped {skipped} irrelevant jobs (wrong domain/language/level).")

    return filtered


def build_sources(source_names: list[str], adzuna_country: str = "us") -> list[JobSource]:
    from scraper.gov_sources import (
        ArbeitnowSource,
        CouncilBoardSource,
        JSearchSource,
        ManualJobsSource,
        RemotiveSource,
        RemoteOkSource,
    )

    sources: list[JobSource] = []

    for source_name in source_names:
        normalized = source_name.strip().lower()
        if normalized in {"existing", "json"}:
            sources.append(ExistingJobsSource())
        elif normalized == "adzuna":
            sources.append(AdzunaSource(country=adzuna_country))
        elif normalized in {"linkedin", "linkedin_local"}:
            sources.append(LinkedInLocalSource())
        elif normalized in {"remotive", "remote_api"}:
            sources.append(RemotiveSource())
        elif normalized in {"remoteok", "remote_ok"}:
            sources.append(RemoteOkSource())
        elif normalized in {"arbeitnow", "arbeit_now"}:
            sources.append(ArbeitnowSource())
        elif normalized in {"jsearch", "rapidapi_jobs", "indeed_api", "indeed"}:
            sources.append(JSearchSource())
        elif normalized in {"manual", "manual_import"}:
            sources.append(ManualJobsSource())
        elif normalized in {"council", "council_boards", "gov_boards"}:
            sources.append(CouncilBoardSource())
        else:
            print(f"Unknown source '{source_name}', skipping.")

    return sources


def resolve_queries(profile: dict, generated: list[str], preferences: JobSearchPreferences) -> list[str]:
    if preferences.custom_queries:
        from scraper.scraper import sanitize_search_queries

        return sanitize_search_queries(preferences.custom_queries, profile)

    return generated


def collect_jobs(
    queries: list[str],
    preferences: JobSearchPreferences,
    source_names: list[str],
    adzuna_country: str = "us",
    profile: dict | None = None,
) -> list[dict]:
    if profile:
        preferences.profile = profile
    queries = resolve_queries(profile or {}, queries, preferences)
    sources = build_sources(source_names, adzuna_country=adzuna_country)
    jobs = []

    for source in sources:
        print(f"Searching source: {source.name}")
        source_jobs = source.search(queries, preferences)
        print(f"  {source.name}: {len(source_jobs)} jobs")
        jobs.extend(source_jobs)

    return deduplicate_jobs(prefilter_jobs(jobs, preferences))[: preferences.target_jobs]
