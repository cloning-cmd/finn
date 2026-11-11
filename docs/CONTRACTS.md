# FINN — Data contracts (FROZEN in Phase 0, 2026-11-11)

Source of truth for shapes exchanged between `api/` and `web/`. Mirrors: `web/lib/types.ts` (TypeScript) and
`api/models.py` (pydantic). Any change requires a `docs/DECISIONS.md` entry and an update to all three files.

## Conventions
- All timestamps ISO-8601 with timezone (`2026-11-11T09:30:00+05:30`). Dates `YYYY-MM-DD`.
- Money in ₹ Cr (float, 2 dp). Changes in % (float, 1 dp). Margin changes in bps (int).
- `headline` ≤ 70 chars, `one_liner` ≤ 140 chars; enforced by pydantic + checked in tests.
- IDs: filings `f_<exchange>_<sha12>`; move cards `m_<ticker>_<date>`; promises `p_<ticker>_<sha8>`; sources
  `s_<sha8>`.
- Priority 0–100; tiers: lead ≥ 70, line 40–69, buried < 40.

## Endpoints (v1)
| Method | Path | Returns |
| --- | --- | --- |
| GET | `/health` | `{ok, db, as_of}` |
| GET | `/brief?window=24h|3d|7d&from=&to=&fixture=1` | `Brief` |
| POST | `/feedback` `{card_id, action: "noted"|"less"}` | `{ok}` |
| GET | `/alerts?limit=` | `Alert[]` |
| GET/POST/PUT/DELETE | `/rules` | `Rule[]` / `Rule` |
| POST | `/rules/parse` `{text}` | `Rule` (preview, not saved) |
| GET | `/research/{ticker}` | `Dossier` (cached) or 404 `{gaps}` |
| POST | `/research/{ticker}` | SSE: `progress` events then `dossier` |
| POST | `/qa` `{ticker, question, card_id?}` | `{claims: Claim[], sources: Source[], model, cost}` |
| POST | `/push/subscribe` | `{ok}` |
| GET | `/push/vapid` | `{public_key}` |
| POST | `/admin/replay?date=` | `{fired}` |
| GET | `/admin/costs` | `{by_task, by_model, cache_hit_pct, total_inr}` |

## Types (TypeScript form; see §6 of FINN_MASTER_PROMPT.md)

```ts
type Tier = "lead" | "line" | "buried";
type Category = "results"|"ma"|"fund_raise"|"management_change"|"litigation"|"insider_trading"|"earnings_call"
  |"investor_meetings"|"credit_rating"|"dividend"|"bonus_split"|"capex"|"press_release"|"postal_ballot"|"agm_egm"
  |"pledging"|"unclassified";
type CardType = Category | "price_move" | "volume_spike";

interface Source { id: string; label: string; url: string; page?: number; quote?: string }
interface Chip { label: string; action: "ask" | "open_source" | "open_research" | "mute"; arg?: string }

interface Card {
  id: string; type: CardType; ticker: string; company: string; ts: string;
  tier: Tier; priority: number;
  headline: string; one_liner?: string;
  payload: ResultsPayload | PeoplePayload | MovePayload | GenericPayload;
  sources: Source[]; chips: Chip[];
  explained_by?: string[]; unexplained?: boolean;
}
interface ResultsPayload {
  period: string; basis: "consolidated" | "standalone"; unit: "₹ Cr"; variant: "standard" | "lender";
  metrics: { name: string; value: number; prev_q: number; prev_y: number; qoq_pct: number; yoy_pct: number }[];
  margins?: { name: string; pct: number; qoq_bps: number; yoy_bps: number }[];
  ebitda_method?: "reported" | "computed_incl_other_income" | "computed_excl_other_income";
  vs_guidance?: { status: PromiseStatus; text: string; promise_id: string };
  extraction: "xbrl" | "pdf_table" | "llm_fallback";
}
interface PeoplePayload {
  role: string; change: "appointment" | "resignation" | "retirement" | "cessation";
  incoming?: { name: string; bio_lines: string[]; prior_roles: string[]; bio_sources: Source[] };
  outgoing?: { name: string; tenure_years?: number };
  effective_date?: string; flags: string[];
}
interface MovePayload {
  close: number; change_pct: number; z: number; volume: number; vol_multiple: number;
  window_filings: { id: string; headline: string; category: Category }[];
  sparkline?: number[];            // last 20 closes (added in Phase 0 for the card UI)
}
interface GenericPayload { summary?: string; fields?: Record<string, string> }

interface Brief {
  window: { from: string; to: string };
  counts: { lead: number; line: number; buried: number }; minutes_saved: number;
  cards: Card[];
  buried: { category: Category; count: number; items: { id: string; headline: string; ticker: string }[] }[];
  as_of?: string;                  // snapshot stamp when serving last-good data
}

interface Rule {
  id: string; name: string; enabled: boolean;
  scope: { type: "portfolio" | "sector" | "ticker"; value?: string };
  condition:
    | { kind: "category"; categories: Category[]; min_priority?: number }
    | { kind: "price_move"; pct?: number; z?: number; direction?: "up" | "down" | "both" }
    | { kind: "volume"; multiple: number; lookback_days: number }
    | { kind: "guidance_gap"; min_gap_pct: number };
  channels: ("push" | "inbox" | "telegram")[];
  source_text?: string;
}
interface Alert { id: string; rule_id: string; rule_name: string; card: Card; fired_at: string; delivered: boolean }

type PromiseStatus = "kept" | "on_track" | "missed" | "revised_down" | "quietly_dropped" | "too_early";
interface PromiseRec {
  id: string; ticker: string; metric: string;
  target_text: string; target_low?: number; target_high?: number; unit?: string; period: string;
  said_in: string; speaker?: string; quote: string; source: Source;
  actual_text?: string; actual_value?: number; actual_source?: Source;
  status: PromiseStatus; later_mentions: { call: string; stance: "reiterated" | "raised" | "lowered" | "absent" }[];
  hard: boolean;
}

interface Claim { text: string; source_ids: string[]; verified: boolean }
interface Dossier {
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
interface ProgressEvent { step: string; status: "start" | "done" | "skip" | "error"; detail?: string; pct?: number }
```

## Deltas from master prompt §6 (recorded here, see DECISIONS 2026-11-11)
- `MovePayload.sparkline?: number[]` added (UI needs 20 closes; avoids a second request).
- `Brief.as_of?` added for snapshot mode.
- `Alert` and `ProgressEvent` shapes defined (master prompt referenced them without a shape).
