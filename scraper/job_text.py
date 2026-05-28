import re

LINKEDIN_NAV_NOISE = [
    "Skip to main content",
    "Home",
    "My Network",
    "Jobs",
    "Messaging",
    "Notifications",
    "For Business",
    "Advertise",
    "Premium",
    "Use AI to assess",
    "Show match details",
    "Tailor my resume",
    "Help me stand out",
    "People you can contact",
    "Similar jobs",
    "More jobs like this",
]

DESCRIPTION_CUTOFF_PATTERNS = [
    "Set alert for similar jobs",
    "Job search faster with Premium",
    "About the company",
    "Need to hire fast",
    "About Accessibility",
    "LinkedIn Corporation",
    "Questions? Visit our Help Center",
    "Select language",
    "See who you already know",
    "Referrals increase your chances",
    "Unlock hiring insights",
    "Exclusive Job Seeker Insights",
    "Sign in to evaluate",
    "Already applied on company website",
]

DESCRIPTION_NOISE_PATTERNS = [
    "Apply Save",
    "Show more Show less",
    "Try Premium for",
    "Reposted",
    "Promoted by hirer",
    "Responses managed off LinkedIn",
]


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = " ".join(text.split())
    mid = len(text) // 2
    if len(text) > 10 and text[:mid].strip() == text[mid:].strip():
        return text[:mid].strip()
    return text


def strip_linkedin_chrome(text: str) -> str:
    cleaned = clean_text(text)
    for phrase in LINKEDIN_NAV_NOISE:
        cleaned = cleaned.replace(phrase, " ")
    cleaned = re.sub(r"\b(Apply|Save|Share|Report)\b", " ", cleaned)
    return clean_text(cleaned)


def clean_job_description(raw_text: str, source: str = "") -> str:
    """Keep job-relevant body text and remove board chrome."""
    text = strip_linkedin_chrome(raw_text)
    if not text:
        return ""

    markers = [
        "About the job",
        "Job description",
        "Role description",
        "Position description",
        "What you'll do",
        "About the role",
    ]
    for marker in markers:
        if marker.lower() in text.lower():
            idx = text.lower().index(marker.lower())
            text = text[idx + len(marker) :].strip()
            break

    if "Report this job" in text:
        text = text.split("Report this job", 1)[1].strip()

    for pattern in DESCRIPTION_CUTOFF_PATTERNS:
        if pattern in text:
            text = text.split(pattern, 1)[0].strip()

    for pattern in DESCRIPTION_NOISE_PATTERNS:
        text = text.replace(pattern, " ")

    # Drop very short nav-only fragments
    if len(text) < 80 and source == "linkedin":
        return ""

    return clean_text(text)
