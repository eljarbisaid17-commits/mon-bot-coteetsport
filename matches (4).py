"""
Scraping des vrais matchs sur coteetsport.ma via Playwright.
On récupère le HTML rendu puis on parse avec les MÊMES regex que la
edge function `fetch-matches` (qui fonctionnent contre Firecrawl).
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from browser import new_browser_context

log = logging.getLogger("parimatchia-bot.matches")

LOGIN_URL = "https://zonereservee.coteetsport.ma/login/"
COTE_EMAIL = os.getenv("COTEETSPORT_EMAIL", "")
COTE_PASSWORD = os.getenv("COTEETSPORT_PASSWORD", "")

TARGET_URLS = [
    "https://www.coteetsport.ma/cote-sport/sport/football",
    "https://www.coteetsport.ma/cote-sport/sport/football/aujourdhui",
    "https://www.coteetsport.ma/cote-sport/sport/football/prochaines-3-heures",
]

ODD_RE = re.compile(
    r'<button[^>]*data-qa="esito_1_(\d+)_3_0_([123])"[^>]*>'
    r'[\s\S]*?<span[^>]*>([\d.,]+)</span>\s*</button>'
)
TEAM_RE = re.compile(r'<span[^>]*tw-fr-truncate[^>]*>([^<]+)</span>')
TIME_BLOCK_RE = re.compile(r'(\d{2})/(\d{2})\s*<br\s*/?>\s*(\d{2}):(\d{2})', re.I)
HREF_RE = re.compile(r'href="([^"]*\/evenement\/football\/[^"]+)"')


def _parse_html(html: str, date_iso: str) -> List[Dict[str, Any]]:
    target_year = datetime.strptime(date_iso, "%Y-%m-%d").year
    odds_by_event: Dict[str, Dict[str, float]] = {}
    for m in ODD_RE.finditer(html):
        eid, pos, raw = m.group(1), m.group(2), m.group(3)
        try:
            v = float(raw.replace(",", "."))
        except Exception:
            continue
        if v <= 0:
            continue
        slot = odds_by_event.setdefault(eid, {})
        if pos == "1":
            slot["home"] = v
        elif pos == "2":
            slot["draw"] = v
        else:
            slot["away"] = v

    out: Dict[str, Dict[str, Any]] = {}
    for eid, odds in odds_by_event.items():
        marker = f'regulator-link-{eid}'
        idx = html.find(marker)
        home = away = ""
        league = "Football"
        start_iso = f"{date_iso}T18:00:00.000Z"
        if idx >= 0:
            before = html[max(0, idx - 800):idx]
            tm = TIME_BLOCK_RE.search(before)
            if tm:
                dd, mm, hh, mn = tm.groups()
                try:
                    start_iso = datetime(
                        target_year, int(mm), int(dd), int(hh), int(mn),
                        tzinfo=timezone.utc,
                    ).isoformat().replace("+00:00", "Z")
                except Exception:
                    pass
            after = html[idx:idx + 2000]
            teams = TEAM_RE.findall(after)
            if len(teams) >= 2:
                home, away = teams[0].strip(), teams[1].strip()
            href = HREF_RE.search(html[idx:idx + 600])
            if href:
                segs = [s for s in href.group(1).split("/") if s]
                if len(segs) >= 2:
                    slug = segs[-2]
                    if slug and len(slug) <= 40:
                        league = slug.replace("-", " ").title()

        if not home or not away or home == away:
            continue
        if re.match(r"^(résultat|resultat|final|1x2|double chance)", league, re.I):
            league = "Football"

        out[eid] = {
            "id": eid,
            "league": league,
            "country": "",
            "homeTeam": home,
            "awayTeam": away,
            "startTime": start_iso,
            "odds": {
                "home": odds.get("home"),
                "draw": odds.get("draw"),
                "away": odds.get("away"),
            },
            "selectionIds": {
                "home": f"esito_1_{eid}_3_0_1",
                "draw": f"esito_1_{eid}_3_0_2",
                "away": f"esito_1_{eid}_3_0_3",
            },
        }
    return list(out.values())


def _login(ctx) -> bool:
    """Connecte le contexte navigateur sur zonereservee.coteetsport.ma.
    Les identifiants viennent des variables Railway COTEETSPORT_EMAIL / COTEETSPORT_PASSWORD.
    """
    if not COTE_EMAIL or not COTE_PASSWORD:
        log.warning("Login coteetsport ignoré (COTEETSPORT_EMAIL/PASSWORD manquants)")
        return False
    page = ctx.new_page()
    try:
        log.info("Login → %s", LOGIN_URL)
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=45_000)
        # cookie banners
        for sel in ['button:has-text("Accepter")',
                    'button:has-text("J\'accepte")',
                    'button[aria-label="close"]', '.close-popup']:
            try:
                page.locator(sel).first.click(timeout=1200)
            except Exception:
                pass
        # champs login (plusieurs sélecteurs candidats)
        email_selectors = [
            'input[name="username"]', 'input[name="email"]',
            'input[type="email"]', '#username', '#email',
        ]
        pwd_selectors = [
            'input[name="password"]', 'input[type="password"]', '#password',
        ]
        filled_email = filled_pwd = False
        for s in email_selectors:
            try:
                page.locator(s).first.fill(COTE_EMAIL, timeout=2500)
                filled_email = True
                break
            except Exception:
                continue
        for s in pwd_selectors:
            try:
                page.locator(s).first.fill(COTE_PASSWORD, timeout=2500)
                filled_pwd = True
                break
            except Exception:
                continue
        if not (filled_email and filled_pwd):
            log.warning("Champs login introuvables (email=%s, pwd=%s)", filled_email, filled_pwd)
            return False
        # bouton submit
        for s in ['button[type="submit"]',
                  'button:has-text("Connexion")',
                  'button:has-text("Se connecter")',
                  'input[type="submit"]']:
            try:
                page.locator(s).first.click(timeout=2500)
                break
            except Exception:
                continue
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass
        # heuristique de succès : on n'est plus sur /login/
        ok = "/login" not in page.url.lower()
        log.info("Login %s (url=%s)", "OK" if ok else "ÉCHEC", page.url)
        return ok
    except Exception as e:
        log.warning("login error: %s", e)
        return False
    finally:
        try:
            page.close()
        except Exception:
            pass


def fetch_matches_for_date(date_iso: str) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    with new_browser_context() as ctx:
        _login(ctx)
        for url in TARGET_URLS:
            try:
                page = ctx.new_page()
                log.info("Loading %s", url)
                page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                for sel in ['button:has-text("Accepter")',
                            'button:has-text("J\'accepte")',
                            'button[aria-label="close"]', '.close-popup']:
                    try:
                        page.locator(sel).first.click(timeout=1200)
                    except Exception:
                        pass
                # Attend qu'au moins une cote 1X2 apparaisse
                try:
                    page.wait_for_selector('[data-qa^="esito_1_"]', timeout=12_000)
                except Exception:
                    pass
                # Scroll progressif pour charger plus d'événements
                try:
                    for _ in range(8):
                        page.mouse.wheel(0, 4000)
                        page.wait_for_timeout(700)
                except Exception:
                    pass
                html = page.content()
                page.close()
                parsed = _parse_html(html, date_iso)
                log.info("  → %d matchs sur %s", len(parsed), url)
                for m in parsed:
                    existing = merged.get(m["id"])
                    score = lambda x: sum(1 for k in ("home","draw","away") if x["odds"].get(k))
                    if not existing or score(m) > score(existing):
                        merged[m["id"]] = m
            except Exception as e:
                log.warning("page %s failed: %s", url, e)
                continue

    log.info("Total fusionné: %d matchs", len(merged))
    return list(merged.values())
