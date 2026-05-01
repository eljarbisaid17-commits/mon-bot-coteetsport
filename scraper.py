"""
Optionnel : scrape le palinsesto coteetsport.ma pour mapper les ids.
L'application Lovable utilise déjà directement les XHR sjmtech.ma,
ce module sert de fallback côté bot si nécessaire.

!! ADAPTER LES SELECTEURS APRES INSPECTION DU DOM REEL !!
"""
import logging
from browser import launch_browser, close_all

log = logging.getLogger("parimatchia-bot.scraper")


def list_matches():
    p, browser, ctx, page = launch_browser()
    try:
        page.wait_for_selector("[data-match]", timeout=30000)
        matches = page.eval_on_selector_all(
            "[data-match]",
            """els => els.map(e => ({
                id: e.getAttribute('data-match'),
                home: e.querySelector('[data-team-home]')?.innerText,
                away: e.querySelector('[data-team-away]')?.innerText,
                time: e.querySelector('[data-time]')?.innerText
            }))""",
        )
        log.info("Found %d matches", len(matches))
        return matches
    finally:
        close_all(p, browser)
