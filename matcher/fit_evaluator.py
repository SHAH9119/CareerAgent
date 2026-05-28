import re

from matcher.domain_config import load_domain_config


DOMAIN_GROUPS: dict[str, list[str]] = {}
WRONG_DOMAIN_TITLE_PATTERNS: dict[str, list[str]] = {}
TARGET_TITLE_TERMS: dict[str, list[str]] = {}

DEFAULT_BLOCKER_PATTERNS = [
    "work rights",
    "working rights",
    "right to work",
    "citizen",
    "permanent resident",
    "visa",
    "security clearance",
]

NICE_TO_HAVE_HINTS = ["desirable", "nice to have", "preferred", "advantage", "beneficial"]


def blocker_patterns(rules: dict | None = None) -> list[str]:
    extras = (rules or {}).get("hard_requirement_keywords", []) or []
    seen: list[str] = []
    for pattern in DEFAULT_BLOCKER_PATTERNS + list(extras):
        value = pattern.strip().lower()
        if value and value not in seen:
            seen.append(value)
    return seen


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def profile_text(profile: dict) -> str:
    parts = [
        " ".join(profile.get("job_titles", [])),
        " ".join(profile.get("job_search_keywords", [])),
        " ".join(profile.get("skills", [])),
        profile.get("summary", ""),
        profile.get("career_stage", ""),
        profile.get("desired_role_level", ""),
    ]

    for item in profile.get("education", []):
        parts.extend([item.get("degree", ""), item.get("institution", "")])
    for item in profile.get("work_experience", []):
        parts.extend([item.get("title", ""), item.get("company", ""), item.get("description", "")])
    for item in profile.get("projects", []):
        parts.extend([item.get("name", ""), item.get("description", ""), " ".join(item.get("technologies", []))])

    return normalize(" ".join(parts))


def job_text(job: dict) -> str:
    return normalize(
        " ".join(
            [
                job.get("title", ""),
                job.get("company", ""),
                job.get("location", ""),
                job.get("employment_type", ""),
                job.get("seniority_level", ""),
                job.get("description", ""),
            ]
        )
    )


def get_rules(profile: dict | None = None) -> dict:
    return load_domain_config(profile)


def detect_domains(text: str, domain_groups: dict | None = None) -> set[str]:
    groups = domain_groups or DOMAIN_GROUPS
    found = set()
    haystack = normalize(text)
    for domain, terms in groups.items():
        if any(
            re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", haystack)
            for term in terms
        ):
            found.add(domain)
    return found


def contains_any(text: str, terms: list[str]) -> bool:
    haystack = normalize(text)
    return any(re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", haystack) for term in terms)


def infer_job_level(job: dict) -> tuple[int, str]:
    text = job_text(job)
    title = normalize(job.get("title", ""))
    seniority = normalize(job.get("seniority_level", ""))
    combined = f"{title} {seniority}"

    if any(term in combined for term in ["intern", "internship", "apprentice"]):
        return 0, "internship"
    if any(term in combined for term in ["graduate", "entry level", "entry-level", "trainee"]):
        return 1, "graduate_entry"
    if "junior" in combined:
        return 2, "junior"
    if any(term in combined for term in ["principal", "director", "head of"]):
        return 5, "principal"
    if any(term in combined for term in ["senior", "lead", "manager"]):
        return 4, "senior"
    if "associate" in combined:
        return 3, "associate_mid"
    if "mid-senior" in text:
        return 4, "senior"
    return 3, "mid"


def infer_candidate_level(profile: dict) -> tuple[int, str]:
    desired = normalize(profile.get("desired_role_level", ""))
    years = profile.get("years_of_experience", 0) or 0

    if "intern" in desired:
        return 0, "internship"
    if any(term in desired for term in ["entry", "graduate"]):
        return 1, "entry"
    if "junior" in desired:
        return 2, "junior"
    if "senior" in desired:
        return 4, "senior"
    if years >= 8:
        return 4, "senior"
    if years >= 3:
        return 3, "mid"
    if years >= 1:
        return 2, "junior"
    return 1, "entry"


def score_seniority(profile: dict, job: dict) -> tuple[int, str]:
    candidate_level, candidate_label = infer_candidate_level(profile)
    job_level, job_label = infer_job_level(job)
    diff = job_level - candidate_level

    if diff == 0:
        return 100, "aligned"
    if diff == 1:
        return 75, "slight_stretch"
    if diff == 2:
        return 60, "stretch"
    if diff >= 3:
        return 40, "too_senior"
    if diff == -1:
        return 70, "slightly_junior"
    return 50, "too_junior"


def score_domain(profile: dict, job: dict, rules: dict | None = None) -> tuple[int, str, set[str], set[str]]:
    rules = rules or get_rules(profile)
    domain_groups = rules.get("domain_groups", DOMAIN_GROUPS)
    wrong_patterns = rules.get("wrong_domain_title_patterns", WRONG_DOMAIN_TITLE_PATTERNS)
    target_title_map = rules.get("target_title_terms", TARGET_TITLE_TERMS)

    primary_domain = rules.get("primary_domain")
    candidate_domains = {primary_domain} if primary_domain else detect_domains(profile_text(profile), domain_groups)
    job_domains = detect_domains(job_text(job), domain_groups)
    title = normalize(job.get("title", ""))

    for wrong_domain, terms in wrong_patterns.items():
        if contains_any(title, terms) and wrong_domain not in candidate_domains:
            allowed_title_terms = []
            for domain in candidate_domains:
                allowed_title_terms.extend(target_title_map.get(domain, []))
            allowed_title_terms = [
                term
                for term in allowed_title_terms
                if term.lower() not in {"civil", "engineer", "project engineer", "planning engineer"}
            ]
            if not contains_any(title, allowed_title_terms):
                job_domains.add(wrong_domain)
                return 15, "wrong_domain", candidate_domains, job_domains

    if not job_domains:
        return 55, "unknown_domain", candidate_domains, job_domains

    overlap = candidate_domains & job_domains
    if overlap:
        extra_domains = job_domains - candidate_domains
        score = min(100, 70 + 10 * len(overlap) - 10 * len(extra_domains))
        score = max(45, score)
        return score, "aligned", candidate_domains, job_domains

    return 25, "wrong_domain", candidate_domains, job_domains


def classify_missing_skills(profile: dict, job: dict, missing_skills: list[str], rules: dict | None = None) -> dict:
    rules = rules or get_rules(profile)
    domain_groups = rules.get("domain_groups", DOMAIN_GROUPS)
    primary_domain = rules.get("primary_domain")
    candidate_domains = {primary_domain} if primary_domain else detect_domains(profile_text(profile), domain_groups)
    job_domains = detect_domains(job_text(job), domain_groups)
    blocker_terms = blocker_patterns(rules)
    classifications = {
        "required_blockers": [],
        "nice_to_have_gaps": [],
        "wrong_domain_gaps": [],
    }

    for skill in missing_skills:
        skill_text = normalize(skill)
        skill_domains = detect_domains(skill_text, domain_groups)

        if skill_domains and not (skill_domains & candidate_domains):
            classifications["wrong_domain_gaps"].append(skill)
        elif any(pattern in skill_text for pattern in blocker_terms):
            classifications["required_blockers"].append(skill)
        elif any(hint in normalize(job.get("description", "")) for hint in NICE_TO_HAVE_HINTS):
            classifications["nice_to_have_gaps"].append(skill)
        elif job_domains and not (job_domains & candidate_domains):
            classifications["wrong_domain_gaps"].append(skill)
        else:
            classifications["nice_to_have_gaps"].append(skill)

    return classifications


def score_requirements(classifications: dict) -> int:
    blocker_penalty = 20 * len(classifications.get("required_blockers", []))
    wrong_domain_penalty = 15 * len(classifications.get("wrong_domain_gaps", []))
    return max(0, 100 - blocker_penalty - wrong_domain_penalty)


def score_skills(matched: list[str], missing: list[str], classifications: dict) -> int:
    actionable_missing = len(classifications.get("required_blockers", [])) + len(classifications.get("nice_to_have_gaps", []))
    denominator = len(matched) + actionable_missing
    if denominator == 0:
        return 55

    return round((len(matched) / denominator) * 100)


def score_job_quality(job: dict) -> int:
    score = 55
    text = normalize(" ".join([job.get("posted_at", ""), job.get("applicants", ""), job.get("salary", "")]))

    if re.search(r"\b(\d+)\s+(minute|hour|day)s?\s+ago\b", text):
        score += 15
    elif re.search(r"\b(\d+)\s+week", text):
        score += 5

    applicant_match = re.search(r"(\d+)\s+(?:applicants|people clicked apply)", text)
    if applicant_match:
        applicants = int(applicant_match.group(1))
        if applicants <= 25:
            score += 10
        elif applicants >= 200:
            score -= 10

    if job.get("salary"):
        score += 5

    return max(0, min(100, score))


def evaluate_fit(profile: dict, job: dict, semantic_score: float, gap: dict) -> dict:
    rules = get_rules(profile)
    weights = rules.get("score_weights", {})
    domain_fit, domain_label, candidate_domains, job_domains = score_domain(profile, job, rules)
    seniority_fit, seniority_label = score_seniority(profile, job)
    classifications = classify_missing_skills(profile, job, gap.get("missing_skills", []), rules)
    requirements_fit = score_requirements(classifications)
    skills_fit = score_skills(gap.get("matched_skills", []), gap.get("missing_skills", []), classifications)
    job_quality_score = score_job_quality(job)

    final_score = round(
        (semantic_score * weights.get("semantic", 0.30))
        + (domain_fit * weights.get("domain", 0.25))
        + (seniority_fit * weights.get("seniority", 0.15))
        + (skills_fit * weights.get("skills", 0.15))
        + (requirements_fit * weights.get("requirements", 0.10))
        + (job_quality_score * weights.get("job_quality", 0.05)),
        1,
    )

    notes = []
    if domain_label == "wrong_domain":
        notes.append("Job appears to be outside the candidate's target domain.")
    if seniority_label == "too_senior":
        notes.append("Role appears too senior for the candidate's current level.")
    if seniority_label == "too_junior":
        notes.append("Role appears below the candidate's current level.")
    if classifications["required_blockers"]:
        notes.append("Role has possible hard requirements to verify.")

    return {
        "semantic_score": semantic_score,
        "domain_fit": domain_fit,
        "domain_label": domain_label,
        "candidate_domains": sorted(candidate_domains),
        "job_domains": sorted(job_domains),
        "seniority_fit": seniority_fit,
        "seniority_label": seniority_label,
        "skills_fit": skills_fit,
        "requirements_fit": requirements_fit,
        "job_quality_score": job_quality_score,
        "final_score": final_score,
        "required_blockers": classifications["required_blockers"],
        "nice_to_have_gaps": classifications["nice_to_have_gaps"],
        "wrong_domain_gaps": classifications["wrong_domain_gaps"],
        "fit_notes": notes,
    }
