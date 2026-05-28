import json
import os
import random
import re
import time
from urllib.parse import quote_plus, urlparse, urlunparse

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from llm import llm_json, llm_text
from scraper.job_text import clean_job_description as shared_clean_job_description

load_dotenv()
LINKEDIN_COOKIE = os.getenv("LINKEDIN_COOKIE")
LINKEDIN_STORAGE_STATE = os.getenv("LINKEDIN_STORAGE_STATE", "data/linkedin_state.json")

DESCRIPTION_CUTOFF_PATTERNS = [
    "Set alert for similar jobs",
    "Job search faster with Premium",
    "About the company",
    "Need to hire fast",
    "About Accessibility",
    "LinkedIn Corporation",
    "Questions? Visit our Help Center",
    "Select language",
]

DESCRIPTION_NOISE_PATTERNS = [
    "Skip to main content",
    "Use AI to assess how you fit",
    "Get AI-powered advice on this job and more exclusive features with Premium.",
    "Try Premium for Rs 0",
    "Show match details",
    "Tailor my resume",
    "Help me stand out",
    "Apply Save",
    "Show more Show less",
]

COMPANY_SELECTORS = [
    ".job-details-jobs-unified-top-card__company-name a",
    ".job-details-jobs-unified-top-card__company-name",
    ".jobs-unified-top-card__company-name a",
    ".jobs-unified-top-card__company-name",
    ".topcard__org-name-link",
    "a.topcard__org-name-link",
]

TITLE_SELECTORS = [
    ".job-details-jobs-unified-top-card__job-title",
    ".jobs-unified-top-card__job-title",
    ".topcard__title",
    "h1",
]

DESCRIPTION_SELECTORS = [
    "div.jobs-description-content__text",
    "div.jobs-box__html-content",
    "div#job-details",
    "section.jobs-description",
    "div.description__text",
]


def normalize_linkedin_url(url: str) -> str:
    """Use one LinkedIn host so auth cookies apply consistently."""
    if not url:
        return ""

    parsed = urlparse(url)
    if parsed.netloc.endswith("linkedin.com"):
        parsed = parsed._replace(netloc="www.linkedin.com")

    return urlunparse(parsed)


def company_from_job_url(url: str) -> str:
    match = re.search(r"-at-([^/?]+?)-\d+", url)
    if not match:
        return "Unknown"

    company = match.group(1).replace("%2B", "+").replace("-", " ")
    return normalize_company_name(company)


def normalize_company_name(company: str) -> str:
    company = clean_text(company)
    if not company:
        return "Unknown"

    company = re.sub(r"\s+at\s+.+$", "", company, flags=re.IGNORECASE)
    known_upper = {"aecom": "AECOM", "jle": "JLE", "atc": "ATC", "anz": "ANZ", "case": "CaSE"}
    words = []
    for word in company.split():
        clean = word.strip()
        words.append(known_upper.get(clean.lower(), clean.capitalize() if clean.islower() else clean))

    return " ".join(words)


def infer_company_from_description(title: str, description: str, url: str = "") -> str:
    if description:
        prefix = clean_text(description[:220])
        if title and prefix.lower().startswith(title.lower()):
            company = prefix[len(title) :].strip()
            company = re.split(
                r"\s+(Apply|Join|Continue|Save|Report|New to LinkedIn|[A-Z][a-z]+,\s+[A-Z][a-z]+(?:,\s+[A-Z][a-z]+)?)\b",
                company,
            )[0].strip()
            if company:
                return normalize_company_name(company)

    return company_from_job_url(url)


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = " ".join(text.split())
    mid = len(text) // 2
    if len(text) > 10 and text[:mid].strip() == text[mid:].strip():
        return text[:mid].strip()

    return text


def first_selector_text(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        element = soup.select_one(selector)
        if element:
            text = clean_text(element.get_text(" ", strip=True))
            if text:
                return text

    return ""


def clean_job_description(raw_text: str, source: str = "linkedin") -> str:
    return shared_clean_job_description(raw_text, source=source)


def extract_job_metadata(text: str) -> dict:
    metadata = {
        "posted_at": "",
        "applicants": "",
        "salary": "",
        "employment_type": "",
        "seniority_level": "",
        "workplace_type": "",
    }

    posted = re.search(r"\b(\d+\s+(?:minute|hour|day|week|month)s?\s+ago)\b", text, flags=re.IGNORECASE)
    if posted:
        metadata["posted_at"] = posted.group(1)

    applicants = re.search(
        r"\b(Over\s+\d+\s+applicants|\d+\s+(?:applicants|people clicked apply)|Be among the first\s+\d+\s+applicants)\b",
        text,
        flags=re.IGNORECASE,
    )
    if applicants:
        metadata["applicants"] = applicants.group(1)

    salary = re.search(
        r"((?:A\$|\$|\u00a3|\u20ac|Rs)\s?[\d,.]+(?:\s?[-\u2013]\s?(?:A\$|\$|\u00a3|\u20ac|Rs)?\s?[\d,.]+)?(?:\s?/(?:hr|hour|day|week|month|year))?)",
        text,
        flags=re.IGNORECASE,
    )
    if salary:
        metadata["salary"] = salary.group(1)

    for label, pattern in [
        ("employment_type", r"Employment type\s+([A-Za-z -]+?)(?:\s+Job function|\s+Industries|\s+Referrals|$)"),
        ("seniority_level", r"Seniority level\s+([A-Za-z -]+?)(?:\s+Employment type|\s+Job function|\s+Industries|$)"),
    ]:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            metadata[label] = clean_text(match.group(1))

    for workplace in ["Remote", "Hybrid", "On-site"]:
        if re.search(rf"\b{re.escape(workplace)}\b", text, flags=re.IGNORECASE):
            metadata["workplace_type"] = workplace
            break

    return metadata


def extract_job_details_from_html(html: str, fallback: dict) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    page_text = clean_text(soup.get_text(" ", strip=True))

    title = first_selector_text(soup, TITLE_SELECTORS) or fallback.get("title", "")
    company = normalize_company_name(first_selector_text(soup, COMPANY_SELECTORS) or fallback.get("company", ""))
    if company == "Unknown":
        company = infer_company_from_description(title, page_text, fallback.get("url", ""))

    description_raw = first_selector_text(soup, DESCRIPTION_SELECTORS) or page_text
    description = clean_job_description(description_raw, source=fallback.get("source", "linkedin"))
    metadata = extract_job_metadata(page_text)

    return {
        "title": title or fallback.get("title", ""),
        "company": company,
        "description": description if len(description) > 120 else "",
        "description_raw_length": len(page_text),
        **metadata,
    }


def generate_smart_query(profile: dict) -> str:
    """Use the LLM to design one high-performing search string."""
    skills = ", ".join(profile.get("skills", [])[:10])
    projects = ", ".join([p.get("name", "") for p in profile.get("projects", [])])
    titles = ", ".join(profile.get("job_titles", []))

    prompt = f"""
Design ONE professional LinkedIn search query for this candidate.
Focus on their specialized skills and projects to find high-match roles.

Candidate Titles: {titles}
Core Skills: {skills}
Notable Projects: {projects}

Return ONLY the query string. No quotes, no intro.
Example: Embedded AI Engineer FPGA
"""

    query = llm_text(prompt, temperature=0.7).strip().replace('"', "")
    print(f"AI search strategy: '{query}'")
    return query


def generate_search_plan(profile: dict) -> list:
    """Use the LLM to design 3 distinct search queries."""
    titles = ", ".join(profile.get("job_titles", []))
    projects = ", ".join([p.get("name", "") for p in profile.get("projects", [])])
    skills = ", ".join(profile.get("skills", [])[:10])
    keywords = ", ".join(profile.get("job_search_keywords", [])[:10])
    career_stage = profile.get("career_stage", "")
    desired_role_level = profile.get("desired_role_level", "")
    education = ", ".join(
        [
            f"{item.get('degree', '')} {item.get('institution', '')} {item.get('year', '')}".strip()
            for item in profile.get("education", [])
        ]
    )

    prompt = f"""
Based on these titles ({titles}) and projects ({projects}),
provide a JSON list of the 3 most effective job search strings.

Candidate education: {education}
Candidate skills: {skills}
Candidate search keywords: {keywords}
Candidate career stage: {career_stage}
Candidate desired role level: {desired_role_level}

Use the candidate's inferred career stage and desired role level.
Do not assume internships, junior roles, senior roles, or a specific domain unless the profile supports it.
If desired_role_level is entry-level or junior, prefer realistic early-career role wording.
If desired_role_level is internship, use internship wording.
If desired_role_level is mid-level or the candidate has 3+ years of experience, do NOT use graduate, intern, internship, trainee, student, or entry-level wording.
Return role titles only. Do NOT append generic words like Jobs, Roles, Hiring, Careers, Openings, Remote, or Apply.
Keep searches simple (2-4 words each). No Boolean logic.

Return ONLY JSON in this format:
{{"queries": ["role query 1", "role query 2", "role query 3"]}}
"""

    data = llm_json(prompt, system="You design job-search queries and return only JSON.", temperature=0)
    queries = data.get("queries") if isinstance(data, dict) else data
    if not queries and isinstance(data, dict):
        queries = next((value for value in data.values() if isinstance(value, list)), [])

    return sanitize_search_queries(queries or [], profile)


def sanitize_search_queries(queries: list[str], profile: dict) -> list[str]:
    role_level = (profile.get("desired_role_level") or "").lower()
    years = profile.get("years_of_experience", 0) or 0
    banned = ["jobs", "roles", "hiring", "careers", "openings", "apply"]
    senior_banned = ["graduate", "internship", "intern", "trainee", "student", "entry level", "entry-level"]

    cleaned = []
    for query in queries:
        value = clean_text(query).strip('"').strip("'")
        for word in banned:
            value = re.sub(rf"\b{re.escape(word)}\b", "", value, flags=re.IGNORECASE)
        if role_level in {"mid-level", "senior"} or years >= 3:
            for word in senior_banned:
                value = re.sub(rf"\b{re.escape(word)}\b", "", value, flags=re.IGNORECASE)
        value = clean_text(value)
        if value and value.lower() not in {item.lower() for item in cleaned}:
            cleaned.append(value)

    return cleaned[:3]


def linkedin_experience_filter(filters: dict | None) -> str:
    if not filters:
        return ""

    level = (filters.get("desired_role_level") or "").lower()
    years = filters.get("years_of_experience") or 0

    if "intern" in level:
        return "1"
    if any(term in level for term in ["entry", "graduate", "junior"]) or years < 2:
        return "2,3"
    if "mid" in level or 3 <= years < 8:
        return "3,4"
    if "senior" in level or years >= 8:
        return "4,5"

    return ""


def fetch_job_details(page, job: dict) -> dict:
    """Extract clean job details from a LinkedIn job page."""
    try:
        page.goto(normalize_linkedin_url(job["url"]).split("?")[0], wait_until="domcontentloaded", timeout=60000)
        time.sleep(random.uniform(4, 6))

        try:
            page.locator("button:has-text('See more'), button:has-text('Show more')").first.click(timeout=3000)
            time.sleep(1)
        except Exception:
            pass

        return extract_job_details_from_html(page.content(), job)
    except Exception as exc:
        print(f"  Description fetch failed: {exc}")
        return {"description": ""}


def fetch_job_description(page, url: str) -> str:
    """Backward-compatible wrapper for description-only callers."""
    return fetch_job_details(page, {"url": url}).get("description", "")


def scrape_page(page, url: str) -> list:
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(random.uniform(5, 7))

    page.mouse.wheel(0, 2000)
    time.sleep(2)

    html = page.content()
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    cards = soup.find_all("div", class_="job-card-container") or soup.find_all(
        "li", class_="scaffold-layout__list-item"
    )

    for card in cards:
        title_tag = card.find("a", href=lambda value: value and "/jobs/view/" in value)
        if not title_tag:
            continue

        title = clean_text(title_tag.get_text())
        href = title_tag.get("href", "")
        full_url = f"https://www.linkedin.com{href.split('?')[0]}" if href.startswith("/") else href.split("?")[0]
        full_url = normalize_linkedin_url(full_url)

        company_tag = (
            card.find("span", class_="job-card-container__primary-description")
            or card.find("div", class_="artdeco-entity-lockup__subtitle")
            or card.find("a", class_="job-card-container__company-name")
            or card.find("span", class_="job-card-container__company-name")
        )
        company = clean_text(company_tag.get_text()) if company_tag else company_from_job_url(full_url)

        jobs.append(
            {
                "title": title,
                "company": company,
                "url": full_url,
                "description": "",
                "source": "linkedin",
            }
        )

    if jobs:
        return jobs

    # LinkedIn changes card wrapper classes often. As a fallback, collect every
    # job-view link and infer title/company from nearby text.
    seen_urls = set()
    for title_tag in soup.find_all("a", href=lambda value: value and "/jobs/view/" in value):
        href = title_tag.get("href", "")
        full_url = f"https://www.linkedin.com{href.split('?')[0]}" if href.startswith("/") else href.split("?")[0]
        full_url = normalize_linkedin_url(full_url)
        if full_url in seen_urls:
            continue

        title = clean_text(title_tag.get_text())
        if not title:
            continue

        container = title_tag.find_parent(["li", "div"])
        company = company_from_job_url(full_url)
        if container:
            company_tag = (
                container.find("span", class_="job-card-container__primary-description")
                or container.find("div", class_="artdeco-entity-lockup__subtitle")
                or container.find("a", class_="job-card-container__company-name")
                or container.find("span", class_="job-card-container__company-name")
            )
            if company_tag:
                company = clean_text(company_tag.get_text())

        seen_urls.add(full_url)
        jobs.append(
            {
                "title": title,
                "company": company,
                "url": full_url,
                "description": "",
                "source": "linkedin",
            }
        )

    if not jobs:
        os.makedirs("data/debug", exist_ok=True)
        debug_path = os.path.join("data", "debug", "linkedin_last_search.html")
        with open(debug_path, "w", encoding="utf-8") as file:
            file.write(html)
        print(f"  No job cards found. Saved page HTML to {debug_path}")
        print(f"  Page title: {page.title()}")
        print(f"  Current URL: {page.url}")

    return jobs


def linkedin_has_auth() -> bool:
    return bool(os.path.exists(LINKEDIN_STORAGE_STATE) or LINKEDIN_COOKIE)


def fetch_all_jobs(search_term: str, target: int = 20, filters: dict | None = None) -> list:
    """Fetch LinkedIn jobs for local prototype use only."""
    if not linkedin_has_auth():
        print("Error: LinkedIn auth missing. Run scraper/save_linkedin_session.py or set LINKEDIN_COOKIE.")
        return []

    url_query = quote_plus(search_term)
    base_url = f"https://www.linkedin.com/jobs/search/?keywords={url_query}"

    if filters:
        if filters.get("remote"):
            base_url += "&f_WT=2"
        if filters.get("past_24h"):
            base_url += "&f_TPR=r86400"
        experience = linkedin_experience_filter(filters)
        if experience:
            base_url += f"&f_E={quote_plus(experience)}"
        location = filters.get("location", "Worldwide")
        base_url += f"&location={quote_plus(location)}"

    all_jobs = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        if os.path.exists(LINKEDIN_STORAGE_STATE):
            context = browser.new_context(storage_state=LINKEDIN_STORAGE_STATE)
            print(f"Using saved LinkedIn browser session: {LINKEDIN_STORAGE_STATE}")
        elif LINKEDIN_COOKIE:
            context = browser.new_context()
            context.add_cookies(
                [{"name": "li_at", "value": LINKEDIN_COOKIE, "domain": ".www.linkedin.com", "path": "/"}]
            )
            print("Using LINKEDIN_COOKIE fallback. For better reliability, run scraper/save_linkedin_session.py.")
        else:
            print("No LinkedIn session or cookie available.")
            browser.close()
            return []

        page = context.new_page()
        try:
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=60000)
            print(f"LinkedIn auth check: {page.title()} ({page.url})")
        except Exception as exc:
            print(f"LinkedIn auth check skipped: {exc}")

        start = 0
        while len(all_jobs) < target:
            print(f"Scanning listings (start={start})...")
            jobs = scrape_page(page, f"{base_url}&start={start}")
            if not jobs:
                break
            all_jobs.extend(jobs)
            start += 25
            if start > 100:
                break

        all_jobs = all_jobs[:target]
        print(f"Phase 1: found {len(all_jobs)} jobs.")

        print("\nPhase 2: fetching descriptions...")
        for index, job in enumerate(all_jobs):
            print(f"[{index + 1}/{len(all_jobs)}] Reading: {job['title']} @ {job['company']}")
            details = fetch_job_details(page, job)
            job.update({key: value for key, value in details.items() if value})

            if (index + 1) % 5 == 0:
                os.makedirs("data", exist_ok=True)
                with open("data/jobs.json", "w", encoding="utf-8") as file:
                    json.dump(all_jobs, file, indent=2)

            time.sleep(random.uniform(5, 8))

        browser.close()

    os.makedirs("data", exist_ok=True)
    with open("data/jobs.json", "w", encoding="utf-8") as file:
        json.dump(all_jobs, file, indent=2)

    return all_jobs


def deduplicate_jobs(jobs: list) -> list:
    """Deduplicate jobs by normalized title+company (primary) and URL (secondary)."""
    seen_titles: set[str] = set()
    seen_urls: set[str] = set()
    unique_jobs = []

    for job in jobs:
        title_key = f"{(job.get('title') or '').strip()}_{(job.get('company') or '').strip()}".lower()
        url = (job.get("url") or "").strip()

        if title_key in seen_titles:
            continue
        if url and url in seen_urls:
            continue

        seen_titles.add(title_key)
        if url:
            seen_urls.add(url)
        unique_jobs.append(job)

    return unique_jobs


if __name__ == "__main__":
    with open("data/profile.json", "r", encoding="utf-8") as file:
        profile = json.load(file)

    search_plan = generate_search_plan(profile)
    print(f"Search plan: {search_plan}")

    all_scraped_jobs = []
    preferences = {
        "remote": True,
        "location": profile.get("location", "") or "Remote",
    }

    for query in search_plan:
        print(f"\nSearching for '{query}'...")
        all_scraped_jobs.extend(fetch_all_jobs(query, target=10, filters=preferences))

    all_scraped_jobs = deduplicate_jobs(all_scraped_jobs)
    print(f"After dedup: {len(all_scraped_jobs)} unique jobs")

    os.makedirs("data", exist_ok=True)
    with open("data/jobs.json", "w", encoding="utf-8") as file:
        json.dump(all_scraped_jobs, file, indent=2)

    print(f"\nMission complete. Collected {len(all_scraped_jobs)} total jobs.")
