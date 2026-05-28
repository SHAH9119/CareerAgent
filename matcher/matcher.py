from sentence_transformers import SentenceTransformer, util
from dotenv import load_dotenv
import json
import os
import re

from llm import llm_json
from matcher.domain_config import load_domain_config
from matcher.fit_evaluator import evaluate_fit, score_domain

load_dotenv()

# Load model once; this downloads on first run (~90MB).
print("Loading semantic model...")
model = SentenceTransformer("all-MiniLM-L6-v2")
print("Model ready.")


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def build_resume_text(profile: dict) -> str:
    """Convert profile dict into one rich text blob for embedding"""
    parts = []

    parts.append(f"Name: {profile.get('name', '')}")
    parts.append(f"Years of experience: {profile.get('years_of_experience', 0)}")

    titles = profile.get("job_titles", [])
    if titles:
        parts.append(f"Target roles: {', '.join(titles)}")

    skills = profile.get("skills", [])
    if skills:
        parts.append(f"Skills: {', '.join(skills)}")

    for exp in profile.get("work_experience", []):
        parts.append(f"Work: {exp['title']} at {exp['company']}. {exp['description']}")

    for proj in profile.get("projects", []):
        techs = ", ".join(proj.get("technologies", []))
        parts.append(f"Project: {proj['name']} using {techs}. {proj['description']}")

    edu = profile.get("education", [])
    if edu:
        for e in edu:
            parts.append(f"Education: {e.get('degree', '')} from {e.get('institution', '')}")

    return " | ".join(parts)


def build_job_text(job: dict) -> str:
    """Use cleaned job fields for embedding and LLM analysis."""
    parts = [
        f"Title: {job.get('title', '')}",
        f"Company: {job.get('company', '')}",
        f"Location: {job.get('location', '')}",
        f"Seniority: {job.get('seniority_level', '')}",
        f"Employment type: {job.get('employment_type', '')}",
        f"Posted: {job.get('posted_at', '')}",
        f"Applicants: {job.get('applicants', '')}",
        f"Description: {job.get('description', '')}",
    ]
    return " | ".join(part for part in parts if part and not part.endswith(": "))


def candidate_evidence_text(profile: dict) -> str:
    return normalize(build_resume_text(profile))


def configured_requirement_terms(profile: dict) -> list[str]:
    """Build the list of skill/requirement terms used by the heuristic gap fallback.

    Pulls from the active domain config (so it is candidate- and country-agnostic)
    plus a small set of universally applicable signal terms.
    """
    rules = load_domain_config(profile)
    primary_domain = rules.get("primary_domain", "")
    terms: list[str] = []
    terms.extend(rules.get("domain_groups", {}).get(primary_domain, []))
    terms.extend(rules.get("target_title_terms", {}).get(primary_domain, []))
    terms.extend(rules.get("requirement_signal_terms", []) or [])
    terms.extend(profile.get("skills", []) or [])

    unique: list[str] = []
    for term in terms:
        value = normalize(term)
        if value and value not in unique:
            unique.append(value)
    return unique


def configured_hard_requirements(profile: dict) -> list[str]:
    """Universal hard-requirement keywords (visa, work rights, etc.) plus config overrides."""
    rules = load_domain_config(profile)
    base = [
        "work rights",
        "working rights",
        "right to work",
        "visa",
        "citizen",
        "permanent resident",
        "security clearance",
    ]
    extras = rules.get("hard_requirement_keywords", []) or []
    seen: list[str] = []
    for item in base + list(extras):
        value = normalize(item)
        if value and value not in seen:
            seen.append(value)
    return seen


def heuristic_skill_gap(profile: dict, job: dict, reason: str = "deterministic fallback") -> dict:
    """Cheap skill-gap fallback for quota failures and obvious low-fit jobs."""
    candidate_text = candidate_evidence_text(profile)
    job_text_value = normalize(build_job_text(job))
    required: list[str] = []
    matched: list[str] = []
    missing: list[str] = []

    for term in configured_requirement_terms(profile):
        if term in job_text_value:
            label = term.title() if len(term) > 4 else term.upper()
            required.append(label)
            if term in candidate_text:
                matched.append(label)
            else:
                missing.append(label)

    normalized_required = {normalize(item) for item in required}
    for blocker in configured_hard_requirements(profile):
        if blocker in job_text_value and blocker not in normalized_required:
            label = blocker.title()
            required.append(label)
            if blocker in candidate_text:
                matched.append(label)
            else:
                missing.append(label)

    if not required:
        title_terms = [part.strip() for part in re.split(r"[/|,-]", job.get("title", "")) if len(part.strip()) > 3]
        required = title_terms[:3]

    return {
        "required_skills": required[:8],
        "matched_skills": matched[:8],
        "missing_skills": missing[:8],
        "recommendation": f"Used {reason}; verify the job manually if it looks important.",
        "gap_source": "fallback",
    }


def normalize_gap(gap: dict, source: str) -> dict:
    return {
        "required_skills": gap.get("required_skills", []) or [],
        "matched_skills": gap.get("matched_skills", []) or [],
        "missing_skills": gap.get("missing_skills", []) or [],
        "recommendation": gap.get("recommendation", "") or "No recommendation returned.",
        "gap_source": gap.get("gap_source", source),
    }


def get_skill_gap(profile: dict, job: dict, use_llm: bool = True) -> dict:
    """Ask the configured LLM to analyze skill gap between profile and job."""
    if not use_llm:
        return heuristic_skill_gap(profile, job, reason="LLM budget skipped")

    candidate_profile = build_resume_text(profile)
    job_desc = build_job_text(job)[:3500]  # limit tokens

    prompt = f"""
You are a recruiter analyzing a candidate's fit for a job.

Candidate profile:
{candidate_profile}

Job description (excerpt):
{job_desc}

Rules:
- Only mark something as missing if it is not present anywhere in the candidate profile.
- Treat degrees, education, work history, projects, tools, and domain experience as candidate evidence.
- If the job lists a degree or general field (e.g. "Bachelor in Engineering" or "STEM degree") and the candidate's profile shows any matching degree, count it as matched, not missing.
- Keep missing_skills focused on concrete, actionable gaps the candidate could realistically close.

Return ONLY a JSON object like this (no markdown, no extra text):
{{
    "required_skills": ["skills the job clearly requires"],
    "matched_skills": ["skills candidate HAS that job needs"],
    "missing_skills": ["skills job needs that candidate is MISSING"],
    "recommendation": "one sentence on fit"
}}
"""

    try:
        gap = llm_json(prompt, system="You are a recruiter and return only valid JSON.", temperature=0)
        return normalize_gap(gap, "llm")
    except Exception as e:
        print(f"  Skill gap analysis failed: {e}")
        return heuristic_skill_gap(profile, job, reason="LLM failed")


def match_jobs(profile: dict, jobs: list) -> list:
    """Core matching engine: scores every job against the resume."""

    print("\nBuilding resume embedding...")
    resume_text = build_resume_text(profile)
    resume_embedding = model.encode(resume_text, convert_to_tensor=True)

    print(f"Scoring {len(jobs)} jobs...\n")
    scored_jobs = []
    max_llm_gap_calls = env_int("LLM_SKILL_GAP_LIMIT", 5)
    llm_gap_calls = 0

    for i, job in enumerate(jobs):
        title = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        description = job.get("description", "")

        if not description:
            print(f"  [{i+1}] Skipping '{title}' - no description")
            continue

        # Combine title + description for richer job embedding
        job_text = build_job_text(job)
        job_embedding = model.encode(job_text, convert_to_tensor=True)

        # Cosine similarity gives a score between 0 and 1.
        similarity = util.cos_sim(resume_embedding, job_embedding).item()
        match_score = round(similarity * 100, 1)  # convert to percentage

        print(f"  [{i+1}/{len(jobs)}] {title} @ {company}")
        print(f"    Match Score: {match_score}%")

        # Get skill gap analysis
        domain_fit, domain_label, _, _ = score_domain(profile, job)
        use_llm_gap = (
            llm_gap_calls < max_llm_gap_calls
            and domain_label != "wrong_domain"
            and domain_fit >= 50
        )
        if use_llm_gap:
            llm_gap_calls += 1
        gap = get_skill_gap(profile, job, use_llm=use_llm_gap)
        fit = evaluate_fit(profile, job, match_score, gap)
        print(f"    Fit Score: {fit['final_score']}%")
        print(f"    Gap Source: {gap.get('gap_source', 'unknown')}")
        print(f"    Matched: {', '.join(gap['matched_skills'][:3])}")
        print(f"    Missing: {', '.join(gap['missing_skills'][:3])}")

        scored_jobs.append({
            **job,
            "match_score": match_score,
            "final_score": fit["final_score"],
            "fit": fit,
            "matched_skills": gap["matched_skills"],
            "missing_skills": gap["missing_skills"],
            "required_skills": gap["required_skills"],
            "recommendation": gap["recommendation"],
            "gap_source": gap.get("gap_source", "unknown")
        })

    # Sort by score highest first
    scored_jobs.sort(key=lambda x: x.get("final_score", x.get("match_score", 0)), reverse=True)
    return scored_jobs


if __name__ == "__main__":
    # Load profile
    with open("data/profile.json", "r", encoding="utf-8") as f:
        profile = json.load(f)

    # Load jobs
    with open("data/jobs.json", "r", encoding="utf-8") as f:
        jobs = json.load(f)

    print(f"Profile: {profile['name']}")
    print(f"Jobs to score: {len(jobs)}")

    scored = match_jobs(profile, jobs)

    # Save results
    os.makedirs("data", exist_ok=True)
    with open("data/scored_jobs.json", "w", encoding="utf-8") as f:
        json.dump(scored, f, indent=2)

    # Print top 10
    print("\n\n===== TOP 10 MATCHES =====")
    for i, job in enumerate(scored[:10]):
        print(f"\n#{i+1} {job['title']} @ {job['company']}")
        print(f"   Score: {job['match_score']}%")
        print(f"   Missing: {', '.join(job['missing_skills'][:3]) or 'None'}")
        print(f"   Verdict: {job['recommendation']}")

    print("\nScored jobs saved to data/scored_jobs.json")
