"""FINN API. Run: api/.venv/Scripts/python.exe -m uvicorn api.main:app --reload --port 8000"""
from __future__ import annotations

import datetime as dt
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import db
from api.config import settings
from api.routers import admin, alerts, brief, push, research, rules


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="FINN API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins + ["https://*.vercel.app"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(brief.router)
app.include_router(admin.router)
app.include_router(research.router)
app.include_router(rules.router)
app.include_router(alerts.router)
app.include_router(push.router)


@app.get("/health")
def health():
    return {"ok": True, "db": db.ping(), "as_of": dt.datetime.now(dt.timezone.utc).isoformat()}
