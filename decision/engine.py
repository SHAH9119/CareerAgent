import json
import os
from collections import Counter

from dotenv import load_dotenv

from llm import llm_json
from matcher.domain_config import load_domain_config
from scraper.utils import safe_join

load_dotenv()


def assign_decisions(scored_jobs: list, profile: dict | None = None) -> list:
    """Assign Apply/Maybe/Skip using final fit, not semantic score alone."""
    print("Assigning decisions based on final fit scores...")
    thresholds = load_domain_config(profile).get("decision_thresholds", {})
    apply_min = thresholds.get("apply_min_final", 62)
    maybe_min = thresholds.get("maybe_min_final", 45)
    maybe_domain = thresholds.get("maybe_min_domain", 50)
    skip_domain = thresholds.get("skip_max_domain", 40)

    for job in scored_jobs:
        fit = job.get("fit", {})
        score = job.get("final_score", job.get("match_score", 0))
        domain_fit = fit.get("domain_fit", 50)
        domain_label = fit.get("domain_label", "unknown_domain")
        seniority_label = fit.get("seniority_label", "aligned")
        blockers = fit.get("required_blockers", [])
        wrong_domain_gaps = fit.get("wrong_domain_gaps", [])

        reasons = []
        if domain_label == "wrong_domain" or domain_fit < skip_domain:
            job["decision"] = "SKIP"
            reasons.append("wrong or weak domain fit")
        elif score >= apply_min and not blockers and seniority_label not in {"too_senior", "too_junior"}:
            job["decision"] = "APPLY"
            if seniority_label == "stretch":
                reasons.append("strong fit; role is a level stretch but reachable")
            else:
                reasons.append("strong overall fit")
        elif score >= maybe_min and domain_fit >= maybe_domain:
            job["decision"] = "MAYBE"
            if blockers:
                reasons.append("possible hard requirements to verify")
            if seniority_label in {"too_senior", "too_junior", "slightly_junior"}:
                reasons.append(f"seniority mismatch: {seniority_label}")
            if wrong_domain_gaps:
                reasons.append("some missing items are outside target domain")
            if not reasons:
                reasons.append("relevant role with some gaps")
        else:
            job["decision"] = "SKIP"
            reasons.append("overall fit is too weak")

        job["decision_reason"] = "; ".join(reasons)

    apply_count = sum(1 for job in scored_jobs if job["decision"] == "APPLY")
    maybe_count = sum(1 for job in scored_jobs if job["decision"] == "MAYBE")
    skip_count = sum(1 for job in scored_jobs if job["decision"] == "SKIP")

    print(f"  APPLY: {apply_count} jobs")
    print(f"  MAYBE: {maybe_count} jobs")
    print(f"  SKIP:  {skip_count} jobs")

    return scored_jobs


def skill_advice_jobs(scored_jobs: list) -> list:
    """Use only relevant jobs for learning advice."""
    fit_jobs = []
    for job in scored_jobs:
        fit = job.get("fit", {})
        if job.get("decision") not in {"APPLY", "MAYBE"}:
            continue
        if fit.get("domain_label") == "wrong_domain" or fit.get("domain_fit", 0) < 50:
            continue
        if fit.get("seniority_label") == "too_junior":
            continue
        fit_jobs.append(job)

    if not fit_jobs:
        fit_jobs = [job for job in scored_jobs if job.get("decision") in {"APPLY", "MAYBE"}]

    return sorted(fit_jobs, key=lambda item: item.get("final_score", item.get("match_score", 0)), reverse=True)[:10]


def fallback_skill_advice(profile: dict, top_jobs: list) -> dict:
    """Create useful advice without spending another LLM call."""
    candidate_text = json.dumps(profile, ensure_ascii=False).lower()
    counter = Counter()
    examples = {}

    for job in top_jobs:
        fit = job.get("fit", {})
        gaps = fit.get("required_blockers", []) + fit.get("nice_to_have_gaps", []) + job.get("missing_skills", [])
        for gap in gaps:
            value = str(gap).strip()
            if not value or value.lower() in candidate_text:
                continue
            counter[value] += 1
            examples.setdefault(value, job.get("title", "fit jobs"))

    top_items = []
    for skill, count in counter.most_common(5):
        top_items.append(
            {
                "skill": skill,
                "reason": f"Appears as a missing requirement in {count} relevant job(s), including {examples.get(skill)}.",
                "appears_in_jobs": count,
            }
        )

    summary = (
        "Generated without an extra LLM call because provider quota was unavailable. "
        "Focus on repeated gaps from the Apply/Maybe jobs first."
    )
    return {"top_skills_to_learn": top_items, "summary": summary}


def get_global_skill_gaps(profile: dict, scored_jobs: list) -> dict:
    """Analyze only fit jobs and find practical skills to learn."""
    print("\nAnalyzing global skill gaps across fit jobs...")

    top_jobs = skill_advice_jobs(scored_jobs)

    candidate_evidence = json.dumps(
        {
            "skills": profile.get("skills", []),
            "education": profile.get("education", []),
            "work_experience": profile.get("work_experience", []),
            "projects": profile.get("projects", []),
            "target_roles": profile.get("job_titles", []),
        },
        ensure_ascii=False,
    )

    all_missing = []
    top_descriptions = []
    for job in top_jobs:
        fit = job.get("fit", {})
        useful_gaps = fit.get("required_blockers", []) + fit.get("nice_to_have_gaps", [])
        all_missing.extend(useful_gaps)
        top_descriptions.append(
            f"Job: {job.get('title')} at {job.get('company')} "
            f"(Final: {job.get('final_score', job.get('match_score'))}%, "
            f"Domain: {fit.get('domain_fit')}, Seniority: {fit.get('seniority_label')})\n"
            f"Useful gaps: {safe_join(useful_gaps)}"
        )

    if not all_missing:
        return {
            "top_skills_to_learn": [],
            "summary": "No repeated practical skill gaps were found across the fit jobs.",
        }

    if os.getenv("LLM_GLOBAL_SKILL_ADVICE", "1").lower() in {"0", "false", "no"}:
        return fallback_skill_advice(profile, top_jobs)

    prompt = f"""
You are a career advisor analyzing a job seeker's skill gaps.

Candidate evidence:
{candidate_evidence}

Fit jobs only:
{safe_join(top_descriptions[:8], chr(10))}

Useful missing skills across fit jobs: {safe_join(all_missing)}

Identify the TOP 5 practical skills this candidate should learn to improve matches.

Rules:
- Only use gaps from fit jobs above.
- Do not recommend skills, degrees, education, tools, or experience already shown in candidate evidence.
- Do not recommend wrong-domain skills.
- Focus on practical, learnable gaps that help the candidate's target roles.

Return ONLY a JSON object like this:
{{
    "top_skills_to_learn": [
        {{
            "skill": "skill name",
            "reason": "one sentence why this matters",
            "appears_in_jobs": 3
        }}
    ],
    "summary": "2 sentence overall career advice for this candidate"
}}
"""

    try:
        return llm_json(prompt, system="You are a career advisor and return only valid JSON.", temperature=0)
    except Exception as exc:
        print(f"  Global skill gap analysis failed: {exc}")
        return fallback_skill_advice(profile, top_jobs)


def deduplicate(jobs: list) -> list:
    seen = set()
    unique = []
    for job in jobs:
        key = f"{job.get('title', '')}_{job.get('company', '')}".lower()
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique


def run_decision_engine(profile: dict, scored_jobs: list) -> dict:
    """Run decisions and career advice."""
    print("\n" + "=" * 50)
    print("DECISION ENGINE STARTING")
    print("=" * 50)

    jobs_with_decisions = assign_decisions(scored_jobs, profile)
    skill_advice = get_global_skill_gaps(profile, jobs_with_decisions)

    apply_jobs = deduplicate([job for job in jobs_with_decisions if job["decision"] == "APPLY"])
    maybe_jobs = deduplicate([job for job in jobs_with_decisions if job["decision"] == "MAYBE"])
    skip_jobs = deduplicate([job for job in jobs_with_decisions if job["decision"] == "SKIP"])

    print("\nTOP SKILLS TO LEARN:")
    for item in skill_advice.get("top_skills_to_learn", []):
        print(f"  - {item['skill']}: {item['reason']}")

    print(f"\nCareer Advice: {skill_advice.get('summary', '')}")

    return {
        "apply": apply_jobs,
        "maybe": maybe_jobs,
        "skip": skip_jobs,
        "skill_advice": skill_advice,
        "summary": {
            "total_jobs_analyzed": len(scored_jobs),
            "apply_count": len(apply_jobs),
            "maybe_count": len(maybe_jobs),
            "skip_count": len(skip_jobs),
        },
    }


if __name__ == "__main__":
    with open("data/profile.json", "r", encoding="utf-8") as file:
        profile = json.load(file)

    with open("data/scored_jobs.json", "r", encoding="utf-8") as file:
        scored_jobs = json.load(file)

    print(f"Profile: {profile['name']}")
    print(f"Scored jobs loaded: {len(scored_jobs)}")

    result = run_decision_engine(profile, scored_jobs)

    os.makedirs("data", exist_ok=True)
    with open("data/decisions.json", "w", encoding="utf-8") as file:
        json.dump(result, file, indent=2)

    print("\n" + "=" * 50)
    print("FINAL SUMMARY")
    print("=" * 50)
    print(f"Total analyzed: {result['summary']['total_jobs_analyzed']}")
    print(f"APPLY:  {result['summary']['apply_count']} jobs")
    print(f"MAYBE:  {result['summary']['maybe_count']} jobs")
    print(f"SKIP:   {result['summary']['skip_count']} jobs")

    print("\nAPPLY LIST:")
    for job in result["apply"]:
        print(f"  - {job['title']} @ {job['company']} ({job.get('final_score', job.get('match_score'))}%)")

    print("\nMAYBE LIST:")
    for job in result["maybe"]:
        print(f"  - {job['title']} @ {job['company']} ({job.get('final_score', job.get('match_score'))}%)")

    print("\nResults saved to data/decisions.json")
