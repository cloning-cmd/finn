"""People enrichment: the code side (verification, dates, headline, payload) with the model output faked."""
from __future__ import annotations

from api.models import Source
from api.pipeline import enrich_people as ep

TEXT = """Sub: Disclosure under Regulation 30 - Shareholders' approval for the appointment of Mr. Leo Puri as
Independent Director of the Company. The Board had unanimously approved the appointment of Mr. Leo Puri (DIN: 01764813)
as an Additional and Independent Director of the Company for a first term of five (5) consecutive years commencing from
7th September 2026 to 6th September 2031. Mr. Leo Puri shall assume office as Chairman of the Board with effect from
23rd January 2027, upon completion of the term of Mr. R. Seshasayee as Chairman and Independent Director on 22nd January 2027.
Brief profile: Mr. Puri was Managing Director of UTI Asset Management Company and earlier a Managing Director at Warburg Pincus
and a Director at McKinsey & Company. He holds an MA from Oxford University."""


def test_parse_date_forms():
    assert ep.parse_date("7th September 2026") == "2026-09-07"
    assert ep.parse_date("September 7, 2026") == "2026-09-07"
    assert ep.parse_date("07.09.2026") == "2026-09-07"
    assert ep.parse_date("immediately") is None


def test_verify_drops_lines_not_in_filing():
    c = ep.ChangeOut(name="Mr. Leo Puri", role="Independent Director", change="appointment", effective_date="7th September 2026",
                     profile_lines=["Mr. Puri was Managing Director of UTI Asset Management Company and earlier a Managing Director at Warburg Pincus and a Director at McKinsey & Company.",
                                    "He was CEO of a large bank for 12 years."],
                     prior_roles=["Managing Director of UTI Asset Management Company", "Chairman of HDFC Bank"], replaces="Mr. R. Seshasayee")
    v = ep.verify_change(c, TEXT)
    assert v is not None and v.name == "Leo Puri"
    assert len(v.profile_lines) == 1 and v.profile_lines[0].startswith("Mr. Puri was Managing Director")
    assert v.prior_roles == ["Managing Director of UTI Asset Management Company"]
    assert v.effective_date == "2026-09-07" and v.replaces == "R. Seshasayee"
    assert ep.verify_change(ep.ChangeOut(name="Jane Doe", role="CFO"), TEXT) is None


def test_primary_headline_and_payload():
    inc = ep.ChangeOut(name="Leo Puri", role="Independent Director", change="appointment", effective_date="2026-09-07",
                       profile_lines=["Mr. Puri was Managing Director of UTI Asset Management Company and earlier a Managing Director at Warburg Pincus and a Director at McKinsey & Company."],
                       prior_roles=["Managing Director of UTI Asset Management Company"])
    out = ep.ChangeOut(name="R. Seshasayee", role="Chairman and Independent Director", change="cessation", effective_date="2027-01-22")
    primary = ep.pick_primary([inc, out])
    assert primary is out  # chairman outranks an independent director
    assert ep.headline_people("ASIANPAINT", out) == "ASIANPAINT: R. Seshasayee steps down as Chairman"  # full role would be 71 chars
    assert len(ep.headline_people("ASIANPAINT", out)) <= 70
    p = ep.build_payload(out, [inc, out], TEXT, Source(id="s_1", label="Filing (NSE)", url="https://x/y.pdf"), [])
    assert p.change == "cessation" and p.outgoing.name == "R. Seshasayee" and p.incoming.name == "Leo Puri"
    assert p.incoming.bio_lines and p.incoming.bio_sources[0].label == "Filing (NSE)"
    assert "top role" in p.flags and "no successor named" not in p.flags
    assert ep.one_liner_for(p).startswith("from 22 Jan 2027 · previously Managing Director of UTI")


def test_headline_truncates_long_roles():
    c = ep.ChangeOut(name="Venkataraman Subramanian", role="Whole-time Director and Chief Financial Officer and Key Managerial Personnel", change="appointment")
    h = ep.headline_people("BAJFINANCE", c)
    assert len(h) <= 70 and h.endswith("appointed Chief Financial Officer")  # the senior clause wins, then abbreviations
