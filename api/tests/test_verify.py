"""Verifier rejects a fabricated quote and a fabricated number; promise matching is pure code."""
from api.models import Claim, PromiseRec, Source
from api.research import promises as pr
from api.research.verify import numbers_in, quote_in_text, table_number_pool, verify_claims

CHUNK = ("Our revenue guidance for FY27 is 1% to 2% in constant currency. Operating margin guidance remains 20% to 22%. "
         "We added 8,203 employees this quarter and free cash flow was ₹5,231 crore.")


def test_quote_must_match_source():
    assert quote_in_text("revenue guidance for FY27 is 1% to 2% in constant currency", CHUNK)
    assert quote_in_text("Operating  margin guidance remains 20% to 22%", CHUNK)  # whitespace tolerant
    assert not quote_in_text("revenue guidance for FY27 is 4% to 6% in constant currency", CHUNK)
    assert not quote_in_text("we expect to double revenue next year", CHUNK)


def test_numbers_in_handles_indian_grouping_and_units():
    assert 8203.0 in numbers_in(CHUNK) and 5231.0 in numbers_in(CHUNK)
    assert numbers_in("PAT of ₹1,29,359 crore and 2.5 bn") == [129359.0, 250.0]


def test_verifier_drops_fabricated_number_and_keeps_supported_claim():
    tables = {"ttm": {"revenue": 189336.0, "pat": 30788.0}, "opm_pct": 24.0}
    pool = table_number_pool(tables)
    claims = [
        Claim(text="TTM revenue of 189,336 Cr with 24% operating margin.", source_ids=["s_screener"]),
        Claim(text="TTM revenue of 199,000 Cr with 24% operating margin.", source_ids=["s_screener"]),
        Claim(text="Management guided 1% to 2% constant-currency growth.", source_ids=["c1"]),
        Claim(text="Management guided 5% growth.", source_ids=["c1"]),
        Claim(text="A claim with no source at all.", source_ids=[]),
    ]
    kept, dropped, reasons = verify_claims(claims, {"c1": CHUNK}, pool)
    assert [c.text[:12] for c in kept] == ["TTM revenue ", "Management g"]
    assert dropped == 3 and all(c.verified for c in kept)
    assert any("199000" in r or "199,000" in r for r in reasons)


def _p(metric, period, low, high, unit="pct", hard=True):
    return PromiseRec(id="p_x", ticker="X", metric=metric, target_text="t", target_low=low, target_high=high, unit=unit, period=period,
                      said_in="Apr 2026", quote="q", source=Source(id="c", label="l", url="u"), status="too_early", hard=hard)


def test_match_hard_revenue_growth_against_quarterly_actuals():
    q = {"Jun 2026": {"yoy_sales_pct": 14.0, "opm_pct": 24.0}, "Sep 2026": {"yoy_sales_pct": 11.0, "opm_pct": 24.0}}
    p = _p("revenue_growth", "FY27", 1.0, 2.0)
    pr.match_hard([p], q, {})
    assert p.status == "on_track" and p.actual_value == 12.5 and "Jun 2026, Sep 2026" in p.actual_text
    m = _p("ebitda_margin", "FY27", 20.0, 22.0)
    pr.match_hard([m], q, {})
    assert m.status == "on_track" and m.actual_value == 24.0
    miss = _p("ebitda_margin", "Q2 FY27", 26.0, 27.0)
    pr.match_hard([miss], q, {})
    assert miss.status == "missed"
    done = _p("revenue_growth", "FY26", 5.0, 6.0)
    pr.match_hard([done], {"Jun 2025": {"yoy_sales_pct": 5}, "Sep 2025": {"yoy_sales_pct": 5}, "Dec 2025": {"yoy_sales_pct": 5}, "Mar 2026": {"yoy_sales_pct": 5}}, {"FY26": {"yoy_sales_pct": 10.0}})
    assert done.status == "kept" and "reported" in done.actual_text
    soft = _p("capex", "FY27", None, None, unit="inr_cr", hard=False)
    pr.match_hard([soft], q, {})
    assert soft.status == "too_early"


def test_target_quarters():
    assert pr._target_quarters("FY27") == ("FY27", ["Jun 2026", "Sep 2026", "Dec 2026", "Mar 2027"])
    assert pr._target_quarters("Q3 FY27") == ("FY27", ["Dec 2026"])
    assert pr._target_quarters("H2 FY27") == ("FY27", ["Dec 2026", "Mar 2027"])
    assert pr._target_quarters("unspecified") == (None, [])
