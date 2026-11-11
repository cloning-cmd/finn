// FINN data contracts — mirrors docs/CONTRACTS.md and api/models.py. FROZEN; change only via DECISIONS.md.

export type Tier = "lead" | "line" | "buried";
export type Category =
  | "results" | "ma" | "fund_raise" | "management_change" | "litigation" | "insider_trading" | "earnings_call"
  | "investor_meetings" | "credit_rating" | "dividend" | "bonus_split" | "capex" | "press_release" | "postal_ballot"
  | "agm_egm" | "pledging" | "unclassified";
export type CardType = Category | "price_move" | "volume_spike";

export interface Source { id: string; label: string; url: string; page?: number; quote?: string }
export interface Chip { label: string; action: "ask" | "open_source" | "open_research" | "mute"; arg?: string }

export interface MetricRow { name: string; value: number; prev_q: number; prev_y: number; qoq_pct: number; yoy_pct: number }
export interface MarginRow { name: string; pct: number; qoq_bps: number; yoy_bps: number }

export type PromiseStatus = "kept" | "on_track" | "missed" | "revised_down" | "quietly_dropped" | "too_early";

export interface ResultsPayload {
  period: string;
  basis: "consolidated" | "standalone";
  unit: "₹ Cr";
  variant: "standard" | "lender";
  metrics: MetricRow[];
  margins?: MarginRow[];
  ebitda_method?: "reported" | "computed_incl_other_income" | "computed_excl_other_income";
  vs_guidance?: { status: PromiseStatus; text: string; promise_id: string };
  extraction: "xbrl" | "pdf_table" | "llm_fallback";
}
export interface PeoplePayload {
  role: string;
  change: "appointment" | "resignation" | "retirement" | "cessation";
  incoming?: { name: string; bio_lines: string[]; prior_roles: string[]; bio_sources: Source[] };
  outgoing?: { name: string; tenure_years?: number };
  effective_date?: string;
  flags: string[];
}
export interface MovePayload {
  close: number; change_pct: number; z: number; volume: number; vol_multiple: number;
  window_filings: { id: string; headline: string; category: Category }[];
  sparkline?: number[];
}
export interface GenericPayload { summary?: string; fields?: Record<string, string> }
export type Payload = ResultsPayload | PeoplePayload | MovePayload | GenericPayload;

export interface Card {
  id: string; type: CardType; ticker: string; company: string; ts: string;
  tier: Tier; priority: number;
  headline: string; one_liner?: string;
  payload: Payload;
  sources: Source[]; chips: Chip[];
  explained_by?: string[]; unexplained?: boolean;
}

export interface BuriedGroup { category: Category; count: number; items: { id: string; headline: string; ticker: string }[] }
export interface Brief {
  window: { from: string; to: string };
  counts: { lead: number; line: number; buried: number };
  minutes_saved: number;
  cards: Card[];
  buried: BuriedGroup[];
  as_of?: string;
}

export type RuleCondition =
  | { kind: "category"; categories: Category[]; min_priority?: number }
  | { kind: "price_move"; pct?: number; z?: number; direction?: "up" | "down" | "both" }
  | { kind: "volume"; multiple: number; lookback_days: number }
  | { kind: "guidance_gap"; min_gap_pct: number };
export interface Rule {
  id: string; name: string; enabled: boolean;
  scope: { type: "portfolio" | "sector" | "ticker"; value?: string };
  condition: RuleCondition;
  channels: ("push" | "inbox" | "telegram")[];
  source_text?: string;
}
export interface Alert { id: string; rule_id: string; rule_name: string; card: Card; fired_at: string; delivered: boolean }

export interface PromiseRec {
  id: string; ticker: string; metric: string;
  target_text: string; target_low?: number; target_high?: number; unit?: string; period: string;
  said_in: string; speaker?: string; quote: string; source: Source;
  actual_text?: string; actual_value?: number; actual_source?: Source;
  status: PromiseStatus;
  later_mentions: { call: string; stance: "reiterated" | "raised" | "lowered" | "absent" }[];
  hard: boolean;
}

export interface Claim { text: string; source_ids: string[]; verified: boolean }
export interface Dossier {
  ticker: string; name: string; as_of: string; basis: "consolidated" | "standalone";
  verdict: Claim[];
  snapshot?: { what: Claim[]; segments: { name: string; share_pct: number }[] };
  financials: { ttm: Record<string, number>; ratios: Record<string, number> };
  trajectory: { years: string[]; series: Record<string, number[]>; notes: Claim[] };
  balance_sheet: { de: number[]; net_debt: number[]; wc_days: number[]; notes: Claim[] };
  cash_quality: { cfo_pat: number[]; fcf: number[]; flag?: string; notes: Claim[] };
  ledger: { summary: Record<PromiseStatus, number>; promises: PromiseRec[]; narrative: Claim[] };
  bull: Claim[]; bear: Claim[];
  sources: Source[]; gaps: string[];
  cost: { inr: number; tokens_in: number; tokens_out: number; cache_hit_pct: number; models: string[] };
}
export interface ProgressEvent { step: string; status: "start" | "done" | "skip" | "error"; detail?: string; pct?: number }

export const CATEGORY_LABEL: Record<Category, string> = {
  results: "Results", ma: "M&A", fund_raise: "Fund raise", management_change: "Management", litigation: "Litigation",
  insider_trading: "Insider trades", earnings_call: "Earnings call", investor_meetings: "Investor meets",
  credit_rating: "Credit rating", dividend: "Dividend", bonus_split: "Bonus / split", capex: "Capex",
  press_release: "Press release", postal_ballot: "Postal ballot", agm_egm: "AGM / EGM", pledging: "Pledging",
  unclassified: "Routine",
};
