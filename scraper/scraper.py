from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import time
import random
import json
import os

load_dotenv()
LINKEDIN_COOKIE = os.getenv("LINKEDIN_COOKIE")

def clean_text(text: str) -> str:
    if not text: return ""
    return " ".join(text.split())

def fetch_logged_in_jobs(search_term: str, limit: int = 50) -> list:
    if not LINKEDIN_COOKIE:
        print("❌ Error: Missing LINKEDIN_COOKIE in .env file!")
        return []

    print(f"🕵️‍♂️ Booting up stealth logged-in browser for '{search_term}'...")
    url_query = search_term.replace(" ", "%20")
    target_url = f"https://www.linkedin.com/jobs/search/?keywords={url_query}"
    scraped_jobs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        context.add_cookies([{"name": "li_at", "value": LINKEDIN_COOKIE, "domain": ".www.linkedin.com", "path": "/"}])

        page = context.new_page()
        page.goto(target_url)
        
        # Give the page a few seconds to do its initial load
        time.sleep(random.uniform(4, 6))
        
        print("🖱️ Scrolling to load more jobs...")
        
        # Loop to keep scrolling until we hit our limit
        for _ in range(15): # Try scrolling up to 15 times
            # Use Playwright to find all current job cards
            job_elements = page.locator(".job-card-container").all()
            current_count = len(job_elements)
            print(f"🔄 Currently found {current_count} jobs...")

            # If we have enough jobs, break the loop!
            if current_count >= limit:
                break

            # If we found jobs, force the browser to scroll down to the VERY LAST one
            if current_count > 0:
                try:
                    job_elements[-1].scroll_into_view_if_needed()
                except Exception:
                    pass # Ignore minor scrolling glitches
            
            # Human delay: Wait for LinkedIn to fetch the next batch
            time.sleep(random.uniform(3, 5))
            
            # Check if scrolling actually added new jobs to the screen
            new_count = len(page.locator(".job-card-container").all())
            if new_count == current_count:
                print("🏁 Reached the end of LinkedIn's job list for this search.")
                break

        # Now that we've scrolled and loaded everything, grab the raw HTML
        print(f"🎯 Extraction starting for top {limit} jobs...")
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        job_cards = soup.find_all("div", class_="job-card-container")

        for card in job_cards[:limit]:
            title_tag = card.find("a", class_="job-card-list__title")
            title = clean_text(title_tag.text) if title_tag else "Unknown Title"

            company_tag = card.find("span", class_="job-card-container__primary-description")
            company = clean_text(company_tag.text) if company_tag else "Unknown Company"
            
            url_fragment = title_tag["href"] if title_tag and "href" in title_tag.attrs else ""
            full_url = f"https://www.linkedin.com{url_fragment}" if url_fragment else ""

            if title != "Unknown Title":
                scraped_jobs.append({
                    "title": title,
                    "company": company,
                    "url": full_url,
                    "description": f"Role at {company} for {title}."
                })
                
        browser.close()
    return scraped_jobs

if __name__ == "__main__":
    # Make the scraper smart: Read the profile first!
    try:
        with open("data/profile.json", "r", encoding="utf-8") as f:
            profile = json.load(f)
        target_job = profile['job_titles'][0]
        print(f"🚀 AI Agent found target job in profile: {target_job}")
    except FileNotFoundError:
        print("⚠️ No profile.json found. Defaulting search to 'Machine Learning'.")
        target_job = "Machine Learning"

    jobs = fetch_logged_in_jobs(target_job, limit=50)
    
    if jobs:
        os.makedirs("data", exist_ok=True)
        with open("data/jobs.json", "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2)
        print(f"\n✅ Successfully saved {len(jobs)} jobs to data/jobs.json!")