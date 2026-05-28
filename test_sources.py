"""Verify non-LinkedIn job sources actually return data."""

import json
import sys

from scraper.sources import JobSearchPreferences
from scraper.gov_sources import (
    ArbeitnowSource,
    RemoteOkSource,
    RemotiveSource,
)


def run(name: str, source, queries: list[str], preferences: JobSearchPreferences) -> int:
    print(f"\n=== {name} ===")
    try:
        jobs = source.search(queries, preferences)
    except Exception as exc:
        print(f"  {name} threw: {exc}")
        return 0

    print(f"  Returned {len(jobs)} jobs")
    for job in jobs[:3]:
        title = job.get("title", "(no title)")
        company = job.get("company", "(no company)")
        location = job.get("location", "")
        print(f"   - {title} @ {company} ({location})")
    return len(jobs)


def main() -> int:
    queries = ["Machine Learning Engineer", "Computer Vision", "Python Developer"]
    preferences = JobSearchPreferences(
        location="",
        remote=True,
        target_jobs=9,
        desired_role_level="entry-level",
        years_of_experience=1,
    )

    totals = {
        "remotive": run("remotive", RemotiveSource(), queries, preferences),
        "remoteok": run("remoteok", RemoteOkSource(), queries, preferences),
        "arbeitnow": run("arbeitnow", ArbeitnowSource(), queries, preferences),
    }

    print("\nTotals:", json.dumps(totals))
    passed = sum(1 for value in totals.values() if value > 0)
    print(f"{passed}/{len(totals)} non-LinkedIn sources returned jobs.")
    return 0 if passed >= 1 else 1


if __name__ == "__main__":
    sys.exit(main())
