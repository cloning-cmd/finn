"""Code-only dossier sections from screener tables: financials (TTM + ratios), trajectory (5y), balance sheet,
cash quality. No model touches these numbers. Every note is a Claim whose numbers come from the table itself,
with source_id "s_screener" so the verifier can check it against the same rows.
"""
from __future__ import annotations

import math
from typing import Optional

from api.ingest import screener as sc
from api.models import BalanceSheet, CashQuality, Claim, Financials, Trajectory

SRC = "s_screener"


def _last(vals: list[Optional[float]], n: int, idx: Optional[list[int]] = None) -> list[Optional[float]]:
    if idx is not None:
        vals = [vals[i] if i < len(vals) else None for i in idx]
    return vals[-n:]


def _f(v: Optional[float], dp: int = 0) -> str:
    if v is None:
        return "n/a"
    return f"{v:,.{dp}f}"


def _cagr(first: Optional[float], last: Optional[float], years: int) -> Optional[float]:
    if not first or not last or first <= 0 or last <= 0 or years <= 0:
        return None
    return round((math.pow(last / first, 1 / years) - 1) * 100, 1)


def _ratio(a: Optional[float], b: Optional[float], dp: int = 2) -> Optional[float]:
    if a is None or b in (None, 0):
        return None
    return round(a / b, dp)


def financials(data: dict) -> Financials:
    pl = data["sections"]["profit-loss"]
    cols = pl["cols"]
    ttm_i = cols.index("TTM") if "TTM" in cols else (len(cols) - 1 if cols else -1)
    ttm: dict[str, float] = {}
    if ttm_i >= 0:
        for label, key in (("Sales", "revenue"), ("Operating Profit", "ebitda"), ("Profit before tax", "pbt"), ("Net Profit", "pat"), ("OPM %", "opm_pct"), ("EPS in Rs", "eps")):
            _, v = sc.series(data, "profit-loss", label)
            if v and ttm_i < len(v) and v[ttm_i] is not None:
                ttm[key] = v[ttm_i]
    ratios: dict[str, float] = {}
    for label, key in (("Stock P/E", "pe"), ("ROCE", "roce_pct"), ("ROE", "roe_pct"), ("Dividend Yield", "div_yield_pct"), ("Market Cap", "mcap_cr"), ("Book Value", "book_value")):
        v = data["top"].get(label)
        if v is not None:
            ratios[key] = v
    if ttm.get("revenue") and ttm.get("pat"):
        ratios["pat_margin_pct"] = round(100 * ttm["pat"] / ttm["revenue"], 1)
    return Financials(ttm=ttm, ratios=ratios)


def trajectory(data: dict, years: int = 5) -> Trajectory:
    idx = sc.fy_cols(data, "profit-loss")[-years:]
    cols = data["sections"]["profit-loss"]["cols"]
    labels = [cols[i].replace("Mar 20", "FY") for i in idx]
    series: dict[str, list[float]] = {}
    for label, key in (("Sales", "revenue"), ("Operating Profit", "ebitda"), ("Net Profit", "pat"), ("OPM %", "opm_pct")):
        _, v = sc.series(data, "profit-loss", label)
        if v:
            series[key] = [x if x is not None else 0.0 for x in _last(v, years, idx)]
    notes: list[Claim] = []
    rev, pat, opm = series.get("revenue"), series.get("pat"), series.get("opm_pct")
    n = len(labels) - 1
    if rev and n > 0:
        c = _cagr(rev[0], rev[-1], n)
        if c is not None:
            notes.append(Claim(text=f"Revenue {_f(rev[0])} → {_f(rev[-1])} Cr over {labels[0]}–{labels[-1]} ({c:+.1f}% CAGR).", source_ids=[SRC], verified=True))
    if pat and n > 0:
        c = _cagr(pat[0], pat[-1], n)
        if c is not None:
            notes.append(Claim(text=f"Net profit {_f(pat[0])} → {_f(pat[-1])} Cr ({c:+.1f}% CAGR).", source_ids=[SRC], verified=True))
    if opm and len(opm) >= 3:
        d = opm[-1] - opm[0]
        direction = "expanded" if d >= 1 else "compressed" if d <= -1 else "held"
        notes.append(Claim(text=f"Operating margin {direction}: {opm[0]:.0f}% in {labels[0]} to {opm[-1]:.0f}% in {labels[-1]}.", source_ids=[SRC], verified=True))
    return Trajectory(years=labels, series=series, notes=notes)


def balance_sheet(data: dict, years: int = 5) -> BalanceSheet:
    bs = data["sections"]["balance-sheet"]
    idx = sc.fy_cols(data, "balance-sheet")[-years:]
    cols = bs["cols"]
    labels = [cols[i].replace("Mar 20", "FY") for i in idx]
    _, eq = sc.series(data, "balance-sheet", "Equity Capital")
    _, res = sc.series(data, "balance-sheet", "Reserves")
    _, bor = sc.series(data, "balance-sheet", "Borrowings")
    _, oa = sc.series(data, "balance-sheet", "Other Assets")
    _, inv = sc.series(data, "balance-sheet", "Investments")
    de: list[float] = []
    net_debt: list[float] = []
    for i in idx:
        e = (eq[i] or 0) + (res[i] or 0) if i < len(eq) and i < len(res) else 0
        b = bor[i] if i < len(bor) and bor[i] is not None else 0.0
        de.append(round(b / e, 2) if e else 0.0)
        net_debt.append(round(b - (inv[i] if i < len(inv) and inv[i] is not None else 0.0), 0))  # investments as cash proxy
    _, wc = sc.series(data, "ratios", "Working Capital Days")
    ridx = sc.fy_cols(data, "ratios")[-years:]
    wc_days = [wc[i] if i < len(wc) and wc[i] is not None else 0.0 for i in ridx]
    notes: list[Claim] = []
    if de and labels:
        notes.append(Claim(text=f"Debt/equity {de[0]:.2f} in {labels[0]} → {de[-1]:.2f} in {labels[-1]}; borrowings {_f(bor[idx[-1]] if idx and idx[-1] < len(bor) else None)} Cr.", source_ids=[SRC], verified=True))
    if wc_days and ridx:
        rl = data["sections"]["ratios"]["cols"]
        notes.append(Claim(text=f"Working-capital days {wc_days[0]:.0f} ({rl[ridx[0]].replace('Mar 20', 'FY')}) → {wc_days[-1]:.0f} ({rl[ridx[-1]].replace('Mar 20', 'FY')}).", source_ids=[SRC], verified=True))
    return BalanceSheet(de=de, net_debt=net_debt, wc_days=wc_days, notes=notes)


def cash_quality(data: dict, years: int = 5) -> CashQuality:
    cf = data["sections"]["cash-flow"]
    idx = sc.fy_cols(data, "cash-flow")[-years:]
    cols = cf["cols"]
    labels = [cols[i].replace("Mar 20", "FY") for i in idx]
    _, cfo = sc.series(data, "cash-flow", "Cash from Operating Activity")
    _, fcf = sc.series(data, "cash-flow", "Free Cash Flow")
    pl_cols = data["sections"]["profit-loss"]["cols"]
    _, pat = sc.series(data, "profit-loss", "Net Profit")
    cfo_pat: list[float] = []
    for i in idx:
        year = cols[i]
        j = pl_cols.index(year) if year in pl_cols else -1
        c = cfo[i] if i < len(cfo) else None
        p = pat[j] if 0 <= j < len(pat) else None
        cfo_pat.append(_ratio(c, p) or 0.0)
    fcf_l = [fcf[i] if i < len(fcf) and fcf[i] is not None else 0.0 for i in idx]
    weak = sum(1 for r in cfo_pat if 0 < r < 0.7) + sum(1 for r in cfo_pat if r <= 0)
    flag = f"CFO/PAT below 0.7 in {weak} of {len(cfo_pat)} years" if len(cfo_pat) >= 3 and weak >= 3 else None
    notes: list[Claim] = []
    if cfo_pat and labels:
        notes.append(Claim(text=f"CFO/PAT {cfo_pat[-1]:.2f} in {labels[-1]} (5y range {min(cfo_pat):.2f}–{max(cfo_pat):.2f}).", source_ids=[SRC], verified=True))
    if fcf_l and labels:
        notes.append(Claim(text=f"Free cash flow {_f(fcf_l[-1])} Cr in {labels[-1]}; cumulative {_f(sum(fcf_l))} Cr over {len(fcf_l)} years.", source_ids=[SRC], verified=True))
    return CashQuality(cfo_pat=cfo_pat, fcf=fcf_l, flag=flag, notes=notes)


def quarterly_actuals(data: dict) -> dict[str, dict[str, Optional[float]]]:
    """{'Sep 2026': {'revenue':..., 'ebitda':..., 'pat':..., 'opm_pct':..., 'yoy_sales_pct':...}} for promise matching."""
    q = data["sections"]["quarters"]
    out: dict[str, dict[str, Optional[float]]] = {}
    for label, key in (("Sales", "revenue"), ("Operating Profit", "ebitda"), ("Net Profit", "pat"), ("OPM %", "opm_pct"), ("YoY Sales growth", "yoy_sales_pct"), ("Profit before tax", "pbt")):
        _, v = sc.series(data, "quarters", label)
        for i, col in enumerate(q["cols"]):
            if i < len(v):
                out.setdefault(col, {})[key] = v[i]
    return out


def annual_actuals(data: dict) -> dict[str, dict[str, Optional[float]]]:
    """{'FY26': {...}} same keys plus capex (= -investing cash flow proxy is NOT used; capex not on screener)."""
    pl = data["sections"]["profit-loss"]
    out: dict[str, dict[str, Optional[float]]] = {}
    for label, key in (("Sales", "revenue"), ("Operating Profit", "ebitda"), ("Net Profit", "pat"), ("OPM %", "opm_pct"), ("Sales growth", "yoy_sales_pct")):
        _, v = sc.series(data, "profit-loss", label)
        for i, col in enumerate(pl["cols"]):
            if i < len(v) and col.startswith("Mar "):
                out.setdefault(col.replace("Mar 20", "FY"), {})[key] = v[i]
    return out
