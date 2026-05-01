"""
Place les sélections sur coteetsport.ma puis génère le code-barres.

!!! IMPORTANT : LES SELECTEURS CSS SONT GENERIQUES !!!
Le DOM réel de coteetsport.ma change. Ouvrez le site dans Chrome → Inspect
et adaptez les sélecteurs marqués TODO ci-dessous.
"""
import os
import time
import base64
import logging
from typing import List, Tuple

from browser import launch_browser, close_all
from captcha import solve_recaptcha_v2, inject_token

log = logging.getLogger("parimatchia-bot.executor")

TARGET_URL = os.getenv("TARGET_URL", "https://www.coteetsport.ma/")
RECAPTCHA_SITEKEY = os.getenv("RECAPTCHA_SITEKEY", "")


def _maybe_solve_captcha(page):
    """Détecte un reCAPTCHA visible et le résout via 2captcha."""
    try:
        if page.locator("iframe[src*='recaptcha']").count() > 0 and RECAPTCHA_SITEKEY:
            log.info("reCAPTCHA detected, solving…")
            token = solve_recaptcha_v2(RECAPTCHA_SITEKEY, page.url)
            inject_token(page, token)
            time.sleep(2)
    except Exception as e:
        log.warning("captcha step skipped: %s", e)


def place_bet_and_get_barcode(selection_ids: List[str], stake: float) -> Tuple[str, str]:
    """
    Retourne (image_base64_png, barcode_value).
    image_base64_png : capture du <canvas>/<img> code-barres
    barcode_value : valeur textuelle du code (ex: "AB123456")
    """
    p, browser, ctx, page = launch_browser()
    try:
        _maybe_solve_captcha(page)

        # 1) Cliquer chaque sélection par data-selection-id
        for sid in selection_ids:
            # TODO: adapter le sélecteur réel (data-id, data-selection, etc.)
            sel = f"[data-selection-id='{sid}']"
            log.info("Clicking selection %s", sid)
            page.wait_for_selector(sel, timeout=30000)
            page.click(sel)
            time.sleep(0.4)

        # 2) Saisir la mise
        # TODO: adapter le sélecteur réel du champ de mise
        page.fill("input[name='stake'], input.stake-input", str(stake))
        time.sleep(0.5)

        _maybe_solve_captcha(page)

        # 3) Cliquer sur "Générer le code-barres" / "Réserver"
        # TODO: adapter le sélecteur réel
        page.click("button.generate-barcode, button:has-text('Réserver')")

        # 4) Attendre l'apparition du code-barres
        # TODO: adapter (souvent un <canvas>, <img> ou bloc avec class barcode)
        page.wait_for_selector(".barcode, canvas#barcode, img.barcode-img", timeout=60000)

        # 5) Capture
        elem = page.locator(".barcode, canvas#barcode, img.barcode-img").first
        png_bytes = elem.screenshot()
        image_b64 = base64.b64encode(png_bytes).decode("ascii")

        # 6) Récupérer la valeur textuelle (souvent affichée à côté)
        barcode_value = ""
        try:
            barcode_value = page.locator(".barcode-value, [data-barcode-value]").first.inner_text(timeout=5000)
        except Exception:
            barcode_value = ""

        log.info("Barcode captured (%d bytes), value=%s", len(png_bytes), barcode_value)
        return image_b64, barcode_value
    finally:
        close_all(p, browser)
