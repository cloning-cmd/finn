"""EOD prices via yfinance. Computes ret, vol60 (prior-60d std of returns), vol_avg20 (prior-20d mean volume), z."""
from __future__ import annotations

import logging
import math
from typing import Optional

import pandas as pd
import yfinance as yf
from sqlalchemy import select

from api import db

log = logging.getLogger(__name__)


def _clean(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


MARKET = "NIFTY"            # stored under this ticker; yfinance symbol ^NSEI
MARKET_SYM = "^NSEI"


def frame_to_rows(ticker: str, sub: pd.DataFrame, mkt: Optional[pd.Series] = None) -> list[dict]:
    """Per-row stats. z is computed on the market-adjusted return (ret - NIFTY ret) against the prior-60-session
    std of that excess return, so an index-wide rally does not flag every stock (DECISIONS 2026-11-11)."""
    sub = sub.dropna(subset=["Close"]).copy()
    if sub.empty:
        return []
    sub["ret"] = sub["Close"].pct_change()
    if mkt is not None:
        sub["mkt_ret"] = mkt.reindex(sub.index)
        sub["ret_ex"] = sub["ret"] - sub["mkt_ret"].fillna(0.0)
    else:
        sub["mkt_ret"] = float("nan")
        sub["ret_ex"] = sub["ret"]
    sub["vol60"] = sub["ret_ex"].rolling(60, min_periods=30).std().shift(1)
    sub["vol_avg20"] = sub["Volume"].rolling(20, min_periods=10).mean().shift(1)
    sub["z"] = sub["ret_ex"] / sub["vol60"]
    rows = []
    for idx, r in sub.iterrows():
        rows.append({
            "ticker": ticker, "date": idx.strftime("%Y-%m-%d"),
            "open": _clean(r["Open"]), "high": _clean(r["High"]), "low": _clean(r["Low"]), "close": _clean(r["Close"]),
            "volume": int(r["Volume"]) if _clean(r["Volume"]) is not None else None,
            "ret": _clean(r["ret"]), "mkt_ret": _clean(r["mkt_ret"]), "ret_ex": _clean(r["ret_ex"]),
            "vol60": _clean(r["vol60"]), "vol_avg20": _clean(r["vol_avg20"]), "z": _clean(r["z"]),
        })
    return rows


def download(tickers: list[str], period: str = "400d") -> dict[str, pd.DataFrame]:
    syms = [MARKET_SYM if t == MARKET else t + ".NS" for t in tickers]
    df = yf.download(syms, period=period, group_by="ticker", auto_adjust=False, threads=True, progress=False)
    out = {}
    for t, s in zip(tickers, syms):
        try:
            out[t] = df[s] if len(syms) > 1 else df
        except KeyError:
            log.warning("no data for %s", s)
    return out


def load_prices(tickers: list[str] | None = None, period: str = "400d") -> dict[str, int]:
    with db.session() as s:
        if tickers is None:
            tickers = list(s.scalars(select(db.Company.ticker).where(db.Company.in_portfolio.is_(True))))
    frames = download([MARKET] + [t for t in tickers if t != MARKET], period)
    mkt_df = frames.pop(MARKET, None)
    mkt = mkt_df["Close"].pct_change() if mkt_df is not None and not mkt_df.empty else None
    written = {}
    with db.session() as s:
        if mkt_df is not None:
            written[MARKET] = db.upsert(s, db.PriceEOD, frame_to_rows(MARKET, mkt_df), pk=["ticker", "date"])
        for t, sub in frames.items():
            rows = frame_to_rows(t, sub, mkt)
            written[t] = db.upsert(s, db.PriceEOD, rows, pk=["ticker", "date"])
    return written


def latest(s, ticker: str, n: int = 20) -> list[db.PriceEOD]:
    rows = s.scalars(select(db.PriceEOD).where(db.PriceEOD.ticker == ticker).order_by(db.PriceEOD.date.desc()).limit(n)).all()
    return list(reversed(rows))
