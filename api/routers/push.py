"""Web Push subscriptions. GET /push/key → VAPID public key; POST /push/subscribe {endpoint, keys{p256dh, auth}};
DELETE /push/subscribe?endpoint=; POST /push/test → one notification to the caller's subscription."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api import db
from api.config import settings
from api.pipeline import alerts as eng

router = APIRouter(prefix="/push", tags=["push"])


class Keys(BaseModel):
    p256dh: str
    auth: str


class SubscriptionIn(BaseModel):
    endpoint: str
    keys: Keys
    expirationTime: Optional[float] = None


@router.get("/key")
def vapid_key():
    return {"public_key": settings.vapid_public_key, "configured": eng.push_configured()}


@router.post("/subscribe")
def subscribe(sub: SubscriptionIn, s: Session = Depends(db.get_db)):
    if not eng.push_configured():
        raise HTTPException(503, "push not configured on the server (VAPID keys missing)")
    row = s.get(db.PushSubscription, sub.endpoint)
    data = {"endpoint": sub.endpoint, "keys": sub.keys.model_dump()}
    if row is None:
        s.add(db.PushSubscription(endpoint=sub.endpoint, json=data))
    else:
        row.json = data
    s.commit()
    return {"ok": True}


@router.delete("/subscribe")
def unsubscribe(endpoint: str, s: Session = Depends(db.get_db)):
    row = s.get(db.PushSubscription, endpoint)
    if row is not None:
        s.delete(row)
        s.commit()
    return {"ok": True}


class TestIn(BaseModel):
    endpoint: str


@router.post("/test")
def test_push(body: TestIn, s: Session = Depends(db.get_db)):
    sent = eng.send_push(s, {"title": "FINN", "body": "Notifications are on. Alerts arrive here.", "url": "/alerts", "tag": "finn-test"},
                         endpoints=[body.endpoint])
    s.commit()
    if sent == 0:
        raise HTTPException(502, "push service did not accept the notification")
    return {"ok": True, "sent": sent}
