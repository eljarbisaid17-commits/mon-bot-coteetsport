"""
Résolution reCAPTCHA via 2captcha.
"""
import os
import time
import logging
import requests

log = logging.getLogger("parimatchia-bot.captcha")

CAPTCHA_API_KEY = os.getenv("CAPTCHA_API_KEY")


def solve_recaptcha_v2(site_key: str, page_url: str, timeout: int = 180) -> str:
    """Retourne le token g-recaptcha-response."""
    if not CAPTCHA_API_KEY:
        raise RuntimeError("CAPTCHA_API_KEY missing")

    log.info("Submitting reCAPTCHA to 2captcha (sitekey=%s)", site_key[:8])
    r = requests.post(
        "https://2captcha.com/in.php",
        data={
            "key": CAPTCHA_API_KEY,
            "method": "userrecaptcha",
            "googlekey": site_key,
            "pageurl": page_url,
            "json": 1,
        },
        timeout=30,
    ).json()
    if r.get("status") != 1:
        raise RuntimeError(f"2captcha submit failed: {r}")
    captcha_id = r["request"]

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(5)
        res = requests.get(
            "https://2captcha.com/res.php",
            params={"key": CAPTCHA_API_KEY, "action": "get",
                    "id": captcha_id, "json": 1},
            timeout=30,
        ).json()
        if res.get("status") == 1:
            log.info("reCAPTCHA solved")
            return res["request"]
        if res.get("request") != "CAPCHA_NOT_READY":
            raise RuntimeError(f"2captcha error: {res}")
    raise TimeoutError("2captcha timeout")


def inject_token(page, token: str):
    page.evaluate(
        """(t)=>{const el=document.getElementById('g-recaptcha-response');
        if(el){el.style.display='block';el.value=t;}}""",
        token,
    )