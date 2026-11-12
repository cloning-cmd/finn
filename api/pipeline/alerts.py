"""Rules → alerts → Web Push.

Rules live in `rules` (JSON per row, validated by api.models.Rule). Three defaults are seeded on first use and can be
edited or disabled but keep their ids, so the sliders on the Rules screen always have something to move:
  r_default_material  category rule: material categories at priority ≥ 60
  r_default_move      price_move: |z| ≥ 2.5 or |ret| ≥ 5 % (either)
  r_default_volume    volume ≥ 2 × 20-day average
`evaluate(since)` scores every card created since `since` against every enabled rule, writes one AlertRow per
(rule, card) that has not fired before, and pushes to every subscription when the rule has the push channel.
Everything here is code; the only model call is the NL rule parser in routers/rules.py.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
from typing import Iterable, Optional

from sqlalchemy import select

from api import db
from api.config import settings
from api.models import Alert, Card, Rule

log = logging.getLogger(__name__)

MATERIAL = ["results", "ma", "fund_raise", "management_change", "litigation", "credit_rating", "dividend", "bonus_split", "capex", "pledging"]

DEFAULT_RULES: list[dict] = [
    {"id": "r_default_material", "name": "Material filings", "enabled": True, "scope": {"type": "portfolio"},
     "condition": {"kind": "category", "categories": MATERIAL, "min_priority": 60}, "channels": ["push", "inbox"]},
    {"id": "r_default_move", "name": "Unusual price move", "enabled": True, "scope": {"type": "portfolio"},
     "condition": {"kind": "price_move", "z": 2.5, "pct": 5.0, "direction": "both"}, "channels": ["push", "inbox"]},
    {"id": "r_default_volume", "name": "Volume spike", "enabled": True, "scope": {"type": "portfolio"},
     "condition": {"kind": "volume", "multiple": 2.0, "lookback_days": 20}, "channels": ["inbox"]},
]


# ----------------------------------------------------------------------------- rules CRUD


def seed_defaults(s) -> int:
    n = 0
    for d in DEFAULT_RULES:
        if s.get(db.RuleRow, d["id"]) is None:
            s.add(db.RuleRow(id=d["id"], json=d, enabled=d["enabled"]))
            n += 1
    return n


def load_rules(s, enabled_only: bool = False) -> list[Rule]:
    seed_defaults(s)
    s.flush()
    rows = s.scalars(select(db.RuleRow)).all()
    out: list[Rule] = []
    for r in rows:
        try:
            rule = Rule.model_validate({**r.json, "enabled": bool(r.enabled)})
        except Exception as e:  # noqa: BLE001 - a bad row must not break the screen
            log.warning("rule %s invalid: %s", r.id, e)
            continue
        if enabled_only and not rule.enabled:
            continue
        out.append(rule)
    order = {d["id"]: i for i, d in enumerate(DEFAULT_RULES)}
    out.sort(key=lambda r: (order.get(r.id, 99), r.name))
    return out


def save_rule(s, rule: Rule) -> Rule:
    row = s.get(db.RuleRow, rule.id)
    data = rule.model_dump()
    if row is None:
        s.add(db.RuleRow(id=rule.id, json=data, enabled=rule.enabled))
    else:
        row.json = data
        row.enabled = rule.enabled
    return rule


def delete_rule(s, rule_id: str) -> bool:
    row = s.get(db.RuleRow, rule_id)
    if row is None:
        return False
    if rule_id.startswith("r_default_"):
        row.enabled = False  # defaults are disabled, never removed
        return True
    s.delete(row)
    return True


def new_rule_id(text: str) -> str:
    return "r_" + hashlib.sha256(f"{text}|{dt.datetime.now(dt.timezone.utc).isoformat()}".encode()).hexdigest()[:10]


# ----------------------------------------------------------------------------- matching (pure)


def matches(rule: Rule, card: Card, sector_of: Optional[dict[str, str]] = None) -> bool:
    if not rule.enabled:
        return False
    sc = rule.scope
    if sc.type == "ticker" and (sc.value or "").upper() != card.ticker.upper():
        return False
    if sc.type == "sector" and sector_of is not None and (sector_of.get(card.ticker) or "").lower() != (sc.value or "").lower():
        return False
    c = rule.condition
    p = card.payload if isinstance(card.payload, dict) else card.payload.model_dump()
    if c.kind == "category":
        if card.type not in c.categories:
            return False
        return c.min_priority is None or card.priority >= c.min_priority
    if c.kind == "price_move":
        if card.type != "price_move":
            return False
        z, ret = float(p.get("z") or 0), float(p.get("change_pct") or 0)
        if c.direction == "up" and ret <= 0:
            return False
        if c.direction == "down" and ret >= 0:
            return False
        hit_z = c.z is not None and abs(z) >= c.z
        hit_pct = c.pct is not None and abs(ret) >= c.pct
        return hit_z or hit_pct
    if c.kind == "volume":
        if card.type != "volume_spike":
            return False
        return float(p.get("vol_multiple") or 0) >= c.multiple
    if c.kind == "guidance_gap":
        vg = p.get("vs_guidance") if card.type == "results" else None
        return bool(vg and vg.get("status") in ("missed", "revised_down"))
    return False


# ----------------------------------------------------------------------------- evaluation


def _cards_since(s, since: dt.datetime) -> list[Card]:
    from api.routers.brief import anomaly_to_card, filing_to_card
    filings = s.scalars(select(db.Filing).where(db.Filing.created_at >= since, db.Filing.tier.is_not(None))).all()
    anomalies = s.scalars(select(db.Anomaly).where(db.Anomaly.created_at >= since, db.Anomaly.payload.is_not(None))).all()
    return [filing_to_card(f) for f in filings] + [anomaly_to_card(a) for a in anomalies]


def alert_id(rule_id: str, card_id: str) -> str:
    return "a_" + hashlib.sha256(f"{rule_id}|{card_id}".encode()).hexdigest()[:12]


def to_alert(row: db.AlertRow, rule_names: dict[str, str]) -> Alert:
    return Alert(id=row.id, rule_id=row.rule_id, rule_name=rule_names.get(row.rule_id, row.rule_id),
                 card=Card.model_validate(row.card), fired_at=(row.fired_at or dt.datetime.now(dt.timezone.utc)).isoformat(),
                 delivered=bool(row.delivered))


def fire(s, rule: Rule, card: Card, when: Optional[dt.datetime] = None, push: bool = True) -> Optional[Alert]:
    """Write the alert if new; push when the rule asks for it. Returns the Alert or None if it already existed."""
    aid = alert_id(rule.id, card.id)
    if s.get(db.AlertRow, aid) is not None:
        return None
    row = db.AlertRow(id=aid, rule_id=rule.id, card_id=card.id, fired_at=when or dt.datetime.now(dt.timezone.utc),
                      delivered=False, card=card.model_dump())
    s.add(row)
    if push and "push" in rule.channels:
        sent = send_push(s, {"title": f"{card.ticker} · {rule.name}", "body": card.headline, "url": f"/?card={card.id}", "tag": card.id})
        row.delivered = sent > 0
    s.flush()
    return to_alert(row, {rule.id: rule.name})


def evaluate(since: Optional[dt.datetime] = None, push: bool = True) -> dict:
    """Run every enabled rule over cards created since `since` (default: last 26 h). Idempotent."""
    since = since or dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=26)
    fired: list[Alert] = []
    with db.session() as s:
        rules = load_rules(s, enabled_only=True)
        cards = _cards_since(s, since)
        for card in cards:
            for rule in rules:
                if matches(rule, card):
                    a = fire(s, rule, card, push=push)
                    if a:
                        fired.append(a)
    return {"cards": len(cards) if cards else 0, "rules": len(rules), "fired": len(fired),
            "pushed": sum(1 for a in fired if a.delivered)}


def list_alerts(s, limit: int = 50) -> list[Alert]:
    rules = {r.id: r.name for r in load_rules(s)}
    rows = s.scalars(select(db.AlertRow).order_by(db.AlertRow.fired_at.desc()).limit(limit)).all()
    return [to_alert(r, rules) for r in rows]


# ----------------------------------------------------------------------------- web push


def push_configured() -> bool:
    return bool(settings.vapid_private_key and settings.vapid_public_key)


def send_push(s, payload: dict, endpoints: Optional[Iterable[str]] = None) -> int:
    """Send one notification to every stored subscription (or the given endpoints). Dead subscriptions (404/410)
    are removed. Returns the number delivered."""
    if not push_configured():
        return 0
    from pywebpush import WebPushException, webpush
    subs = s.scalars(select(db.PushSubscription)).all()
    if endpoints is not None:
        want = set(endpoints)
        subs = [x for x in subs if x.endpoint in want]
    sent = 0
    for sub in subs:
        try:
            webpush(subscription_info=sub.json, data=json.dumps(payload), vapid_private_key=settings.vapid_private_key,
                    vapid_claims={"sub": settings.vapid_subject}, ttl=3600, timeout=10)
            sent += 1
        except WebPushException as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code in (404, 410):
                s.delete(sub)
            else:
                log.warning("push failed %s: %s", code, str(e)[:120])
        except Exception as e:  # noqa: BLE001
            log.warning("push error: %s", str(e)[:120])
    return sent
