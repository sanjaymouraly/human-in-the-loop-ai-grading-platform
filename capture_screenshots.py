"""
Capture real browser screenshots of the running application using Playwright.

Prerequisites:
    pip install playwright
    playwright install chromium
    python manage.py migrate
    python manage.py seed_demo
    python manage.py runserver 127.0.0.1:8000   (in another terminal)

Usage:
    python capture_screenshots.py

Saves genuine browser screenshots to docs/images/.
"""
import os
import sys
import time
import subprocess

BASE_URL = "http://127.0.0.1:8000"
IMAGES_DIR = os.path.join(os.path.dirname(__file__), "docs", "images")

# (url_path, output_name, login_username_or_None, login_password)
PAGES = [
    ("/accounts/login/", "login.png", None, None),
    ("/", "dashboard.png", "manager", "ManagerPass123!"),
    ("/projects/", "projects-list.png", "manager", "ManagerPass123!"),
    ("/projects/1/", "dataset-management.png", "manager", "ManagerPass123!"),
    ("/rubrics/1/", "rubric-editor.png", "manager", "ManagerPass123!"),
    ("/analytics/1/", "agreement-analytics.png", "manager", "ManagerPass123!"),
    ("/evaluations/projects/1/disagreements/", "disagreement-resolution.png", "manager", "ManagerPass123!"),
    ("/evaluations/queue/", "reviewer-queue.png", "reviewer1", "ReviewerPass123!"),
]


def wait_for_server(timeout=30):
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{BASE_URL}/accounts/login/", timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def main():
    os.makedirs(IMAGES_DIR, exist_ok=True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        def login(username, password):
            page.goto(f"{BASE_URL}/accounts/login/")
            page.wait_for_load_state("networkidle")
            page.fill("input[name='username']", username)
            page.fill("input[name='password']", password)
            page.click("button.btn-primary")
            page.wait_for_load_state("networkidle")
            time.sleep(1)

        for url_path, name, user, pwd in PAGES:
            if user:
                login(user, pwd)
            else:
                page.goto(f"{BASE_URL}{url_path}")
                page.wait_for_load_state("networkidle")
                time.sleep(1)
            page.goto(f"{BASE_URL}{url_path}")
            page.wait_for_load_state("networkidle")
            time.sleep(1.5)
            out = os.path.join(IMAGES_DIR, name)
            page.screenshot(path=out, full_page=True)
            print(f"Saved {name}")

        browser.close()
    print("Done.")


if __name__ == "__main__":
    sys.exit(main())
