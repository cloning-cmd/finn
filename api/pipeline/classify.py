"""Tier 0 rule classifier for exchange announcements (no LLM). Maps NSE category text + subject (+ first page of the
attachment) to the 17-category taxonomy, with an intensity in [0.3, 1.5] used by the scorer.
Tier 1 (cheap LLM) is attempted only for leftovers and only when a provider key is configured."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select

from api import db

log = logging.getLogger(__name__)


@dataclass
class Classification:
    category: str
    intensity: float = 1.0
    confidence: float = 0.9
    classifier: str = "rule"
    note: str = ""


def _rx(p: str) -> re.Pattern:
    return re.compile(p, re.I)


# Refinement helpers (applied after the category match)
ROLE_JUNIOR = _rx(r"(independent director|non[- ]*executive|company secretary|compliance officer|additional director|nominee director|senior management personnel|\bSMP\b)")
ROLE_SENIOR = _rx(r"(managing director|\bMD\b|chief executive|\bCEO\b|chief financial|\bCFO\b|chairman|chairperson|vice[- ]chair|whole[- ]time director|executive director|chief operating|\bCOO\b|promoter|group president)")
AUDITOR = _rx(r"(statutory auditor|secretarial auditor|cost auditor|internal auditor|change in auditor|\bauditor\b)")
INTIMATION = _rx(r"(intimation|schedule|to consider|will be held|will hold|notice of|prior intimation|date of|to be held)")
OUTCOME = _rx(r"(outcome|approved|approval|declared|results? (for|of)|unaudited|audited|submitted)")
REAFFIRM = _rx(r"(reaffirm|re-affirm|affirmed|assigned|withdrawn)")
RATING_MOVE = _rx(r"(upgrade|downgrade|revised|revision|outlook (changed|revised)|placed on watch)")
PLEDGE_RELEASE = _rx(r"(release|revocation|revoke)")
ROUTINE_FUND = _rx(r"(commercial paper|\bCPs?\b|non[- ]convertible debentures?|\bNCDs?\b|allotment of (debentures|NCD|commercial|securities)|issue of securities|allotment of securities)")
BIG_FUND = _rx(r"(\bQIP\b|qualified institution|preferential|rights issue|\bIPO\b|initial public offer|\bFPO\b|public issue)")

# Ordered rules: (pattern on "desc || subject", category, intensity, body_ok). First match wins.
# body_ok=True: the rule may also fire on the first page of the attachment when the subject was uninformative.
RULES: list[tuple[re.Pattern, str, float, bool]] = [
    # routine first so "allotment"/"newspaper"/"trading window" don't leak into other buckets
    (_rx(r"\b(ESOP|ESOS|ESPS|RSU|employee stock|stock option)"), "unclassified", 1.0, True),
    (_rx(r"trading window"), "unclassified", 1.0, True),
    (_rx(r"newspaper|advertisement|publication of (notice|results)"), "unclassified", 1.0, False),
    (_rx(r"(reconciliation of share capital|share capital audit|certificate under (regulation|reg|SEBI)|compliance certificate|loss of share|duplicate share|issue of duplicate|investor (complaint|grievance)|secretarial compliance|BRSR|business responsibility|ESG report|sustainability report|annual secretarial|registrar|\bCSR\b|monitoring agency|statement of deviation|deviation)"), "unclassified", 1.0, True),
    (_rx(r"(\bIEPF\b|investor education|reminder letter|transfer of (equity )?shares to the investor|unclaimed (dividend|shares)|special window|re-lodgement|change in (corporate )?(office )?address|registrar and (share )?transfer)"), "unclassified", 1.0, True),
    (_rx(r"(annual report|notice of (the )?annual general|integrated annual)"), "agm_egm", 0.8, False),
    # board-meeting intimations hide under meeting/updates descs; catch them before the meeting rules
    (_rx(r"(meeting of the board of directors|board meeting).*(scheduled|to consider|will be held|is convened)"), "results", 0.4, False),
    # a press/media release ON the results is part of the results event (collapsed into the outcome filing)
    (_rx(r"(press|media) release.*(financial results|results for the)"), "results", 1.0, False),
    # calls & meetings BEFORE results (transcripts/recordings mention "financial results")
    (_rx(r"(transcript|earnings call|earnings conference|conference call|concall|audio recording|video recording|link of (the )?recording|\brecording\b|earnings presentation|results presentation)"), "earnings_call", 1.0, True),
    (_rx(r"(analyst|institutional investor|investor meet|investor conference|investor presentation|investor day|non[- ]deal roadshow|\bNDR\b|investor interaction|investor call)"), "investor_meetings", 1.0, False),
    # results
    (_rx(r"(financial results|results? for the (quarter|period|half|year)|unaudited .*results|audited .*results|quarterly results|statement of (standalone|consolidated) .*results|interim condensed)"), "results", 1.0, True),
    # people
    (_rx(r"(appointment|appointed|resignation|resigned|cessation|ceased|retire|retirement|demise|passed away|change in (director|management|senior management|key managerial|auditor)|\bKMP\b|key managerial|re-?appointment|change in designation|elevation|succession|steps? down|stepping down)"), "management_change", 1.0, True),
    # ratings
    (_rx(r"(credit rating|rating (action|rationale|update|reaffirm|upgrade|downgrade|assigned|letter)|CRISIL|ICRA|CARE Ratings|India Ratings|Ind-Ra|Brickwork|Acuite|Moody|S&P Global|Fitch)"), "credit_rating", 1.0, True),
    # ownership / pledges / insider
    (_rx(r"(pledge|encumbrance|encumbered|regulation 31\b|reg\.? 31\b)"), "pledging", 1.0, True),
    (_rx(r"(takeover regulations|\bSAST\b|regulation 29|reg\.? 29|regulation 7 ?\(2\)|reg\.? 7 ?\(2\)|insider trading|\bPIT\b|prohibition of insider|regulation 10\(6\)|reg\.? 10\(6\))"), "insider_trading", 1.0, True),
    # deals & capital
    # legal before deals: insolvency/NCLT matters are litigation even when a resolution plan is mentioned
    (_rx(r"(litigation|arbitration|court|tribunal|\bNCLT\b|\bNCLAT\b|show[- ]cause|penalty|penalt|fine imposed|SEBI order|adjudication|writ|demand notice|tax demand|GST (demand|order)|income tax (order|demand)|orders? passed|action\(s\) taken|legal proceeding|dispute|claim filed|insolvency|\bCIRP\b|resolution professional)"), "litigation", 1.0, True),
    (_rx(r"(initial public offer|\bIPO\b|listing of (the )?(equity )?shares of|proposed listing|trading in (the )?(equity )?shares of .* (will )?commence|commencement of trading|demerger|scheme of arrangement|amalgamation|merger)"), "ma", 1.2, True),
    (_rx(r"(acquisition|acquire|acquired|joint venture|\bJV\b|divest|disinvest|slump sale|sale or disposal|stake (sale|purchase)|strategic investment|incorporation of|wholly[- ]owned subsidiary|subsidiary|associate company|share purchase agreement|\bSPA\b|business transfer|restructuring|resolution plan)"), "ma", 1.0, True),
    (_rx(r"(buy[- ]?back)"), "bonus_split", 1.4, True),
    (_rx(r"(bonus (issue|shares)|stock split|sub-?division of (equity )?shares|split of (equity )?shares)"), "bonus_split", 1.0, True),
    (_rx(r"(dividend|record date|book closure)"), "dividend", 1.0, True),
    (_rx(r"(\bQIP\b|qualified institution|preferential (issue|allotment)|rights issue|fund ?raising|raising of funds|raise funds|issuance of (securities|equity|shares|debentures|NCD|commercial paper|bonds)|issue of securities|allotment of (debentures|NCD|commercial paper|bonds|equity shares|securities)|\bNCDs?\b|commercial paper|debentures|borrowing|term loan|\bECB\b|external commercial)"), "fund_raise", 1.0, True),
    # business
    (_rx(r"(capex|capacity (expansion|addition)|expansion|new (plant|facility|unit|manufacturing)|commission(ing|ed)|greenfield|brownfield|setting up (of )?(a )?(plant|facility)|investment in (plant|capacity))"), "capex", 1.0, True),
    (_rx(r"(order (win|received|book|inflow)|bagged|bagging|receiving of orders|secures? (an )?order|contract (award|win|received)|letter of (award|intent)|\bLOA\b|\bLOI\b|wins? (order|contract)|awarded)"), "press_release", 1.0, False),
    (_rx(r"(rumou?r verification|news verification|clarification|price movement|spurt in volume|market rumou?rs)"), "press_release", 1.0, False),
    (_rx(r"(press release|media release|media statement|press note|press statement|launch|partnership|collaboration|agreement|\bMoU\b|memorandum of understanding|tie[- ]up|award|recognition|business update|operational update|monthly (business|update)|production (update|figures)|sales (update|volume)|update on|shareholders? letter)"), "press_release", 0.9, False),
    # governance meetings
    (_rx(r"postal ballot"), "postal_ballot", 1.0, True),
    (_rx(r"(\bAGM\b|\bEGM\b|annual general meeting|extraordinary general meeting|general meeting|shareholders?'? meeting|voting results|scrutini[sz]er|proceedings of)"), "agm_egm", 1.0, True),
    # generic meeting intimations last (low intensity; refined upward if it is an outcome with results)
    (_rx(r"board meeting"), "results", 0.4, False),
    (_rx(r"committee meeting"), "unclassified", 0.6, False),
]


def clean_subject(ticker: str, subject: str) -> str:
    """NSE subjects read "X Limited has informed the Exchange regarding 'Y'." -> Y."""
    s = (subject or "").strip()
    m = re.search(r"(?:regarding|about)\s*[:\-]?\s*['\"“‘](.+?)['\"”’]\.?\s*$", s)
    if m:
        s = m.group(1)
    else:
        s = re.sub(r"^.*?has (informed|submitted to|filed with|intimated) (the )?exchange,?\s*(the|about|regarding|a copy of|copy of|its|that)?\s*[:\-]?\s*", "", s, flags=re.I)
        s = re.sub(r"^(please find (attached|enclosed)|we (wish to|would like to) (inform|intimate)|this is to inform( you)?)\s*(that|herewith)?\s*", "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip(" .:-,")
    return s[:1].upper() + s[1:] if s else s


PR_FILENAME = _rx(r"_PR_|press[_-]?release|media[_-]?release")


def classify_text(desc: str, subject: str, body: str = "", url: str = "") -> Optional[Classification]:
    text = f"{desc or ''} || {subject or ''}"
    probe = f"{text} || {(body or '')[:1500]}"
    for pat, cat, intensity, _ in RULES:
        if pat.search(text):
            return refine(Classification(category=cat, intensity=intensity, note=pat.pattern[:30]), probe)
    # NSE names press-release attachments "<SYM>_<ts>_PR_<date>.pdf"
    if url and PR_FILENAME.search(url.rsplit("/", 1)[-1]):
        return refine(Classification(category="press_release", intensity=0.9, confidence=0.8, note="url:PR"), probe)
    # second pass: subject was uninformative ("General Updates"); look at the first page of the attachment
    if body:
        for pat, cat, intensity, body_ok in RULES:
            if body_ok and pat.search(body[:1500]):
                return refine(Classification(category=cat, intensity=intensity * 0.9, confidence=0.7, note="body:" + pat.pattern[:30]), probe)
    return None


def refine(c: Classification, probe: str) -> Classification:
    cat = c.category
    if cat == "results":
        if c.intensity < 1.0 and OUTCOME.search(probe) and re.search(r"financial results|results", probe, re.I):
            c.intensity = 1.0
        elif c.intensity < 1.0:
            c.note = "board meeting intimation"
    elif cat == "management_change":
        if AUDITOR.search(probe) and not ROLE_SENIOR.search(probe):
            return Classification(category="unclassified", intensity=1.0, confidence=0.8, note="auditor change")
        if ROLE_JUNIOR.search(probe):
            c.intensity = 0.6
        elif ROLE_SENIOR.search(probe):
            c.intensity = 1.0
        else:
            c.intensity = 0.7
        if re.search(r"re-?appointment", probe, re.I):
            c.intensity = min(c.intensity, 0.4)
    elif cat == "credit_rating":
        if RATING_MOVE.search(probe):
            c.intensity = 1.3
        elif REAFFIRM.search(probe):
            c.intensity = 0.2
    elif cat == "pledging":
        if PLEDGE_RELEASE.search(probe):
            c.intensity = 0.45
    elif cat == "fund_raise":
        if ROUTINE_FUND.search(probe) and not BIG_FUND.search(probe):
            c.intensity = 0.4  # routine NCD / CP allotments
    elif cat == "earnings_call":
        if INTIMATION.search(probe) and not re.search(r"transcript|recording|presentation", probe, re.I):
            c.intensity = 0.6
    elif cat == "ma":
        if re.search(r"incorporation of|wholly[- ]owned subsidiary", probe, re.I) and not re.search(r"acqui|merger|amalgamation|stake|IPO|public offer", probe, re.I):
            c.intensity = 0.5
    c.intensity = max(0.3, min(1.5, c.intensity))
    return c


def classify_pending(limit: int = 5000, use_llm: bool = True, reclassify_all: bool = False) -> dict:
    """Classify filings with category IS NULL (or all). Returns coverage stats."""
    stats = {"total": 0, "rule": 0, "llm": 0, "fallback": 0}
    with db.session() as s:
        q = select(db.Filing) if reclassify_all else select(db.Filing).where(db.Filing.category.is_(None))
        rows = s.scalars(q.limit(limit)).all()
        llm = None
        if use_llm:
            try:
                from api.pipeline.classify_llm import classify_llm  # Phase 2
                llm = classify_llm
            except ImportError:
                llm = None
        for f in rows:
            stats["total"] += 1
            c = classify_text(f.raw_category or "", f.subject or "", f.body_text or "", f.attachment_url or "")
            if c is None and llm is not None:
                c = llm(f)
                if c:
                    stats["llm"] += 1
            if c is None:
                c = Classification(category="unclassified", intensity=0.5, confidence=0.3, classifier="fallback", note="no rule matched")
                stats["fallback"] += 1
            elif c.classifier == "rule":
                stats["rule"] += 1
            f.category = c.category
            f.category_conf = c.confidence
            f.classifier = c.classifier
            payload = dict(f.payload or {})
            payload["intensity"] = c.intensity
            payload["classify_note"] = c.note
            f.payload = payload
            if reclassify_all:
                f.priority = None
                f.headline = None
    if stats["total"]:
        stats["rule_coverage_pct"] = round(100 * stats["rule"] / stats["total"], 1)
    return stats
