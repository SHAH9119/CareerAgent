import os
import json
import time
import random
import re
from groq import Groq
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# Load API Keys and Cookies
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LINKEDIN_COOKIE = os.getenv("LINKEDIN_COOKIE")

def clean_text(text: str) -> str:
    if not text: return ""
    return " ".join(text.split())

# --- THE BRAIN: AI QUERY ARCHITECT ---
def generate_smart_query(profile: dict) -> str:
    """Uses LLM to design a high-performing LinkedIn search string based on the profile."""
    client = Groq(api_key=GROQ_API_KEY)
    
    skills = ", ".join(profile.get('skills', [])[:10])
    projects = ", ".join([p['name'] for p in profile.get('projects', [])])
    titles = ", ".join(profile.get('job_titles', []))

    prompt = f"""
    Design ONE professional LinkedIn search query for this candidate.
    Focus on their specialized skills and projects to find high-match roles.
    
    Candidate Titles: {titles}
    Core Skills: {skills}
    Notable Projects: {projects}

    Return ONLY the query string. No quotes, no intro.
    Example: "Embedded AI Engineer FPGA"
    """

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    
    query = response.choices[0].message.content.strip().replace('"', '')
    print(f"🤖 AI Search Strategy: '{query}'")
    return query

# --- THE HANDS: DEEP SCRAPER ---
def fetch_job_description(page, url: str) -> str:
    """Smartly extracts the full job description using semantic scanning."""
    try:
        page.goto(url.split("?")[0], wait_until="domcontentloaded", timeout=60000)
        time.sleep(random.uniform(4, 6))

        # Try to expand "See more"
        try:
            page.locator("button:has-text('See more'), button:has-text('Show more')").first.click(timeout=3000)
            time.sleep(1)
        except:
            pass

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        
        # Scan for the container with the most 'job-like' keywords
        potential_containers = soup.find_all(['article', 'section', 'div'])
        best_content = ""
        keywords = ["Requirements", "Responsibilities", "Qualifications", "About the job"]
        
        for container in potential_containers:
            content_text = container.get_text(separator=" ", strip=True)
            if any(word in content_text for word in keywords):
                if len(content_text) > len(best_content):
                    best_content = content_text

        return clean_text(best_content) if len(best_content) > 200 else ""
    except Exception as e:
        print(f"  ⚠️ Skip: Description fetch failed ({e})")
        return ""

def scrape_page(page, url: str) -> list:
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(random.uniform(5, 7))

    # Scroll to trigger lazy loading
    page.mouse.wheel(0, 2000)
    time.sleep(2)

    html = page.content()
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    # Target multiple possible LinkedIn card containers
    cards = soup.find_all("div", class_="job-card-container") or soup.find_all("li", class_="scaffold-layout__list-item")
    
    for card in cards:
        title_tag = card.find("a", href=lambda x: x and "/jobs/view/" in x)
        if not title_tag: continue
        
        title = clean_text(title_tag.get_text())
        href = title_tag.get("href", "")
        full_url = f"https://www.linkedin.com{href.split('?')[0]}" if href.startswith("/") else href.split("?")[0]

        # --- PASTE THE NEW LOGIC HERE ---
        company_tag = (
            card.find("span", class_="job-card-container__primary-description") or 
            card.find("div", class_="artdeco-entity-lockup__subtitle") or
            card.find("a", class_="job-card-container__company-name") or
            card.find("span", class_="job-card-container__company-name")
        )
        # --------------------------------
        
        company = clean_text(company_tag.get_text()) if company_tag else "Unknown"

        jobs.append({"title": title, "company": company, "url": full_url, "description": ""})
    return jobs

def fetch_all_jobs(search_term: str, target: int = 20, filters: dict = None) -> list:
    """The manager function that handles Phase 1 and Phase 2."""
    if not LINKEDIN_COOKIE:
        print("❌ Error: LINKEDIN_COOKIE missing.")
        return []

    url_query = search_term.replace(" ", "%20")
    base_url = f"https://www.linkedin.com/jobs/search/?keywords={url_query}"
    
    # Apply Filters
    if filters:
        if filters.get("remote"): base_url += "&f_WT=2"
        if filters.get("past_24h"): base_url += "&f_TPR=r86400"
        loc = filters.get("location", "Worldwide")
        base_url += f"&location={loc.replace(' ', '%20')}"

    all_jobs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        context.add_cookies([{"name": "li_at", "value": LINKEDIN_COOKIE, "domain": ".www.linkedin.com", "path": "/"}])
        page = context.new_page()

        # Phase 1: Collect URLs
        start = 0
        while len(all_jobs) < target:
            print(f"📡 Scanning listings (Start: {start})...")
            jobs = scrape_page(page, f"{base_url}&start={start}")
            if not jobs: break
            all_jobs.extend(jobs)
            start += 25
            if start > 100: break

        all_jobs = all_jobs[:target]
        print(f"✅ Phase 1: Found {len(all_jobs)} jobs.")

        # Phase 2: Deep Scrape Descriptions
        print("\n🔍 Phase 2: Deep Extraction...")
        for i, job in enumerate(all_jobs):
            print(f"[{i+1}/{len(all_jobs)}] Reading: {job['title']} @ {job['company']}")
            desc = fetch_job_description(page, job["url"])
            job["description"] = desc
            
            if desc: print(f"  ✨ Success: {len(desc)} chars.")
            
            if (i + 1) % 5 == 0: # Auto-save progress
                with open("data/jobs.json", "w", encoding="utf-8") as f:
                    json.dump(all_jobs, f, indent=2)

            time.sleep(random.uniform(5, 8))

        browser.close()

    with open("data/jobs.json", "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, indent=2)
    return all_jobs

# --- THE BRAIN: MULTI-QUERY ARCHITECT ---
def generate_search_plan(profile: dict) -> list:
    """Uses LLM to design 3-4 distinct search queries for different job categories."""
    client = Groq(api_key=GROQ_API_KEY)
    
    titles = ", ".join(profile.get('job_titles', []))
    projects = ", ".join([p['name'] for p in profile.get('projects', [])])

    prompt = f"""
    Based on these titles ({titles}) and projects ({projects}), 
    provide a JSON list of the 3 most effective LinkedIn search strings.
    Keep them simple (2-4 words each). No Boolean logic.
    
    Example output: ["Computer Vision Intern", "ML Engineer Intern", "Embedded AI"]
    """

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"} # Force JSON output
    )
    
    data = json.loads(response.choices[0].message.content)
    # The LLM might return {"queries": [...]} or similar
    queries = list(data.values())[0] if isinstance(data, dict) else data
    return queries

# --- THE MANAGER: UPDATED MAIN ---
if __name__ == "__main__":
    with open("data/profile.json", "r", encoding="utf-8") as f:
        profile = json.load(f)
    
    # Get a list of search terms instead of just one
    search_plan = generate_search_plan(profile)
    print(f"📋 Search Plan: {search_plan}")

    all_scraped_jobs = []
    preferences = {"remote": False, "location": "Islamabad, Pakistan"}

    for query in search_plan:
        print(f"\n🚀 PASS: Searching for '{query}'...")
        # Scrape 10 jobs for each category to keep it fast
        jobs = fetch_all_jobs(query, target=10, filters=preferences)
        all_scraped_jobs.extend(jobs)

    # Save final combined results
    with open("data/jobs.json", "w", encoding="utf-8") as f:
        json.dump(all_scraped_jobs, f, indent=2)
    
    print(f"\n🎉 Mission Complete! Collected {len(all_scraped_jobs)} total jobs.") 
    
    # Deduplicate by URL
seen_urls = set()
unique_jobs = []
for job in all_scraped_jobs:
    if job["url"] not in seen_urls:
        seen_urls.add(job["url"])
        unique_jobs.append(job)

all_scraped_jobs = unique_jobs
print(f"🧹 After dedup: {len(all_scraped_jobs)} unique jobs")

def clean_text(text: str) -> str:
    if not text: return ""
    text = " ".join(text.split())
    # Fix duplicated titles
    mid = len(text) // 2
    if len(text) > 10 and text[:mid].strip() == text[mid:].strip():
        return text[:mid].strip()
    return text