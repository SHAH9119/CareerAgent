"""End-to-end smoke tests for CareerAgent. Hits real HTTP endpoints."""

import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000/api"
RESULTS: list[tuple[str, bool, str]] = []


def request(method: str, path: str, payload: dict | None = None, timeout: int = 30):
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


def expect(label: str, fn):
    try:
        result = fn()
        RESULTS.append((label, True, ""))
        return result
    except Exception as exc:
        body = ""
        if isinstance(exc, urllib.error.HTTPError):
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
        RESULTS.append((label, False, f"{exc} {body}".strip()))
        print(f"FAIL {label}: {exc} {body}")
        return None


def main() -> int:
    print("Running CareerAgent smoke tests against", BASE)

    expect("/api/health is up", lambda: assert_keys(request("GET", "/health"), ["status"]))

    profile = expect("/api/profile returns parsed profile", lambda: request("GET", "/profile"))
    if profile:
        assert profile.get("name"), "profile is missing a name"

    sources = expect("/api/sources lists data sources", lambda: request("GET", "/sources"))
    if sources:
        assert sources.get("sources"), "no sources reported"
        labels = {item["id"] for item in sources["sources"]}
        for required in {"remotive", "remoteok", "arbeitnow", "adzuna", "jsearch", "manual"}:
            assert required in labels, f"source {required} missing"

    summary = expect("/api/summary returns aggregated data", lambda: request("GET", "/summary"))
    if summary:
        for key in ("apply", "maybe", "skip"):
            assert key in summary, f"missing key {key} in summary"

    domain_payload = {
        "path": "config/candidates/active.json",
        "config": {
            "primary_domain": "ai_ml_software",
            "score_weights": {
                "semantic": 0.3,
                "domain": 0.25,
                "seniority": 0.15,
                "skills": 0.15,
                "requirements": 0.10,
                "job_quality": 0.05,
            },
            "decision_thresholds": {
                "apply_min_final": 60,
                "maybe_min_final": 42,
                "maybe_min_domain": 45,
                "skip_max_domain": 30,
            },
        },
    }
    saved = expect("POST /api/domain-config saves active config", lambda: request("POST", "/domain-config", domain_payload))
    if saved:
        assert saved.get("path") == "config/candidates/active.json"

    expect(
        "POST /api/domain-config rejects empty payload",
        lambda: assert_rejects(
            lambda: request("POST", "/domain-config", {"path": "config/candidates/active.json", "config": {}}),
            400,
        ),
    )

    expect("GET /api/domain-config returns merged rules", lambda: assert_keys(request("GET", "/domain-config"), ["score_weights", "decision_thresholds"]))

    drafts_before = expect("/api/tailor/drafts lists drafts", lambda: request("GET", "/tailor/drafts"))
    if summary and summary.get("apply"):
        job = summary["apply"][0]
    elif summary and summary.get("maybe"):
        job = summary["maybe"][0]
    else:
        job = None

    if job:
        draft = expect("POST /api/tailor/draft creates a draft", lambda: request("POST", "/tailor/draft", {"job": job}, timeout=120))
        if draft and draft.get("id"):
            draft_id = draft["id"]
            expect(
                "POST /api/tailor/status moves draft to review",
                lambda: request("POST", "/tailor/status", {"draft_id": draft_id, "status": "review", "notes": "smoke test"}),
            )
            expect(
                "POST /api/tailor/status moves draft to approved",
                lambda: request("POST", "/tailor/status", {"draft_id": draft_id, "status": "approved", "notes": "smoke test approved"}),
            )

    run = expect(
        "POST /api/run-agent kicks off agent with manual+existing sources",
        lambda: request(
            "POST",
            "/run-agent",
            {
                "resume_path": "my_resume.pdf",
                "sources": ["manual", "existing"],
                "target_jobs": 5,
                "location": "",
                "remote": True,
                "past_24h": False,
                "skip_parse": True,
                "skip_scrape": False,
                "custom_queries": [],
                "use_db": True,
            },
        ),
    )
    if run:
        for _ in range(120):
            status = request("GET", "/run-agent/status")
            if status.get("stage") in {"succeeded", "failed"}:
                break
            time.sleep(2)
        final_status = request("GET", "/run-agent/status")
        RESULTS.append(("Agent run reaches a terminal state", final_status.get("stage") in {"succeeded", "failed"}, final_status.get("message", "")))

    print("\nResults:")
    passed = 0
    for label, ok, detail in RESULTS:
        marker = "OK  " if ok else "FAIL"
        print(f"  {marker} {label}{(' - ' + detail) if detail else ''}")
        if ok:
            passed += 1

    print(f"\n{passed}/{len(RESULTS)} checks passed.")
    return 0 if passed == len(RESULTS) else 1


def assert_keys(value, keys):
    assert isinstance(value, dict), f"expected dict, got {type(value).__name__}"
    for key in keys:
        assert key in value, f"missing key {key}"
    return value


def assert_rejects(fn, expected_status):
    try:
        fn()
    except urllib.error.HTTPError as exc:
        assert exc.code == expected_status, f"expected {expected_status}, got {exc.code}"
        return True
    raise AssertionError(f"expected HTTP {expected_status}, request succeeded")


if __name__ == "__main__":
    sys.exit(main())
