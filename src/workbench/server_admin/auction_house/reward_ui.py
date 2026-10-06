"""Legacy Rewards page location: the bundle/recipient workflow now lives in the hub's Inbox tab."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

router = APIRouter(tags=["Auction House Rewards"])


@router.get("/auction-house/rewards")
def rewards_page():
    return RedirectResponse("/auction-house#inbox", status_code=307)
