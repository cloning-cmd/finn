"""Results enrichment on real NSE XBRL fixtures (trimmed to the OneD/FourD contexts). No network."""
import datetime as dt
from pathlib import Path

import pytest

from api.models import ResultsPayload
from api.pipeline import enrich_results as er

FX = Path(__file__).parent / "fixtures" / "xbrl"


def load(sym: str, q: str) -> dict:
    return er.parse_quarter((FX / f"{sym}_{q}_consolidated.xml").read_bytes())


def payload_for(sym: str):
    return er.build_payload(load(sym, "2026-09-30"), load(sym, "2026-06-30"), load(sym, "2025-09-30"), "consolidated")


def test_parse_quarter_reads_period_basis_and_format():
    cur = load("INFY", "2026-09-30")
    assert (cur["start"], cur["end"]) == (dt.date(2026, 7, 1), dt.date(2026, 9, 30))
    assert cur["basis"] == "consolidated" and cur["format"] == "indas"
    assert cur["v"]["RevenueFromOperations"] == pytest.approx(49244.0)  # rupees -> Rs Cr
    assert load("HDFCBANK", "2026-09-30")["format"] == "banking"
    assert load("BAJFINANCE", "2026-09-30")["format"] == "nbfc"


def test_standard_metrics_are_arithmetic_on_xbrl_tags():
    cur = load("INFY", "2026-09-30")
    v = cur["v"]
    m, method, gaps = er.compute_metrics(cur)
    assert gaps == [] and method == "computed_excl_other_income"
    assert m["Revenue"] == pytest.approx(v["RevenueFromOperations"])
    assert m["EBITDA"] == pytest.approx(v["ProfitBeforeTax"] + v["FinanceCosts"] + v["DepreciationDepletionAndAmortisationExpense"] - v["OtherIncome"])
    assert m["PBT"] == pytest.approx(v["ProfitBeforeTax"]) and m["PAT"] == pytest.approx(v["ProfitLossForPeriod"])


def test_lender_variants():
    bank = er.compute_metrics(load("HDFCBANK", "2026-09-30"))[0]
    vb = load("HDFCBANK", "2026-09-30")["v"]
    assert bank["NII"] == pytest.approx(vb["InterestEarned"] - vb["InterestExpended"])
    assert set(bank) == {"NII", "PPOP", "Provisions", "PAT"}
    nbfc = er.compute_metrics(load("BAJFINANCE", "2026-09-30"))[0]
    vn = load("BAJFINANCE", "2026-09-30")["v"]
    assert nbfc["NII"] == pytest.approx(vn["InterestEarned"] - vn["FinanceCosts"])
    assert nbfc["PPOP"] == pytest.approx(vn["ProfitBeforeTax"] + vn["ImpairmentOnFinancialInstruments"])


@pytest.mark.parametrize("sym", ["INFY", "HDFCBANK", "BAJFINANCE"])
def test_payload_validates_contract_and_copy_limits(sym):
    p, gaps = payload_for(sym)
    assert isinstance(p, ResultsPayload) and p.extraction == "xbrl" and gaps == []
    assert len(p.metrics) == 4 and all(m.prev_q > 0 and m.prev_y > 0 for m in p.metrics)
    for m in p.metrics:
        assert m.qoq_pct == pytest.approx((m.value - m.prev_q) / m.prev_q * 100, abs=0.06)
        assert m.yoy_pct == pytest.approx((m.value - m.prev_y) / m.prev_y * 100, abs=0.06)
    assert p.period == "Q2 FY27 (Jul-Sep 2026)"
    assert p.variant == ("standard" if sym == "INFY" else "lender")
    h = er.headline_from_payload(sym, p, dt.date(2026, 9, 30))
    assert len(h) <= 70 and "!" not in h and h.startswith(f"{sym} Q2 FY27:")
    o = er.one_liner_from_payload(p)
    assert o and len(o) <= 140


def test_missing_comparatives_degrade_with_gaps():
    p, gaps = er.build_payload(load("INFY", "2026-09-30"), None, None, "consolidated")
    assert all(m.qoq_pct == 0 and m.yoy_pct == 0 for m in p.metrics)
    assert any("previous-quarter" in g for g in gaps) and any("year-ago" in g for g in gaps)


def test_loss_headline_states_amounts_not_percentages():
    p, _ = payload_for("INFY")
    pat = next(m for m in p.metrics if m.name == "PAT")
    pat.value, pat.prev_y, pat.yoy_pct = -1879.0, -2582.0, 27.2
    h = er.headline_from_payload("INDIGO", p, dt.date(2026, 9, 30))
    assert len(h) <= 70 and "loss ₹1,879 Cr" in h and "+27.2%" not in h.split("loss")[1]
    pat.prev_y = 500.0
    assert "profit ₹500 Cr yr ago" in er.headline_from_payload("INDIGO", p, dt.date(2026, 9, 30))


def test_filed_window_rejects_xbrl_broadcast_weeks_later():
    ts = dt.datetime(2026, 10, 12, 18, 0, tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30)))
    assert not er._filed_within({"filed": "30-Oct-2026 19:05:00"}, ts, er.MAX_FILED_GAP_DAYS)
    assert er._filed_within({"filed": "13-Oct-2026 09:05:00"}, ts, er.MAX_FILED_GAP_DAYS)
    assert er._filed_within({"filed": None}, ts, er.MAX_FILED_GAP_DAYS)


def test_quarter_helpers():
    assert er._prev_quarter_end(dt.date(2026, 3, 31)) == dt.date(2025, 12, 31)
    assert er._prev_quarter_end(dt.date(2026, 12, 31)) == dt.date(2026, 9, 30)
    assert er._year_ago(dt.date(2026, 6, 30)) == dt.date(2025, 6, 30)
    assert er.period_label(dt.date(2026, 3, 31)) == "Q4 FY26 (Jan-Mar 2026)"
    assert er.inr(129359.4) == "1,29,359" and er.inr(999) == "999" and er.inr(-1500) == "-1,500"
