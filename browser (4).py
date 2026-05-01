"""
Lance un Chromium furtif (undetected) pour contourner Akamai/Cloudflare.
"""
import os
import logging
from contextlib import contextmanager
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

log = logging.getLogger("parimatchia-bot.browser")

TARGET_URL = os.getenv("TARGET_URL", "https://www.coteetsport.ma/")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def launch_browser():
    p = sync_playwright().start()
    browser: Browser = p.chromium.launch(
        headless=HEADLESS,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
    )
    context: BrowserContext = browser.new_context(
        user_agent=UA,
        viewport={"width": 1366, "height": 900},
        locale="fr-FR",
    )
    # Hide webdriver flag
    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"
    )
    page: Page = context.new_page()
    log.info("Navigating to %s", TARGET_URL)
    page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
    return p, browser, context, page


def close_all(p, browser):
    try:
        browser.close()
    finally:
        p.stop()


@contextmanager
def new_browser_context():
    """Crée un contexte navigateur Playwright réutilisable par matches.py."""
    p = sync_playwright().start()
    browser: Browser | None = None
    try:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        context: BrowserContext = browser.new_context(
            user_agent=UA,
            viewport={"width": 1366, "height": 900},
            locale="fr-FR",
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"
        )
        yield context
    finally:
        if browser:
            browser.close()
        p.stop()