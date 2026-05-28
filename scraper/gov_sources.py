"""Public job board sources (no LinkedIn session). Prototype HTML fetchers."""

import json
import os
import re
import urllib.parse
import urllib.request
from urllib.error import HTTPError
from html import unescape

from bs4 import BeautifulSoup

from scraper.job_text import clean_job_description, clean_text
from scraper.utils import distribute_target

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch_html(url: str, timeout: int = 30) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        if exc.code in {301, 302, 303, 307, 308} and exc.headers.get("Location"):
            redirected_url = urllib.parse.urljoin(url, exc.headers["Location"])
            redirected_request = urllib.request.Request(redirected_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(redirected_request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        raise


DETAIL_SELECTORS = [
    "[data-automation='jobAdDetails']",
    "[data-automation='job-detail']",
    "[data-testid='job-detail']",
    ".job-details",
    ".job-description",
    "article",
    "main",
]


def fetch_detail_description(url: str, source: str) -> str:
    """Best-effort detail fetch for public boards so matcher has real text."""
    if not url:
        return ""

    try:
        soup = BeautifulSoup(fetch_html(url, timeout=30), "html.parser")
    except Exception as exc:
        print(f"  {source} detail fetch failed: {exc}")
        return ""

    for selector in DETAIL_SELECTORS:
        element = soup.select_one(selector)
        if element:
            description = clean_job_description(element.get_text(" ", strip=True), source=source)
            if len(description) >= 120:
                return description

    description = clean_job_description(soup.get_text(" ", strip=True), source=source)
    return description if len(description) >= 120 else ""


def html_to_description(value: str, source: str) -> str:
    return clean_job_description(BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True), source=source)


GENERIC_QUERY_WORDS = {
    "engineer",
    "developer",
    "manager",
    "specialist",
    "consultant",
    "officer",
    "assistant",
    "associate",
    "senior",
    "junior",
    "lead",
    "staff",
    "remote",
    "jobs",
    "role",
}


def important_query_words(query: str) -> list[str]:
    words = [word.lower() for word in re.findall(r"[a-zA-Z0-9+#.]+", query or "") if len(word) > 2]
    return [word for word in words if word not in GENERIC_QUERY_WORDS] or words


def query_matches_job(query: str, job: dict) -> bool:
    important_words = important_query_words(query)
    if not important_words:
        return True

    title_tags = " ".join(
        [
            job.get("title", ""),
            job.get("company", ""),
            job.get("location", ""),
            " ".join(job.get("tags", []) or []),
        ]
    ).lower()
    full_text = " ".join(
        [
            title_tags,
            job.get("description", "")[:1500],
        ]
    ).lower()

    if any(word in title_tags for word in important_words):
        return True

    # For multi-word queries, accept the job if any important word appears in
    # the description or tags. Stricter (2-word) checks tend to drop too many
    # cross-region jobs (German titles, non-English boards, etc.).
    return any(word in full_text for word in important_words)


def salary_range(min_salary, max_salary, currency: str = "$") -> str:
    values = [value for value in [min_salary, max_salary] if value not in {None, "", 0}]
    if not values:
        return ""
    if len(values) == 1:
        return f"{currency}{values[0]}"
    return f"{currency}{values[0]} - {currency}{values[1]}"


class RemotiveSource:
    """Remote jobs API without auth; useful as a production-safe non-LinkedIn source."""

    name = "remotive"

    def search(self, queries: list[str], preferences) -> list[dict]:
        jobs = []
        quotas = distribute_target(preferences.target_jobs, max(1, len(queries)))

        for query, quota in zip(queries, quotas):
            if quota <= 0:
                continue
            params = urllib.parse.urlencode({"search": query, "limit": min(quota, 50)})
            url = f"https://remotive.com/api/remote-jobs?{params}"
            try:
                request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8", errors="replace"))
            except Exception as exc:
                print(f"  remotive failed for '{query}': {exc}")
                continue

            for item in payload.get("jobs", [])[:quota]:
                description = clean_job_description(
                    BeautifulSoup(item.get("description", ""), "html.parser").get_text(" ", strip=True),
                    source=self.name,
                )
                jobs.append(
                    {
                        "title": clean_text(unescape(item.get("title", ""))),
                        "company": clean_text(unescape(item.get("company_name", ""))) or "Unknown",
                        "location": item.get("candidate_required_location", "Remote"),
                        "url": item.get("url", ""),
                        "description": description,
                        "source": self.name,
                        "posted_at": item.get("publication_date", ""),
                        "salary": item.get("salary", ""),
                        "workplace_type": "Remote",
                    }
                )
            print(f"  remotive '{query}': {len(jobs)} total jobs")

        return jobs


class RemoteOkSource:
    """RemoteOK public JSON feed. No login or API key required."""

    name = "remoteok"

    def search(self, queries: list[str], preferences) -> list[dict]:
        jobs = []
        quotas = distribute_target(preferences.target_jobs, max(1, len(queries)))

        for query, quota in zip(queries, quotas):
            raw_jobs = self.fetch_query_jobs(query)
            found = 0
            for item in raw_jobs:
                description = html_to_description(item.get("description", ""), self.name)
                job = {
                    "title": clean_text(unescape(item.get("position", ""))),
                    "company": clean_text(unescape(item.get("company", ""))) or "Unknown",
                    "location": item.get("location", "Remote") or "Remote",
                    "url": item.get("url") or item.get("apply_url") or "",
                    "description": description,
                    "source": self.name,
                    "posted_at": item.get("date", ""),
                    "salary": salary_range(item.get("salary_min"), item.get("salary_max")),
                    "workplace_type": "Remote",
                    "tags": item.get("tags", []) or [],
                }
                if not query_matches_job(query, job):
                    continue
                jobs.append(job)
                found += 1
                if found >= quota:
                    break
            print(f"  remoteok '{query}': {found} jobs")

        return jobs[: preferences.target_jobs]

    def fetch_query_jobs(self, query: str) -> list[dict]:
        words = important_query_words(query)
        tag_candidates = []
        if len(words) > 1:
            tag_candidates.append("-".join(words[:2]))
        tag_candidates.extend(words[:2])

        urls = [f"https://remoteok.com/remote-{urllib.parse.quote(tag)}-jobs.json" for tag in tag_candidates]
        urls.append("https://remoteok.com/api")

        seen = set()
        jobs = []
        for url in urls:
            try:
                request = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "application/json",
                    },
                )
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8", errors="replace"))
            except Exception as exc:
                print(f"  remoteok fetch failed for {url}: {exc}")
                continue

            for item in payload:
                if not isinstance(item, dict) or not item.get("position"):
                    continue
                key = item.get("id") or item.get("url") or item.get("slug")
                if key in seen:
                    continue
                seen.add(key)
                jobs.append(item)

            if jobs:
                break

        return jobs


class ArbeitnowSource:
    """Arbeitnow public job-board API. Europe/remote oriented, no key required."""

    name = "arbeitnow"

    def search(self, queries: list[str], preferences) -> list[dict]:
        jobs: list[dict] = []
        try:
            request = urllib.request.Request(
                "https://www.arbeitnow.com/api/job-board-api",
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            print(f"  arbeitnow failed: {exc}")
            return []

        raw_jobs = payload.get("data", []) if isinstance(payload, dict) else payload
        quotas = distribute_target(preferences.target_jobs, max(1, len(queries)))
        seen_urls: set[str] = set()

        for query, quota in zip(queries, quotas):
            found = 0
            for item in raw_jobs:
                url = item.get("url", "")
                if url in seen_urls:
                    continue
                description = html_to_description(item.get("description", ""), self.name)
                remote = bool(item.get("remote"))
                tags = [str(tag) for tag in (item.get("tags") or [])]
                job = {
                    "title": clean_text(unescape(item.get("title", ""))),
                    "company": clean_text(unescape(item.get("company_name", ""))) or "Unknown",
                    "location": clean_text(item.get("location", "")) or ("Remote" if remote else ""),
                    "url": url,
                    "description": description,
                    "source": self.name,
                    "posted_at": str(item.get("created_at", "")),
                    "workplace_type": "Remote" if remote else "",
                    "tags": tags,
                }
                if preferences.remote and not remote:
                    continue
                if query and not query_matches_job(query, job):
                    continue
                seen_urls.add(url)
                jobs.append(job)
                found += 1
                if found >= quota:
                    break
            print(f"  arbeitnow '{query}': {found} jobs")

        return jobs[: preferences.target_jobs]


class JSearchSource:
    """Optional RapidAPI JSearch adapter for Indeed/Google Jobs-style coverage."""

    name = "jsearch"

    def __init__(self):
        self.api_key = os.getenv("RAPIDAPI_KEY") or os.getenv("JSEARCH_API_KEY")

    def search(self, queries: list[str], preferences) -> list[dict]:
        if not self.api_key:
            print("Skipping JSearch: RAPIDAPI_KEY or JSEARCH_API_KEY is missing.")
            return []

        jobs = []
        quotas = distribute_target(preferences.target_jobs, max(1, len(queries)))
        for query, quota in zip(queries, quotas):
            if quota <= 0:
                continue

            search_query = query
            if preferences.location and preferences.location.lower() not in {"remote", "worldwide"}:
                search_query = f"{query} in {preferences.location}"

            params = {
                "query": search_query,
                "page": "1",
                "num_pages": "1",
            }
            if preferences.remote:
                params["remote_jobs_only"] = "true"
            if preferences.past_24h:
                params["date_posted"] = "today"

            url = f"https://jsearch.p.rapidapi.com/search?{urllib.parse.urlencode(params)}"
            request = urllib.request.Request(
                url,
                headers={
                    "X-RapidAPI-Key": self.api_key,
                    "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
                    "Accept": "application/json",
                    "User-Agent": USER_AGENT,
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8", errors="replace"))
            except Exception as exc:
                print(f"  jsearch failed for '{query}': {exc}")
                continue

            found = 0
            for item in payload.get("data", [])[:quota]:
                jobs.append(
                    {
                        "title": clean_text(unescape(item.get("job_title", ""))),
                        "company": clean_text(unescape(item.get("employer_name", ""))) or "Unknown",
                        "location": clean_text(
                            ", ".join(
                                part
                                for part in [
                                    item.get("job_city"),
                                    item.get("job_state"),
                                    item.get("job_country"),
                                ]
                                if part
                            )
                        ) or ("Remote" if item.get("job_is_remote") else ""),
                        "url": item.get("job_apply_link") or item.get("job_google_link") or "",
                        "description": clean_job_description(item.get("job_description", ""), source=self.name),
                        "source": self.name,
                        "posted_at": item.get("job_posted_at_datetime_utc", "") or item.get("job_posted_at_timestamp", ""),
                        "salary": salary_range(item.get("job_min_salary"), item.get("job_max_salary"), item.get("job_salary_currency") or "$"),
                        "employment_type": item.get("job_employment_type", ""),
                        "workplace_type": "Remote" if item.get("job_is_remote") else "",
                        "source_job_id": item.get("job_id"),
                    }
                )
                found += 1
            print(f"  jsearch '{query}': {found} jobs")

        return jobs[: preferences.target_jobs]


class ManualJobsSource:
    name = "manual"

    def __init__(self, path: str = "data/manual_jobs.json"):
        self.path = path

    def search(self, queries: list[str], preferences) -> list[dict]:
        if not os.path.exists(self.path):
            return []

        with open(self.path, "r", encoding="utf-8") as file:
            jobs = json.load(file)

        for job in jobs:
            job.setdefault("source", self.name)
        return jobs[: preferences.target_jobs]


class CouncilBoardSource:
    """Reads council/gov board URLs from config/job_boards.json."""

    name = "council_boards"

    def search(self, queries: list[str], preferences) -> list[dict]:
        config_path = os.path.join("config", "job_boards.json")
        if not os.path.exists(config_path):
            print("  council_boards: config/job_boards.json not found.")
            return []

        with open(config_path, "r", encoding="utf-8") as file:
            boards = json.load(file).get("boards", [])

        jobs = []
        for board in boards:
            if preferences.sector and board.get("sector") != preferences.sector:
                continue

            url = board.get("search_url_template", "").format(
                query=urllib.parse.quote_plus(queries[0] if queries else ""),
                location=urllib.parse.quote_plus(preferences.location or ""),
            )
            if not url:
                continue

            try:
                html = fetch_html(url)
                title_pattern = board.get("title_regex", r"<a[^>]+>([^<]{10,120})</a>")
                for match in list(re.finditer(title_pattern, html, flags=re.IGNORECASE))[: preferences.target_jobs]:
                    title = clean_text(unescape(match.group(1)))
                    detail_url = board.get("base_url", url)
                    jobs.append(
                        {
                            "title": title,
                            "company": board.get("name", "Council"),
                            "location": board.get("location", preferences.location),
                            "url": detail_url,
                            "description": fetch_detail_description(detail_url, self.name),
                            "source": self.name,
                            "sector": board.get("sector", "local_government"),
                        }
                    )
            except Exception as exc:
                print(f"  council_boards {board.get('name')}: {exc}")

        return jobs[: preferences.target_jobs]
