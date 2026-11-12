"""One-liner enrichment: generic-headline detection and the code-side verification of model output."""
from __future__ import annotations

from api.pipeline import enrich_oneliner as eo

TEXT = """Sub.: Updates on ratings. This is to inform that ICRA has upgraded ratings of Suzlon Energy Limited as under:
Total bank loan facilities rated Rs.2635 Crores. Long term rating ICRA A+ / Positive (reaffirmed; outlook revised to
'Positive' from 'Stable'). Short term rating ICRA A1 (reaffirmed)."""


def test_generic_detection():
    assert eo.is_generic("SUZLON: Credit Rating")
    assert eo.is_generic("ADANIPORTS: Disclosure under Regulation 30 of the SEBI (Listing Obl…")
    assert eo.is_generic("SUZLON: Rumour Verification - Regulation 30(11)")
    assert not eo.is_generic("INFY Q2 FY27: rev ₹49,244 Cr +10.7% YoY, PAT ₹7,838 Cr +6.3%")
    assert not eo.is_generic("TITAN: Noel N. Tata retires as Vice-Chairman")


def test_verify_accepts_supported_output():
    out = eo.OneLinerOut(headline="ICRA revises outlook to Positive on Rs 2635 crore facilities", one_liner="Long term ICRA A+ reaffirmed, short term ICRA A1 reaffirmed",
                         quote="ICRA has upgraded ratings of Suzlon Energy Limited as under")
    assert eo.verify(out, TEXT) is None


def test_verify_rejects_invented_number_or_quote():
    bad_num = eo.OneLinerOut(headline="ICRA upgrades Rs 3000 crore facilities", one_liner="", quote="ICRA has upgraded ratings of Suzlon Energy Limited as under")
    assert "number" in eo.verify(bad_num, TEXT)
    bad_quote = eo.OneLinerOut(headline="ICRA revises outlook to Positive", one_liner="", quote="CRISIL downgraded the company last week")
    assert "sentence" in eo.verify(bad_quote, TEXT)


def test_clean_line_limits_and_strips_slop():
    assert eo.clean_line("Great news!! Outlook revised to Positive 🎉", 60) == "Great news.. Outlook revised to Positive"
    assert len(eo.clean_line("x" * 100, 60)) == 60
    assert eo.clean_line("Extension of timeline for the business transfer and share sale", 50) == "Extension of timeline for the business transfer…"
