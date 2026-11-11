"""Dossier orchestration for ANY NSE symbol: resolve → screener tables → code-only sections → documents → promises →
synthesis → verify → cache by (ticker, latest_doc_sha, prompt_version). Degrades with gaps[]; never fills from memory."""
from __future__ import annotations

import datetime as dt
import logging
from typing import Callable, Optional

from sqlalchemy import select

from api import db
from api.ingest import screener as sc
from api.models import Cost, Dossier, Ledger, Snapshot, Source
from api.research import docs, financials as fin, promises as pr, synthesize as syn

log = logging.getLogger(__name__)
PROMPT_VERSION = f"g{pr.PROMPT_VERSION}-s{syn.PROMPT_VERSION}"
Progress = Callable[[str, str, Optional[str]], None]


class UnknownTicker(ValueError):
    pass


def _noop(step: str, status: str, detail: Optional[str] = None) -> None:
    return None


def resolve(ticker: str) -> tuple[str, dict]:
    t = ticker.strip().upper()
    if not t.isalnum() and "-" not in t and "&" not in t:
        raise UnknownTicker(f"'{ticker}' is not an NSE symbol")
    try:
        data = sc.load(t)
    except sc.ScreenerError as e:
        raise UnknownTicker(str(e)) from e
    return t, data


def cached(ticker: str) -> Optional[Dossier]:
    with db.session() as s:
        row = s.get(db.DossierRow, ticker.upper())
    if row is None:
        return None
    try:
        return Dossier.model_validate(row.json)
    except Exception:
        return None


def build(ticker: str, progress: Progress = _noop, force: bool = False, n_calls: int = 5) -> Dossier:
    progress("resolve", "start", ticker)
    t, data = resolve(ticker)
    name = data.get("name") or t
    progress("resolve", "done", f"{name} ({data['basis']})")
    gaps: list[str] = []
    sources: list[Source] = [Source(id="s_screener", label="screener.in tables", url=data["source_url"])]

    progress("tables", "start", None)
    financials = fin.financials(data)
    trajectory = fin.trajectory(data)
    balance = fin.balance_sheet(data)
    cash = fin.cash_quality(data)
    if not trajectory.years:
        gaps.append("no annual P&L table on screener.in")
    progress("tables", "done", f"{len(trajectory.years)} years")

    progress("documents", "start", None)
    ing = docs.ingest_for_ticker(t, data, n_calls=n_calls, progress=progress)
    gaps.extend(ing["gaps"])
    n_chunks = sum(d["chunks"] for d in ing["documents"])
    progress("documents", "done", f"{len(ing['documents'])} documents")
    doc_sha = docs.latest_doc_sha(t)

    if not force:
        with db.session() as s:
            row = s.get(db.DossierRow, t)
        if row is not None and row.doc_sha == doc_sha and row.prompt_version == PROMPT_VERSION:
            progress("cache", "done", "dossier unchanged")
            d = Dossier.model_validate(row.json)
            d.cost.cache_hit_pct = 100.0
            return d

    for d in ing["documents"]:
        kind = "Annual report" if d["kind"] == "ar" else "Concall"
        url = next((c["transcript"] for c in data["concalls"] if c["period"] == d["period"]), None) if d["kind"] == "concall" else (data["annual_reports"][0]["url"] if data["annual_reports"] else "")
        sources.append(Source(id=d["id"], label=f"{kind} {d['period']}", url=url or ""))

    cost = {"inr": 0.0, "tokens_in": 0, "tokens_out": 0, "calls": 0, "cached": 0, "models": []}

    def add_cost(c: dict) -> None:
        cost["inr"] += c.get("inr", 0.0)
        cost["tokens_in"] += c.get("tokens_in", 0)
        cost["tokens_out"] += c.get("tokens_out", 0)
        cost["calls"] += c.get("calls", 0)
        cost["cached"] += c.get("cached", 0)
        cost["models"] = sorted(set(cost["models"]) | set(c.get("models", [])))

    progress("guidance", "start", None)
    mgmt_chunks = [c for c in docs.chunks_for(t, kind="concall", management_only=True)]
    promises: list = []
    if mgmt_chunks:
        promises, c1, g1 = pr.extract_promises(t, mgmt_chunks, progress=progress)
        add_cost(c1)
        gaps.extend(g1)
        pr.match_hard(promises, fin.quarterly_actuals(data), fin.annual_actuals(data))
        calls = sorted({c["period"] for c in mgmt_chunks}, key=pr.period_date)
        pr.later_mentions(t, promises, calls)
        progress("guidance", "done", f"{len(promises)} promises from {len(mgmt_chunks)} management chunks")
    else:
        gaps.append("no management transcript chunks → ledger empty")
        progress("guidance", "skip", "no transcripts")

    progress("synthesis", "start", None)
    tables = {"financials": financials.model_dump(), "trajectory": trajectory.model_dump(), "balance_sheet": balance.model_dump(), "cash_quality": cash.model_dump()}
    chunks = syn.pick_chunks(t) if n_chunks else []
    synth, c2, g2 = syn.synthesize(t, name, tables, promises, chunks)
    add_cost(c2)
    gaps.extend(g2)
    for p in promises:
        if not p.hard and p.id in synth["soft_statuses"]:
            p.status = synth["soft_statuses"][p.id]
    progress("synthesis", "done", f"{synth['dropped']} claims dropped by verifier")

    for c in chunks:
        sources.append(Source(id=c["id"], label=f"{'AR' if c['kind'] == 'ar' else 'Concall'} {c['period']} p.{c['page']}", url=c["url"], page=c["page"], quote=c["text"][:200]))
    with db.session() as s:
        for p in promises:
            s.merge(db.PromiseRow(id=p.id, ticker=t, json=p.model_dump(), status=p.status))
    total_calls = cost["calls"] + cost["cached"]
    dossier = Dossier(
        ticker=t, name=name, as_of=docs.as_of_now(), basis=data["basis"],
        verdict=synth["verdict"][:3],
        snapshot=Snapshot(what=synth["snapshot_what"][:3] or ([] if not data.get("about") else []), segments=synth["segments"]),
        financials=financials, trajectory=trajectory, balance_sheet=balance, cash_quality=cash,
        ledger=Ledger(summary=pr.summarize(promises), promises=sorted(promises, key=lambda p: (not p.hard, p.status, p.said_in)), narrative=synth["ledger_narrative"][:3]),
        bull=synth["bull"][:3], bear=synth["bear"][:3], sources=sources, gaps=gaps,
        cost=Cost(inr=round(cost["inr"], 2), tokens_in=cost["tokens_in"], tokens_out=cost["tokens_out"],
                  cache_hit_pct=round(100 * cost["cached"] / total_calls, 1) if total_calls else 0.0, models=cost["models"]),
    )
    if not dossier.snapshot.what and data.get("about"):
        from api.models import Claim
        dossier.snapshot.what = [Claim(text=data["about"][:280], source_ids=["s_screener"], verified=True)]
    with db.session() as s:
        s.merge(db.DossierRow(ticker=t, as_of=dossier.as_of, doc_sha=doc_sha, prompt_version=PROMPT_VERSION, json=dossier.model_dump()))
    progress("done", "done", f"₹{dossier.cost.inr:.2f}")
    return dossier
