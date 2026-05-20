import json
import os
import random
import time

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from groq import Groq
from playwright.sync_api import sync_playwright

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LINKEDIN_COOKIE = os.getenv("LINKEDIN_COOKIE")


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = " ".join(text.split())
    mid = len(text) // 2
    if len(text) > 10 and text[:mid].strip() == text[mid:].strip():
        return text[:mid].strip()

    return text


def generate_smart_query(profile: dict) -> str:
    """Use the LLM to design one high-performing search string."""
    client = Groq(api_key=GROQ_API_KEY)

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

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )

    query = response.choices[0].message.content.strip().replace('"', "")
    print(f"AI search strategy: '{query}'")
    return query


def generate_search_plan(profile: dict) -> list:
    """Use the LLM to design 3 distinct search queries."""
    client = Groq(api_key=GROQ_API_KEY)

    titles = ", ".join(profile.get("job_titles", []))
    projects = ", ".join([p.get("name", "") for p in profile.get("projects", [])])

    prompt = f"""
Based on these titles ({titles}) and projects ({projects}),
provide a JSON list of the 3 most effective job search strings.
Keep them simple (2-4 words each). No Boolean logic.

Example output: {{"queries": ["Computer Vision Intern", "ML Engineer Intern", "Embedded AI"]}}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )

    data = json.loads(response.choices[0].message.content)
    queries = data.get("queries") if isinstance(data, dict) else data
    if not queries and isinstance(data, dict):
        queries = next((value for value in data.values() if isinstance(value, list)), [])

    return queries or []


def fetch_job_description(page, url: str) -> str:
    """Extract the full job description from a LinkedIn job page."""
    try:
        page.goto(url.split("?")[0], wait_until="domcontentloaded", timeout=60000)
        time.sleep(random.uniform(4, 6))

        try:
            page.locator("button:has-text('See more'), button:has-text('Show more')").first.click(timeout=3000)
            time.sleep(1)
        except Exception:
            pass

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        potential_containers = soup.find_all(["article", "section", "div"])
        best_content = ""
        keywords = ["Requirements", "Responsibilities", "Qualifications", "About the job"]

        for container in potential_containers:
            content_text = container.get_text(separator=" ", strip=True)
            if any(word in content_text for word in keywords) and len(content_text) > len(best_content):
                best_content = content_text

        return clean_text(best_content) if len(best_content) > 200 else ""
    except Exception as exc:
        print(f"  Description fetch failed: {exc}")
        return ""


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

        company_tag = (
            card.find("span", class_="job-card-container__primary-description")
            or card.find("div", class_="artdeco-entity-lockup__subtitle")
            or card.find("a", class_="job-card-container__company-name")
            or card.find("span", class_="job-card-container__company-name")
        )
        company = clean_text(company_tag.get_text()) if company_tag else "Unknown"

        jobs.append(
            {
                "title": title,
                "company": company,
                "url": full_url,
                "description": "",
                "source": "linkedin",
            }
        )

    return jobs


def fetch_all_jobs(search_term: str, target: int = 20, filters: dict | None = None) -> list:
    """Fetch LinkedIn jobs for local prototype use only."""
    if not LINKEDIN_COOKIE:
        print("Error: LINKEDIN_COOKIE missing.")
        return []

    url_query = search_term.replace(" ", "%20")
    base_url = f"https://www.linkedin.com/jobs/search/?keywords={url_query}"

    if filters:
        if filters.get("remote"):
            base_url += "&f_WT=2"
        if filters.get("past_24h"):
            base_url += "&f_TPR=r86400"
        location = filters.get("location", "Worldwide")
        base_url += f"&location={location.replace(' ', '%20')}"

    all_jobs = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        context.add_cookies(
            [{"name": "li_at", "value": LINKEDIN_COOKIE, "domain": ".www.linkedin.com", "path": "/"}]
        )
        page = context.new_page()

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
            job["description"] = fetch_job_description(page, job["url"])

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
    """Deduplicate jobs by URL, falling back to title/company."""
    seen = set()
    unique_jobs = []

    for job in jobs:
        key = job.get("url") or f"{job.get('title', '')}_{job.get('company', '')}".lower()
        if key and key not in seen:
            seen.add(key)
            unique_jobs.append(job)

    return unique_jobs


if __name__ == "__main__":
    with open("data/profile.json", "r", encoding="utf-8") as file:
        profile = json.load(file)

    search_plan = generate_search_plan(profile)
    print(f"Search plan: {search_plan}")

    all_scraped_jobs = []
    preferences = {"remote": False, "location": "Islamabad, Pakistan"}

    for query in search_plan:
        print(f"\nSearching for '{query}'...")
        all_scraped_jobs.extend(fetch_all_jobs(query, target=10, filters=preferences))

    all_scraped_jobs = deduplicate_jobs(all_scraped_jobs)
    print(f"After dedup: {len(all_scraped_jobs)} unique jobs")

    os.makedirs("data", exist_ok=True)
    with open("data/jobs.json", "w", encoding="utf-8") as file:
        json.dump(all_scraped_jobs, file, indent=2)

    print(f"\nMission complete. Collected {len(all_scraped_jobs)} total jobs.")
