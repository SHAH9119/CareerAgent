"""Headless smoke test for the CareerAgent UI.

Boots through every page, captures console errors, network failures, and
takes screenshots so the user can visually inspect the result.
"""

import os
import sys
import time

from playwright.sync_api import sync_playwright

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://127.0.0.1:5174")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")
SCREENSHOT_DIR = os.path.join("data", "ui_screens")

PAGES = [
    ("dashboard", "Dashboard", "Dashboard"),
    ("tailoring", "Tailoring", "Resume Tailoring"),
    ("agent-run", "AgentRun", "Agent Run"),
    ("settings", "Settings", "Settings"),
    ("onboarding", "Onboarding", "Welcome to CareerAgent"),
]


def main() -> int:
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    failures: list[str] = []
    console_logs: list[str] = []
    network_failures: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda exc: failures.append(f"pageerror: {exc}"))
        page.on(
            "requestfailed",
            lambda req: network_failures.append(f"{req.method} {req.url} - {req.failure}"),
        )

        try:
            page.goto(FRONTEND_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as exc:
            print(f"Initial load failed: {exc}")
            browser.close()
            return 1

        time.sleep(2)

        def click_nav(label: str) -> None:
            try:
                page.locator(f"button.nav-item:has-text('{label}')").first.click(timeout=5000)
                time.sleep(2)
            except Exception as exc:
                failures.append(f"nav click '{label}' failed: {exc}")

        def shoot(name: str) -> None:
            path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
            page.screenshot(path=path, full_page=True)
            print(f"  saved {path}")

        click_nav("Dashboard")
        shoot("01_dashboard")

        click_nav("Tailoring")
        shoot("02_tailoring")

        click_nav("Agent Run")
        shoot("03_agent_run")

        click_nav("Settings")
        shoot("04_settings")

        try:
            page.locator(".profile-card").click(timeout=5000)
            time.sleep(2)
            shoot("05_onboarding")
        except Exception as exc:
            failures.append(f"open onboarding failed: {exc}")

        browser.close()

    print("\nConsole logs:")
    for line in console_logs:
        print(f"  {line}")

    print("\nNetwork failures:")
    for line in network_failures:
        print(f"  {line}")

    print("\nFailures:")
    for line in failures:
        print(f"  {line}")

    blocking = [line for line in failures if line]
    return 0 if not blocking and not network_failures else 1


if __name__ == "__main__":
    sys.exit(main())
