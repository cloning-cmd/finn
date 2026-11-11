import json
from pathlib import Path

import pytest

from api.pipeline.classify import classify_text, clean_subject
from api.pipeline.score import compute_priority, fiscal_label, headline_for, period_from_text, tier_for
import datetime as dt

FIX = Path(__file__).parent / "fixtures" / "filings_labelled.json"


def labelled():
    return [r for r in json.loads(FIX.read_text(encoding="utf-8")) if r.get("label")]


def test_rule_coverage_and_accuracy_on_labelled_set():
    rows = labelled()
    assert len(rows) >= 50
    covered = 0
    correct = 0
    misses = []
    for r in rows:
        c = classify_text(r["desc"], r["subject"], r.get("body", ""), r.get("url", ""))
        if c is not None:
            covered += 1
            if c.category == r["label"]:
                correct += 1
            else:
                misses.append((r["ticker"], r["desc"][:30], r["subject"][:60], c.category, r["label"]))
        else:
            misses.append((r["ticker"], r["desc"][:30], r["subject"][:60], None, r["label"]))
    coverage = covered / len(rows)
    accuracy = correct / len(rows)
    print(f"\ncoverage={coverage:.1%} accuracy={accuracy:.1%} misses={len(misses)}")
    for m in misses:
        print("  MISS", m)
    assert coverage >= 0.80
    assert accuracy >= 0.90


@pytest.mark.parametrize("desc,subject,cat", [
    ("Outcome of Board Meeting", "X Limited has submitted to the Exchange, the financial results for the period ended September 30, 2026", "results"),
    ("Analysts/Institutional Investor Meet/Con. Call Updates", "Transcript of the discussion on the Unaudited Financial Results", "earnings_call"),
    ("Appointment", "Appointment of Mr A as Non-Executive Independent Director", "management_change"),
    ("ESOP/ESOS/ESPS", "Allotment of 9138522 Shares.", "unclassified"),
    ("Credit Rating", "X has informed the Exchange about Credit Rating", "credit_rating"),
    ("General Updates", "Proposed Initial Public Offer of Jio Platforms Limited.", "ma"),
    ("Updates", "Disclosure under Regulation 31 of SAST - pledge of shares", "pledging"),
])
def test_rule_examples(desc, subject, cat):
    c = classify_text(desc, subject)
    assert c is not None and c.category == cat


def test_intensity_refinements():
    junior = classify_text("Appointment", "Appointment of Mr A as Non-Executive Independent Director")
    senior = classify_text("Change in Management", "Resignation of Mr B as Chief Financial Officer")
    assert junior.intensity < senior.intensity
    reaff = classify_text("Credit Rating", "CRISIL has reaffirmed the rating at AAA/Stable")
    assert reaff.intensity <= 0.3
    routine = classify_text("Allotment of Securities", "Allotment of Commercial Paper")
    assert routine.category == "fund_raise" and routine.intensity <= 0.5


def test_clean_subject_and_headline():
    assert clean_subject("INFY", "Infosys Limited has informed the Exchange regarding 'Investor Conference'.") == "Investor Conference"
    assert clean_subject("TITAN", "Titan Company Limited has submitted to the Exchange, the financial results for the period ended September 30, 2026") \
        .startswith("Financial results")
    h = headline_for("TITAN", "Titan Company Limited has submitted to the Exchange, the financial results for the quarter and half year ended September 30, 2026 (consolidated)", "results")
    assert h.startswith("TITAN: Q2 FY27 results") and len(h) <= 70


def test_fiscal_labels():
    assert fiscal_label(dt.date(2026, 9, 30)) == "Q2 FY27"
    assert fiscal_label(dt.date(2026, 3, 31)) == "Q4 FY26"
    assert fiscal_label(dt.date(2026, 12, 31)) == "Q3 FY27"
    assert period_from_text("for the quarter ended 30 September 2026") == dt.date(2026, 9, 30)
    assert period_from_text("quarter ended September 30, 2026") == dt.date(2026, 9, 30)


def test_priority_and_tiers():
    lead = compute_priority("results", 1.0, 10.0)
    buried = compute_priority("unclassified", 1.0, 10.0)
    assert tier_for(lead) == "lead" and tier_for(buried) == "buried"
    assert compute_priority("results", 0.4, 10.0) < 40  # board-meeting intimation stays buried
    assert 0 <= compute_priority("ma", 1.5, 10.0, surprise=1.5) <= 100
