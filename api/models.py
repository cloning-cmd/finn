"""FINN data contracts (pydantic). Mirrors docs/CONTRACTS.md and web/lib/types.ts. FROZEN; change via DECISIONS.md."""
from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

Tier = Literal["lead", "line", "buried"]
Category = Literal[
    "results", "ma", "fund_raise", "management_change", "litigation", "insider_trading", "earnings_call",
    "investor_meetings", "credit_rating", "dividend", "bonus_split", "capex", "press_release", "postal_ballot",
    "agm_egm", "pledging", "unclassified",
]
CATEGORIES: list[str] = list(Category.__args__)  # type: ignore[attr-defined]
CardType = Union[Category, Literal["price_move", "volume_spike"]]
PromiseStatus = Literal["kept", "on_track", "missed", "revised_down", "quietly_dropped", "too_early"]
PROMISE_STATUSES: list[str] = list(PromiseStatus.__args__)  # type: ignore[attr-defined]


class Source(BaseModel):
    id: str
    label: str
    url: str
    page: Optional[int] = None
    quote: Optional[str] = None


class Chip(BaseModel):
    label: str
    action: Literal["ask", "open_source", "open_research", "mute"]
    arg: Optional[str] = None


class MetricRow(BaseModel):
    name: str
    value: float
    prev_q: float
    prev_y: float
    qoq_pct: float
    yoy_pct: float


class MarginRow(BaseModel):
    name: str
    pct: float
    qoq_bps: int
    yoy_bps: int


class VsGuidance(BaseModel):
    status: PromiseStatus
    text: str
    promise_id: str


class ResultsPayload(BaseModel):
    period: str
    basis: Literal["consolidated", "standalone"]
    unit: Literal["₹ Cr"] = "₹ Cr"
    variant: Literal["standard", "lender"] = "standard"
    metrics: list[MetricRow]
    margins: Optional[list[MarginRow]] = None
    ebitda_method: Optional[Literal["reported", "computed_incl_other_income", "computed_excl_other_income"]] = None
    vs_guidance: Optional[VsGuidance] = None
    extraction: Literal["xbrl", "pdf_table", "llm_fallback"]


class Incoming(BaseModel):
    name: str
    bio_lines: list[str] = Field(default_factory=list, max_length=3)
    prior_roles: list[str] = Field(default_factory=list)
    bio_sources: list[Source] = Field(default_factory=list)


class Outgoing(BaseModel):
    name: str
    tenure_years: Optional[float] = None


class PeoplePayload(BaseModel):
    role: str
    change: Literal["appointment", "resignation", "retirement", "cessation"]
    incoming: Optional[Incoming] = None
    outgoing: Optional[Outgoing] = None
    effective_date: Optional[str] = None
    flags: list[str] = Field(default_factory=list)


class WindowFiling(BaseModel):
    id: str
    headline: str
    category: Category


class MovePayload(BaseModel):
    close: float
    change_pct: float
    z: float
    volume: int
    vol_multiple: float
    window_filings: list[WindowFiling] = Field(default_factory=list)
    sparkline: Optional[list[float]] = None


class GenericPayload(BaseModel):
    summary: Optional[str] = None
    fields: Optional[dict[str, str]] = None


Payload = Union[ResultsPayload, PeoplePayload, MovePayload, GenericPayload]


class Card(BaseModel):
    id: str
    type: CardType
    ticker: str
    company: str
    ts: str
    tier: Tier
    priority: float = Field(ge=0, le=100)
    headline: str = Field(max_length=70)
    one_liner: Optional[str] = Field(default=None, max_length=140)
    payload: Payload
    sources: list[Source] = Field(default_factory=list)
    chips: list[Chip] = Field(default_factory=list)
    explained_by: Optional[list[str]] = None
    unexplained: Optional[bool] = None


class BuriedItem(BaseModel):
    id: str
    headline: str
    ticker: str


class BuriedGroup(BaseModel):
    category: Category
    count: int
    items: list[BuriedItem]


class Window(BaseModel):
    from_: str = Field(alias="from")
    to: str
    model_config = {"populate_by_name": True}


class Counts(BaseModel):
    lead: int
    line: int
    buried: int


class Brief(BaseModel):
    window: Window
    counts: Counts
    minutes_saved: float
    cards: list[Card]
    buried: list[BuriedGroup]
    as_of: Optional[str] = None


class CategoryCondition(BaseModel):
    kind: Literal["category"] = "category"
    categories: list[Category]
    min_priority: Optional[float] = None


class PriceMoveCondition(BaseModel):
    kind: Literal["price_move"] = "price_move"
    pct: Optional[float] = None
    z: Optional[float] = None
    direction: Optional[Literal["up", "down", "both"]] = "both"


class VolumeCondition(BaseModel):
    kind: Literal["volume"] = "volume"
    multiple: float
    lookback_days: int = 20


class GuidanceGapCondition(BaseModel):
    kind: Literal["guidance_gap"] = "guidance_gap"
    min_gap_pct: float


RuleCondition = Union[CategoryCondition, PriceMoveCondition, VolumeCondition, GuidanceGapCondition]


class Scope(BaseModel):
    type: Literal["portfolio", "sector", "ticker"]
    value: Optional[str] = None


class Rule(BaseModel):
    id: str
    name: str
    enabled: bool = True
    scope: Scope
    condition: RuleCondition = Field(discriminator="kind")
    channels: list[Literal["push", "inbox", "telegram"]] = Field(default_factory=lambda: ["inbox"])
    source_text: Optional[str] = None


class Alert(BaseModel):
    id: str
    rule_id: str
    rule_name: str
    card: Card
    fired_at: str
    delivered: bool = False


class LaterMention(BaseModel):
    call: str
    stance: Literal["reiterated", "raised", "lowered", "absent"]


class PromiseRec(BaseModel):
    id: str
    ticker: str
    metric: str
    target_text: str
    target_low: Optional[float] = None
    target_high: Optional[float] = None
    unit: Optional[str] = None
    period: str
    said_in: str
    speaker: Optional[str] = None
    quote: str
    source: Source
    actual_text: Optional[str] = None
    actual_value: Optional[float] = None
    actual_source: Optional[Source] = None
    status: PromiseStatus
    later_mentions: list[LaterMention] = Field(default_factory=list)
    hard: bool


class Claim(BaseModel):
    text: str
    source_ids: list[str] = Field(default_factory=list)
    verified: bool = False


class Segment(BaseModel):
    name: str
    share_pct: float


class Snapshot(BaseModel):
    what: list[Claim]
    segments: list[Segment] = Field(default_factory=list)


class Financials(BaseModel):
    ttm: dict[str, float] = Field(default_factory=dict)
    ratios: dict[str, float] = Field(default_factory=dict)


class Trajectory(BaseModel):
    years: list[str] = Field(default_factory=list)
    series: dict[str, list[float]] = Field(default_factory=dict)
    notes: list[Claim] = Field(default_factory=list)


class BalanceSheet(BaseModel):
    de: list[float] = Field(default_factory=list)
    net_debt: list[float] = Field(default_factory=list)
    wc_days: list[float] = Field(default_factory=list)
    notes: list[Claim] = Field(default_factory=list)


class CashQuality(BaseModel):
    cfo_pat: list[float] = Field(default_factory=list)
    fcf: list[float] = Field(default_factory=list)
    flag: Optional[str] = None
    notes: list[Claim] = Field(default_factory=list)


class Ledger(BaseModel):
    summary: dict[str, int] = Field(default_factory=lambda: {s: 0 for s in PROMISE_STATUSES})
    promises: list[PromiseRec] = Field(default_factory=list)
    narrative: list[Claim] = Field(default_factory=list)


class Cost(BaseModel):
    inr: float = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cache_hit_pct: float = 0
    models: list[str] = Field(default_factory=list)


class Dossier(BaseModel):
    ticker: str
    name: str
    as_of: str
    basis: Literal["consolidated", "standalone"]
    verdict: list[Claim] = Field(default_factory=list, max_length=3)
    snapshot: Optional[Snapshot] = None
    financials: Financials = Field(default_factory=Financials)
    trajectory: Trajectory = Field(default_factory=Trajectory)
    balance_sheet: BalanceSheet = Field(default_factory=BalanceSheet)
    cash_quality: CashQuality = Field(default_factory=CashQuality)
    ledger: Ledger = Field(default_factory=Ledger)
    bull: list[Claim] = Field(default_factory=list, max_length=3)
    bear: list[Claim] = Field(default_factory=list, max_length=3)
    sources: list[Source] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    cost: Cost = Field(default_factory=Cost)


class ProgressEvent(BaseModel):
    step: str
    status: Literal["start", "done", "skip", "error"]
    detail: Optional[str] = None
    pct: Optional[float] = None
