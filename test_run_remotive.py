"""Drive a full pipeline run against Remotive + RemoteOK and report stats."""

import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8000/api"


def request(method: str, path: str, payload: dict | None = None, timeout: int = 600):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8") or "{}"
        return json.loads(raw)


def main() -> int:
    request(
        "POST",
        "/run-agent",
        {
            "resume_path": "my_resume.pdf",
            "sources": ["remotive", "remoteok"],
            "target_jobs": 15,
            "location": "",
            "remote": True,
            "past_24h": False,
            "skip_parse": True,
            "skip_scrape": False,
            "custom_queries": ["Machine Learning Engineer", "Computer Vision", "Python Developer"],
            "use_db": True,
        },
    )

    started = time.time()
    while time.time() - started < 600:
        status = request("GET", "/run-agent/status")
        stage = status.get("stage")
        print(f"  [{int(time.time() - started)}s] stage={stage} msg={status.get('message')}")
        if stage in {"succeeded", "failed"}:
            break
        time.sleep(3)

    final = request("GET", "/run-agent/status")
    print("\nFinal status:", json.dumps(final, indent=2))

    summary = request("GET", "/summary")
    apply_jobs = summary.get("apply", [])
    maybe_jobs = summary.get("maybe", [])
    skip_jobs = summary.get("skip", [])
    print(f"APPLY: {len(apply_jobs)}, MAYBE: {len(maybe_jobs)}, SKIP: {len(skip_jobs)}")

    for label, group in [("APPLY", apply_jobs), ("MAYBE", maybe_jobs[:3])]:
        for job in group:
            print(f"  {label}: {job.get('title')} @ {job.get('company')} score={job.get('final_score')}")

    return 0 if final.get("stage") == "succeeded" else 1


if __name__ == "__main__":
    sys.exit(main())
