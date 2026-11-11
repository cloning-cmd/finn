"""Admin endpoints: cost receipt and replay. Guarded by a shared token (X-Admin-Token header or ?token=)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from api.config import settings
from api.llm.router import costs_summary

router = APIRouter(prefix="/admin", tags=["admin"])


def _check(token_q: Optional[str], token_h: Optional[str]) -> None:
    if (token_h or token_q) != settings.admin_token:
        raise HTTPException(status_code=401, detail="admin token required")


@router.get("/costs")
def costs(token: Optional[str] = Query(None), x_admin_token: Optional[str] = Header(None)):
    _check(token, x_admin_token)
    return costs_summary()
