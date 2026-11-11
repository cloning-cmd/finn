"""GET /research/{ticker} → cached Dossier or 404 {gaps}. POST /research/{ticker} → SSE progress events then dossier.
POST /qa → grounded answer as verified claims + sources."""
from __future__ import annotations

import json
import queue
import threading
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from api.research import dossier as dz
from api.research import qa as qa_mod

router = APIRouter(tags=["research"])


@router.get("/research/{ticker}")
def get_research(ticker: str):
    d = dz.cached(ticker)
    if d is None:
        raise HTTPException(status_code=404, detail={"gaps": [f"no dossier yet for {ticker.upper()}; POST to build"]})
    return d.model_dump()


@router.post("/research/{ticker}")
async def post_research(ticker: str, force: int = 0, calls: int = 5):
    q: queue.Queue = queue.Queue()

    def progress(step: str, status: str, detail: Optional[str] = None) -> None:
        q.put({"event": "progress", "data": json.dumps({"step": step, "status": status, "detail": detail})})

    def work() -> None:
        try:
            d = dz.build(ticker, progress=progress, force=bool(force), n_calls=max(1, min(calls, 8)))
            q.put({"event": "dossier", "data": d.model_dump_json()})
        except dz.UnknownTicker as e:
            q.put({"event": "error", "data": json.dumps({"detail": str(e), "gaps": [str(e)]})})
        except Exception as e:  # noqa: BLE001
            q.put({"event": "error", "data": json.dumps({"detail": f"research failed: {e}", "gaps": [str(e)]})})
        finally:
            q.put(None)

    threading.Thread(target=work, daemon=True).start()

    async def gen():
        import asyncio
        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, q.get)
            if item is None:
                break
            yield item

    return EventSourceResponse(gen(), ping=15)


class QAIn(BaseModel):
    ticker: str
    question: str
    card_id: Optional[str] = None


@router.post("/qa")
def post_qa(body: QAIn):
    try:
        return qa_mod.answer(body.ticker, body.question)
    except dz.UnknownTicker as e:
        raise HTTPException(status_code=404, detail=str(e))
