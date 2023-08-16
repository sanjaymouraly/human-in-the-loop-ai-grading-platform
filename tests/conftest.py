import pytest
from playwright.sync_api import sync_playwright

@pytest.fixture(scope="session")
def browser():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            yield browser
            browser.close()
    except Exception:
        pytest.skip("Playwright not available")

@pytest.fixture
def page(browser):
    page = browser.new_page()
    yield page
    page.close()
