import os
import time

from dotenv import load_dotenv
from playwright.sync_api import Error, sync_playwright

load_dotenv()

STORAGE_STATE_PATH = os.getenv("LINKEDIN_STORAGE_STATE", "data/linkedin_state.json")
PROFILE_DIR = os.getenv("LINKEDIN_PROFILE_DIR", "data/linkedin_browser_profile")


def is_logged_in(page) -> bool:
    try:
        url = page.url.lower()
        title = page.title().lower()
        return (
            "/feed" in url
            or "feed" in title
            or page.locator("a[href*='/mynetwork/'], a[href*='/jobs/']").count() > 0
        )
    except Error:
        return False


def main() -> None:
    os.makedirs(os.path.dirname(STORAGE_STATE_PATH), exist_ok=True)
    os.makedirs(PROFILE_DIR, exist_ok=True)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            PROFILE_DIR,
            headless=False,
            viewport={"width": 1366, "height": 900},
        )
        page = context.new_page()
        page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")

        print("\nLog in to LinkedIn in the browser window that opened.")
        print("This script will wait here and will NOT scrape or navigate to jobs.")
        print("After login succeeds, it will save the browser session automatically.")
        print("If LinkedIn asks for verification, complete it in the same browser window.\n")

        deadline = time.time() + 600
        while time.time() < deadline:
            if is_logged_in(page):
                break
            time.sleep(2)
        else:
            input("Login was not detected automatically. If you are logged in now, press Enter to save anyway...")

        context.storage_state(path=STORAGE_STATE_PATH)
        context.close()

    print(f"Saved LinkedIn session to {STORAGE_STATE_PATH}")
    print("Now rerun your main.py command. It should say: Using saved LinkedIn browser session.")


if __name__ == "__main__":
    main()
