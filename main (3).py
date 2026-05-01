"""
PariMatchia Bot - API FastAPI exposée publiquement (Railway)

Reçoit un panier de paris depuis l'application Lovable, ouvre coteetsport.ma
dans un Chrome headless, place les sélections, génère le code-barres
et renvoie l'image base64 à l'application.
"""
import os
import base64
import logging
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from executor import place_bet_and_get_barcode
from matches import fetch_matches_for_date

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("parimatchia-bot")

API_TOKEN = os.getenv("API_TOKEN")
if not API_TOKEN:
    raise RuntimeError("API_TOKEN env var is required")

app = FastAPI(title="PariMatchia Bot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Selection(BaseModel):
    id: str = Field(..., description="ID interne coteetsport, ex: 123_2")
    label: Optional[str] = None


class TicketRequest(BaseModel):
    selections: List[Selection]
    stake: float = Field(..., gt=0, description="Mise en MAD")


class TicketResponse(BaseModel):
    success: bool
    barcode_image_base64: Optional[str] = None
    barcode_value: Optional[str] = None
    error: Optional[str] = None


def check_token(authorization: Optional[str]) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")


@app.get("/")
def root():
    return {"service": "PariMatchia Bot", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/matches")
def matches(date: str, authorization: Optional[str] = Header(None)):
    """Récupère les vrais matchs football de coteetsport.ma pour la date YYYY-MM-DD."""
    check_token(authorization)
    log.info("Fetching matches for %s", date)
    try:
        items = fetch_matches_for_date(date)
        return {"success": True, "date": date, "matches": items}
    except Exception as e:
        log.exception("Matches fetch failed")
        return {"success": False, "error": str(e), "matches": []}


@app.post("/reserve", response_model=TicketResponse)
def reserve(payload: TicketRequest, authorization: Optional[str] = Header(None)):
    check_token(authorization)
    log.info("Received ticket request: %d selections, stake=%.2f",
             len(payload.selections), payload.stake)
    try:
        ids = [s.id for s in payload.selections]
        image_b64, value = place_bet_and_get_barcode(ids, payload.stake)
        return TicketResponse(
            success=True,
            barcode_image_base64=image_b64,
            barcode_value=value,
        )
    except Exception as e:
        log.exception("Ticket failed")
        return TicketResponse(success=False, error=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)