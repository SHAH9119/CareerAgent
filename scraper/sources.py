import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable

from dotenv import load_dotenv

from scraper.scraper import deduplicate_jobs, fetch_all_jobs

load_dotenv()


@dataclass
class JobSearchPreferences:
    location: str = "Pakistan"
    remote: bool = True
    past_24h: bool = False
    target_jobs: int = 25


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
        per_query = max(1, preferences.target_jobs // max(1, len(queries)))

        for query in queries:
            jobs.extend(self._search_query(query, preferences, per_query))

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
        per_query = max(1, preferences.target_jobs // max(1, len(queries)))
        filters = {
            "remote": preferences.remote,
            "past_24h": preferences.past_24h,
            "location": preferences.location,
        }

        for query in queries:
            jobs.extend(fetch_all_jobs(query, target=per_query, filters=filters))

        return jobs


def build_sources(source_names: list[str], adzuna_country: str = "us") -> list[JobSource]:
    sources: list[JobSource] = []

    for source_name in source_names:
        normalized = source_name.strip().lower()
        if normalized in {"existing", "manual", "json"}:
            sources.append(ExistingJobsSource())
        elif normalized == "adzuna":
            sources.append(AdzunaSource(country=adzuna_country))
        elif normalized in {"linkedin", "linkedin_local"}:
            sources.append(LinkedInLocalSource())
        else:
            print(f"Unknown source '{source_name}', skipping.")

    return sources


def collect_jobs(
    queries: list[str],
    preferences: JobSearchPreferences,
    source_names: list[str],
    adzuna_country: str = "us",
) -> list[dict]:
    sources = build_sources(source_names, adzuna_country=adzuna_country)
    jobs = []

    for source in sources:
        print(f"Searching source: {source.name}")
        source_jobs = source.search(queries, preferences)
        print(f"  {source.name}: {len(source_jobs)} jobs")
        jobs.extend(source_jobs)

    return deduplicate_jobs(jobs)[: preferences.target_jobs]
