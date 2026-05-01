"""
Scraping des vrais matchs sur coteetsport.ma via Playwright (rendu JS complet).
Renvoie une liste normalisée pour l'app Lovable.
"""
from __future__ import annotations

import logging
from datetime import datetime, date as date_cls
from typing import List, Dict, Any, Optional

from browser import new_browser_context

log = logging.getLogger("parimatchia-bot.matches")

TARGET_URL = "https://www.coteetsport.ma/cote-sport/sport/football"


def fetch_matches_for_date(date_iso: str) -> List[Dict[str, Any]]:
    """
    Charge la grille football de coteetsport.ma pour la date donnée (YYYY-MM-DD)
    et retourne une liste de matchs normalisés:
        { id, league, country, homeTeam, awayTeam, startTime, odds:{home,draw,away},
          selectionIds:{home,draw,away} }

    NOTE: Les sélecteurs CSS ci-dessous sont des hypothèses raisonnables.
    Si coteetsport.ma change son markup, mets-les à jour ICI.
    """
    target_date = datetime.strptime(date_iso, "%Y-%m-%d").date()

    with new_browser_context() as ctx:
        page = ctx.new_page()
        log.info("Loading %s", TARGET_URL)
        page.goto(TARGET_URL, wait_until="networkidle", timeout=45_000)

        # Tente de fermer une éventuelle popup cookies/promo
        for sel in ['button:has-text("Accepter")', 'button:has-text("J\'accepte")',
                    'button[aria-label="close"]', '.close-popup']:
            try:
                page.locator(sel).first.click(timeout=1500)
            except Exception:
                pass

        # Si le site a un sélecteur de date, on essaie de cliquer sur le jour voulu.
        # (À AFFINER selon le markup réel.)
        try:
            day_label = target_date.strftime("%d/%m")
            page.locator(f'text="{day_label}"').first.click(timeout=3000)
            page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            log.info("No date picker click possible, using default view")

        # Attend que la grille soit présente
        try:
            page.wait_for_selector('[data-event-id], .event-row, .match-row', timeout=15_000)
        except Exception:
            log.warning("No event rows detected after load")

        # Extraction. On boucle sur tous les conteneurs de match.
        rows = page.query_selector_all('[data-event-id], .event-row, .match-row')
        log.info("Found %d candidate match rows", len(rows))

        matches: List[Dict[str, Any]] = []
        for r in rows:
            try:
                event_id = r.get_attribute("data-event-id") or ""
                # Equipes
                teams = r.query_selector_all('.team-name, .event-team, [data-team]')
                if len(teams) < 2:
                    text = r.inner_text() or ""
                    parts = [p.strip() for p in text.split(" - ") if p.strip()]
                    if len(parts) < 2:
                        continue
                    home, away = parts[0], parts[1]
                else:
                    home = (teams[0].inner_text() or "").strip()
                    away = (teams[1].inner_text() or "").strip()
                if not home or not away:
                    continue

                # Heure
                time_el = r.query_selector('.event-time, .match-time, time')
                time_txt = (time_el.inner_text().strip() if time_el else "00:00")[:5]
                try:
                    hh, mm = [int(x) for x in time_txt.split(":")[:2]]
                except Exception:
                    hh, mm = 0, 0
                start_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=hh, minute=mm)

                # Pays / compétition (cherche dans un parent éventuel)
                country = ""
                league = ""
                parent = r.evaluate_handle("el => el.closest('[data-country], .competition, .league-block')")
                if parent:
                    try:
                        country = parent.get_attribute("data-country") or ""
                        h = parent.query_selector('.country-name, .league-name, h3')
                        if h:
                            league = (h.inner_text() or "").strip()
                    except Exception:
                        pass

                # Cotes
                odds_els = r.query_selector_all('.odd-value, .selection-odd, [data-odd]')
                def to_float(s: Optional[str]) -> Optional[float]:
                    if not s:
                        return None
                    s = s.replace(",", ".").strip()
                    try:
                        v = float(s)
                        return v if v > 0 else None
                    except Exception:
                        return None

                odd_home = to_float(odds_els[0].inner_text()) if len(odds_els) > 0 else None
                odd_draw = to_float(odds_els[1].inner_text()) if len(odds_els) > 1 else None
                odd_away = to_float(odds_els[2].inner_text()) if len(odds_els) > 2 else None

                # Selection IDs réels (clés que /reserve attend)
                def sel_id(idx: int) -> Optional[str]:
                    if idx >= len(odds_els):
                        return None
                    el = odds_els[idx]
                    return (el.get_attribute("data-selection-id")
                            or el.get_attribute("data-id")
                            or (f"{event_id}_{['1','N','2'][idx]}" if event_id else None))

                matches.append({
                    "id": event_id or f"{home}-{away}-{start_dt.isoformat()}",
                    "league": league or "Football",
                    "country": country or "",
                    "homeTeam": home,
                    "awayTeam": away,
                    "startTime": start_dt.isoformat(),
                    "odds": {"home": odd_home, "draw": odd_draw, "away": odd_away},
                    "selectionIds": {
                        "home": sel_id(0),
                        "draw": sel_id(1),
                        "away": sel_id(2),
                    },
                })
            except Exception as e:
                log.warning("Row parse failed: %s", e)
                continue

        log.info("Returning %d matches for %s", len(matches), date_iso)
        return matches