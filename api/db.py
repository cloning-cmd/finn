"""SQLAlchemy models + session. Schema of record: supabase/migrations/001_init.sql (Postgres). SQLite locally."""
from __future__ import annotations

import datetime as dt
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, Index, Integer, LargeBinary, String, Text,
                        create_engine, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from api.config import ROOT, settings

JSONType = JSON().with_variant(JSONB(), "postgresql")


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"
    ticker = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    nse_symbol = Column(String)
    bse_code = Column(String)
    sector = Column(String)
    industry = Column(String)
    is_lender = Column(Boolean, default=False)
    in_portfolio = Column(Boolean, default=False)
    weight = Column(Float, default=0.0)


class PriceEOD(Base):
    __tablename__ = "prices_eod"
    ticker = Column(String, primary_key=True)
    date = Column(String, primary_key=True)  # YYYY-MM-DD
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Integer)
    ret = Column(Float)          # daily return (fraction)
    mkt_ret = Column(Float)      # NIFTY 50 return same day
    ret_ex = Column(Float)       # ret - mkt_ret (market-adjusted)
    vol60 = Column(Float)        # std of ret_ex over the prior 60 sessions
    vol_avg20 = Column(Float)    # mean volume over the prior 20 sessions
    z = Column(Float)            # ret_ex / vol60


class Filing(Base):
    __tablename__ = "filings"
    id = Column(String, primary_key=True)
    ticker = Column(String, index=True, nullable=False)
    exchange = Column(String, default="NSE")
    ts = Column(DateTime(timezone=True), index=True, nullable=False)
    subject = Column(Text)
    raw_category = Column(String)
    body_text = Column(Text)
    attachment_url = Column(String)
    content_hash = Column(String, unique=True)
    category = Column(String, index=True)
    category_conf = Column(Float)
    classifier = Column(String)       # "rule" | "llm"
    priority = Column(Float)
    tier = Column(String)
    headline = Column(String)
    one_liner = Column(String)
    payload = Column(JSONType)
    card_type = Column(String)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class Anomaly(Base):
    __tablename__ = "anomalies"
    id = Column(String, primary_key=True)
    ticker = Column(String, index=True)
    date = Column(String, index=True)
    kind = Column(String)             # price_move | volume_spike
    value = Column(Float)
    z = Column(Float)
    vol_multiple = Column(Float)
    explained_by = Column(JSONType)   # list[str] filing ids
    unexplained = Column(Boolean, default=False)
    priority = Column(Float)
    tier = Column(String)
    payload = Column(JSONType)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class RuleRow(Base):
    __tablename__ = "rules"
    id = Column(String, primary_key=True)
    json = Column(JSONType, nullable=False)
    enabled = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class AlertRow(Base):
    __tablename__ = "alerts"
    id = Column(String, primary_key=True)
    rule_id = Column(String, index=True)
    card_id = Column(String, index=True)
    fired_at = Column(DateTime(timezone=True), default=_utcnow, index=True)
    delivered = Column(Boolean, default=False)
    card = Column(JSONType)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    endpoint = Column(String, primary_key=True)
    json = Column(JSONType, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True)
    ticker = Column(String, index=True)
    kind = Column(String)             # ar | concall | results | ppt
    period = Column(String)
    url = Column(String)
    sha256 = Column(String, index=True)
    text_path = Column(String)
    pages = Column(Integer)
    scanned = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(String, primary_key=True)
    document_id = Column(String, index=True)
    ticker = Column(String, index=True)
    period = Column(String)
    speaker = Column(String)
    page = Column(Integer)
    text = Column(Text)
    embedding = Column(LargeBinary)   # float32[384] little-endian


class PromiseRow(Base):
    __tablename__ = "promises"
    id = Column(String, primary_key=True)
    ticker = Column(String, index=True)
    json = Column(JSONType, nullable=False)
    status = Column(String)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class DossierRow(Base):
    __tablename__ = "dossiers"
    ticker = Column(String, primary_key=True)
    as_of = Column(String)
    doc_sha = Column(String)
    prompt_version = Column(String)
    json = Column(JSONType, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class LLMCache(Base):
    __tablename__ = "llm_cache"
    key = Column(String, primary_key=True)
    task = Column(String, index=True)
    model = Column(String)
    prompt_version = Column(String)
    input_hash = Column(String)
    output = Column(JSONType)
    tokens_in = Column(Integer, default=0)
    tokens_out = Column(Integer, default=0)
    cost_inr = Column(Float, default=0.0)
    hits = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True, autoincrement=True)
    card_id = Column(String)
    ticker = Column(String)
    category = Column(String)
    action = Column(String)           # noted | less
    ts = Column(DateTime(timezone=True), default=_utcnow)


Index("ix_filings_ticker_ts", Filing.ticker, Filing.ts)
Index("ix_feedback_ticker_cat", Feedback.ticker, Feedback.category)


def _make_engine():
    url = settings.database_url
    if url.startswith("sqlite"):
        path = url.replace("sqlite:///", "")
        (ROOT / path).parent.mkdir(parents=True, exist_ok=True)
        return create_engine(f"sqlite:///{ROOT / path}", connect_args={"check_same_thread": False}, future=True)
    return create_engine(url, pool_pre_ping=True, pool_size=3, max_overflow=2, future=True)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def init_db() -> None:
    Base.metadata.create_all(engine)


@contextmanager
def session() -> Iterator[Session]:
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency."""
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def upsert(s: Session, model, rows: list[dict], pk: list[str], chunk: int = 500) -> int:
    """Dialect-aware bulk upsert (SQLite + Postgres). Returns rows written."""
    if not rows:
        return 0
    if engine.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as _insert
    else:
        from sqlalchemy.dialects.sqlite import insert as _insert
    table = model.__table__
    n = 0
    for i in range(0, len(rows), chunk):
        batch = rows[i:i + chunk]
        stmt = _insert(table).values(batch)
        update_cols = {c.name: getattr(stmt.excluded, c.name) for c in table.columns if c.name not in pk}
        stmt = stmt.on_conflict_do_update(index_elements=pk, set_=update_cols) if update_cols else stmt.on_conflict_do_nothing(index_elements=pk)
        s.execute(stmt)
        n += len(batch)
    return n


def ping() -> bool:
    try:
        with engine.connect() as c:
            c.execute(text("select 1"))
        return True
    except Exception:
        return False
