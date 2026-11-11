# FINN — Master Build Prompt

> Paste this whole file as the first message to your coding agent (Claude Code, Cursor, etc.) in an empty repo.
> It is the single source of truth for WHAT to build. Session-to-session progress lives in `docs/STATE.md`
> (see §12 Context Protocol). Deadline: **Sun 15 Nov 2026**. Today's start: Wed 11 Nov 2026.

---

## 0. Your role and how to work

You are a senior full-stack AI engineer building **FINN**, a mobile-first financial investment agent, for the
ENAM Holdings "AI Engineer Build Challenge". You work with me (the candidate) as a pair. Rules:

1. **Thin-but-working beats broad-but-broken.** A demo that doesn't run is the worst outcome. Always keep `main` deployable.
2. Work in **small tasks** (≤ ~1 hour each). After every task: run it, test it, commit, and update `docs/STATE.md`.
3. **Numbers come from code; words come from models.** Never ask an LLM to do arithmetic or to recall facts about a company.
4. **Cheapest tool that works:** rules → parsers → cheap LLM → strong LLM. Cache every LLM call.
5. **Every claim carries a source.** No source, no claim.
6. Before starting any phase, re-read §12 and `docs/STATE.md`. If something in this prompt conflicts with a decision
   recorded in `docs/DECISIONS.md`, the DECISIONS file wins (it is newer).
7. When unsure about an external API shape (NSE, BSE, screener, yfinance), **spike it first** with a 20-line script in
   `/spikes`, record what you learned in `docs/DECISIONS.md`, then build.
8. Ask me only when a choice is expensive to reverse. Otherwise decide, record it in DECISIONS.md, and move on.

---

## 1. The assignment (what ENAM grades)

**Deliverables (due 15 Nov 2026):**
- A mobile-first **working prototype** (deployed link that works on a phone — we ship a PWA).
- The **GitHub repository**.
- The **AI build history** (coding-agent / LLM conversations used while building).
- A short **writeup** (covering email): what was built, key decisions and trade-offs, what was left out, what's next.
- Email to `assessment@enam.com`, subject exactly: `IIT Delhi – AI Engineer - 2027`.

**Graded on:** creativity, product sense, judgment, architecture — not completeness. Density and design both count.
"No AI slop": core, concise, beautifully presented, interactive. **Efficiency earns bonus points** (smart model routing,
caching, chunking; less spend for the same result). Free tiers are enough.

**Functional requirements from the brief:**

*Companies*
- Mock portfolio of 15–20 NSE/BSE companies, mixed sectors and sizes.
- 3–5 ad-hoc research companies (may be outside the portfolio).
- **The research engine must generalise to any NSE ticker** where data exists. Graders may test a ticker we didn't pick.

*Backend data sources (plumbing, don't over-engineer)*
- EOD price & volume (yfinance; `.NS` / `.BO` suffixes).
- Corporate announcements/filings from NSE/BSE (17-category taxonomy provided — §5).
- Fundamentals: annual reports + concall transcripts (links on screener.in or company IR site).

*PUSH — the app reaches out*
1. **Windowed digest**: user picks a window (default last 24h); every filing across the portfolio, filtered and
   prioritised; routine stuff collapsed/hidden.
2. **Triggered alerts**: material announcement of a type the user cares about; unusual EOD move — volume > ~2× recent
   average, or price move beyond ±X% in a day. **Thresholds must be user-configurable.**
3. Presentation requirements:
   - **Management change** → short background/bio of the incoming person (web enrichment is allowed here).
   - **Quarterly results** → first cut of **Revenue, EBITDA, PBT, PAT**, this quarter vs last quarter (QoQ) and vs same
     quarter last year (YoY), from the actual results filing.
   - Every other type → our judgment: one-line summary, or just surfaced at the right priority.

*PULL — on-demand research grounded ONLY in primary sources (annual reports + concall transcripts)*
- Menu: Business snapshot · Financial snapshot · Trajectory · Balance sheet · Cash quality · Narrative vs numbers ·
  Guidance · Bull vs bear. Pick what to build and how deep.
- **Most valued:** last 4 quarters — what management promised (guidance, growth commentary) vs what was delivered.
- **No broker notes, no news, no research reports, no model outside-knowledge** on the pull side.

*Interaction model*: experiment; mobile-first; show a point of view on how an investor should interact.

---

## 2. Product thesis (our point of view)

**Attention is the budget. FINN's success metric is how little the investor has to read.**

Three signature features (all MUST ship):
1. **Finite Brief** — inbox-zero for markets. A ranked card stack that *ends* ("You're caught up"). Header:
   "3 matter · 38 buried · ~19 min saved" (minutes saved = buried filings × 0.5 min). Swipe right = noted,
   swipe left = less like this (mutes category for that company and nudges weights).
2. **Promise Ledger** — every quantitative guidance statement from the last 4–6 concalls becomes a tracked record,
   scored *Kept / On track / Missed / Revised down / Quietly dropped / Too early* against actuals. Powers Pull, and feeds
   Push: results cards say "guided 18–20%, delivered 14% — 2nd miss in a row".
3. **Explain the Move** — each EOD anomaly is linked to filings in a ±48h window; no filing → flagged **Unexplained**
   and boosted in priority.

Also MUST ship (cheap, high signal):
4. **Volatility-aware thresholds** — default rule uses z-score vs the stock's own 60-day volatility; user can override
   with fixed ±X% and volume multiple. Natural-language rule input ("alert me if any bank falls 3% on 2× volume") parsed
   to rule JSON by a cheap LLM.
5. **Bio from the filing itself** — Indian listing rules require appointment filings to include a brief profile of the
   appointee; extract that first, then enrich with a web-search snippet. Label each source.
6. **Cost receipt** on every dossier: "₹0.38 · 41k tokens · 92% cached · 3 models".
7. **Citation verifier** — code checks every quoted snippet exists in the source (fuzzy ≥ 0.85) and every number exists
   in the source text or structured tables; failing claims are dropped and counted.
8. **Replay a day** — demo control that re-fires a past results-heavy day's alerts with short delays, so graders see Push
   working on a quiet day.

STRETCH (only after Phase 4 is green, in this order): 60-sec audio brief (browser SpeechSynthesis) → pre-results cheat
sheet (board-meeting intimation → push "results tomorrow: here's what they promised") → management credibility score on
portfolio grid → Telegram bot channel.

---

## 3. Tech stack (decided; change only via DECISIONS.md)

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router, TypeScript) + Tailwind + Framer Motion; installable **PWA** (manifest + service worker, Web Push via VAPID) |
| API | Python 3.11 + FastAPI (uvicorn), deployed on Render/Railway/Fly free tier |
| DB | Supabase Postgres + pgvector (+ Storage for PDFs) |
| Jobs | GitHub Actions cron (and runnable locally via `make ingest`) |
| LLM gateway | LiteLLM (or thin wrapper) with per-task routing + provider fallback + SQL cache |
| Cheap model | Gemini Flash-class (free tier) or Groq-hosted Llama — configurable via env |
| Strong model | Claude Sonnet-class or GPT-class — configurable via env; used rarely |
| Embeddings | Local `bge-small-en-v1.5` via sentence-transformers (or free API) |
| PDFs | PyMuPDF (text), pdfplumber (tables) |
| Scraping | httpx + selectolax/BeautifulSoup; polite delays; on-disk + DB cache |

Model IDs live ONLY in `.env` / `api/config.py`. Verify current model names and free-tier limits at setup time.

---

## 4. Repository layout

```
finn/
  CLAUDE.md                 # agent memory: rules + pointers (auto-loaded by Claude Code)
  README.md                 # graders' entry point
  Makefile                  # make dev | ingest | eod | research T=INFY | test | seed
  docs/
    STATE.md                # LIVING progress log — update after every task
    DECISIONS.md            # ADR-lite log of choices + spike findings
    CONTRACTS.md            # JSON contracts (§6), frozen in Phase 0
    WRITEUP.md              # draft of the covering email
    build-history/          # exported agent/LLM sessions (one file per session)
  spikes/                   # throwaway API probes
  api/
    main.py  config.py  db.py
    routers/   brief.py alerts.py rules.py research.py qa.py admin.py push.py
    ingest/    nse.py bse.py prices.py screener.py documents.py
    pipeline/  classify.py score.py enrich_results.py enrich_people.py anomalies.py explain_move.py
    research/  chunk.py extract_guidance.py ledger.py sections.py synthesize.py verify.py
    llm/       router.py cache.py prompts/*.md cost.py
    tests/
  jobs/        run_filings.py run_eod.py replay_day.py
  web/
    app/ (brief) (alerts) (research)/[ticker] (rules) (settings)
    components/ cards/ ledger/ charts/ ui/
    lib/ api.ts types.ts push.ts
    public/ manifest.json sw.js icons/
  supabase/ migrations/*.sql  seed/portfolio.csv
  .github/workflows/ filings.yml eod.yml
```

---

## 5. Domain reference (from the challenge's companion doc)

**Announcement categories:** results · M&A · fund_raise · management_change · litigation · insider_trading ·
earnings_call · investor_meetings · credit_rating · dividend · bonus_split · capex · press_release · postal_ballot ·
agm_egm · pledging · unclassified (ESOP allotments, compliance certificates, ESG reports, auditor appointments).

**Definitions:** Revenue = top line. EBITDA = earnings before interest, tax, depreciation & amortisation
(compute as PBT + finance costs + D&A when not reported; record whether other income is included). PBT = profit
before tax. PAT = profit after tax. Margin = metric ÷ revenue. QoQ = vs previous quarter. YoY = vs same quarter last
year. Cash conversion = CFO ÷ PAT. FCF = CFO − capex. D/E = debt ÷ equity.

**Lenders (banks/NBFCs):** EBITDA is meaningless. Results card uses a lender variant: Net Interest Income, Operating
Profit (PPOP), Provisions, PAT. Detect via sector/industry or presence of "interest earned" rows.

**Indian fiscal labels:** FY27 = Apr 2026–Mar 2027. Q1 = Apr–Jun, Q2 = Jul–Sep, Q3 = Oct–Dec, Q4 = Jan–Mar.
Show amounts in ₹ Cr, changes in %, margin changes in bps.

---

## 6. Data contracts (freeze in Phase 0 → `docs/CONTRACTS.md` and `web/lib/types.ts` + pydantic models)

```ts
type Tier = "lead" | "line" | "buried";
type Category = "results"|"ma"|"fund_raise"|"management_change"|"litigation"|"insider_trading"|"earnings_call"
  |"investor_meetings"|"credit_rating"|"dividend"|"bonus_split"|"capex"|"press_release"|"postal_ballot"|"agm_egm"
  |"pledging"|"unclassified";
type CardType = Category | "price_move" | "volume_spike";

interface Source { id: string; label: string; url: string; page?: number; quote?: string }
interface Chip { label: string; action: "ask" | "open_source" | "open_research" | "mute"; arg?: string }

interface Card {
  id: string; type: CardType; ticker: string; company: string; ts: string;   // ISO
  tier: Tier; priority: number;                                              // 0–100
  headline: string;            // ≤ 70 chars, factual, no adjectives
  one_liner?: string;          // ≤ 140 chars, why it matters
  payload: ResultsPayload | PeoplePayload | MovePayload | GenericPayload;
  sources: Source[]; chips: Chip[];
  explained_by?: string[];     // filing ids (move cards)
  unexplained?: boolean;
}

interface ResultsPayload {
  period: string;              // "Q2 FY27 (Jul–Sep 2026)"
  basis: "consolidated" | "standalone"; unit: "₹ Cr"; variant: "standard" | "lender";
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
  effective_date?: string; flags: string[];   // e.g. "unscheduled exit", "interim appointment"
}

interface MovePayload {
  close: number; change_pct: number; z: number; volume: number; vol_multiple: number;
  window_filings: { id: string; headline: string; category: Category }[];
}
interface GenericPayload { summary?: string; fields?: Record<string, string> }

interface Brief {
  window: { from: string; to: string };
  counts: { lead: number; line: number; buried: number }; minutes_saved: number;
  cards: Card[];                                   // lead + line, priority desc
  buried: { category: Category; count: number; items: { id: string; headline: string; ticker: string }[] }[];
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
  source_text?: string;                             // the natural-language rule as typed
}

type PromiseStatus = "kept" | "on_track" | "missed" | "revised_down" | "quietly_dropped" | "too_early";
interface PromiseRec {
  id: string; ticker: string; metric: string;       // "revenue_growth", "ebitda_margin", "capex", "plant_commissioning"...
  target_text: string; target_low?: number; target_high?: number; unit?: string; period: string;
  said_in: string; speaker?: string; quote: string; source: Source;
  actual_text?: string; actual_value?: number; actual_source?: Source;
  status: PromiseStatus; later_mentions: { call: string; stance: "reiterated" | "raised" | "lowered" | "absent" }[];
  hard: boolean;                                    // true = numeric, matched in code
}

interface Claim { text: string; source_ids: string[]; verified: boolean }
interface Dossier {
  ticker: string; name: string; as_of: string; basis: "consolidated" | "standalone";
  verdict: Claim[];                                 // 3 lines max, top of screen
  snapshot?: { what: Claim[]; segments: { name: string; share_pct: number }[] };
  financials: { ttm: Record<string, number>; ratios: Record<string, number> };
  trajectory: { years: string[]; series: Record<string, number[]>; notes: Claim[] };
  balance_sheet: { de: number[]; net_debt: number[]; wc_days: number[]; notes: Claim[] };
  cash_quality: { cfo_pat: number[]; fcf: number[]; flag?: string; notes: Claim[] };
  ledger: { summary: Record<PromiseStatus, number>; promises: PromiseRec[]; narrative: Claim[] };
  bull: Claim[]; bear: Claim[];                     // 3 each
  sources: Source[]; gaps: string[];                // e.g. "No concall transcripts found"
  cost: { inr: number; tokens_in: number; tokens_out: number; cache_hit_pct: number; models: string[] };
}
```

---

## 7. Backend specs

### 7.1 Database (Supabase migration `001_init.sql`)
Tables: `companies(ticker pk, name, nse_symbol, bse_code, sector, industry, is_lender, in_portfolio, weight)`,
`prices_eod(ticker, date, open, high, low, close, volume, pk(ticker,date))`,
`filings(id pk, ticker, exchange, ts, subject, raw_category, body_text, attachment_url, content_hash unique,
category, category_conf, classifier, priority, tier, headline, one_liner, payload jsonb, created_at)`,
`anomalies(id, ticker, date, kind, value, z, vol_multiple, explained_by text[], unexplained bool)`,
`rules`, `alerts(id, rule_id, card_id, fired_at, delivered bool)`, `push_subscriptions`,
`documents(id, ticker, kind[ar|concall|results|ppt], period, url, sha256, text_path, pages)`,
`chunks(id, document_id, ticker, period, speaker, page, text, embedding vector(384))`,
`promises` (PromiseRec), `dossiers(ticker, as_of, json, prompt_version)`,
`llm_cache(key pk, model, prompt_version, input_hash, output jsonb, tokens_in, tokens_out, cost_inr, created_at)`,
`feedback(card_id, ticker, category, action[noted|less], ts)`.

### 7.2 Ingestion
- **prices.py**: yfinance download 400 days for all portfolio tickers (batch), upsert. Compute `vol_avg20`, `ret`,
  `vol60` (std of daily returns), `z = ret / vol60`.
- **nse.py**: session warm-up GET `https://www.nseindia.com` with browser headers to get cookies, then
  `GET /api/corporate-announcements?index=equities&symbol=<SYM>&from_date=DD-MM-YYYY&to_date=DD-MM-YYYY`.
  Map fields (subject/desc, category text, attachment URL, timestamp) — confirm exact field names in the spike.
  Expect blocking from cloud IPs: retry with backoff, then fall back to **bse.py** (BSE announcements API with
  `Referer: https://www.bseindia.com/`; confirm endpoint + params in the spike). Dedupe on `content_hash`.
- **Backfill** 30 days for the portfolio on first run. Store attachments' text (first 3 pages) for classification.
- **screener.py**: `https://www.screener.in/company/<SYM>/consolidated/` (fallback `/company/<SYM>/`). Parse
  quarterly results, P&L, balance sheet, cash flow, ratios, shareholding tables, and the Documents section
  (annual report + concall transcript links). Cache HTML for 24h. 1.5s delay between requests.
- **documents.py**: download PDFs (cache by sha256), extract text per page with PyMuPDF; detect empty text layer →
  mark `scanned=true`, skip, record a gap.

### 7.3 Push pipeline
**classify.py** — Tier 0 rules (no LLM): map exchange category/subject keywords → category. Examples:
"financial results", "outcome of board meeting" + "results" → results; "appointment", "resignation", "cessation",
"KMP", "director" → management_change; "credit rating" → credit_rating; "acquisition", "amalgamation", "scheme of
arrangement", "joint venture", "subsidiary" → ma; "allotment" + "ESOP/ESOS" → unclassified; "trading window" →
unclassified; "transcript", "conference call", "audio recording" → earnings_call; "analyst/investor meet" →
investor_meetings; "pledge", "encumbrance" → pledging; "SAST", "Reg 7(2)", "PIT" → insider_trading.
Log coverage. Tier 1: cheap LLM on subject + first page for leftovers, JSON `{category, intensity, confidence}`.
Target: ≥ 80% rule coverage, ≥ 90% accuracy on a 50-filing hand-labelled set in `api/tests/fixtures/`.

**score.py** —
`priority = clamp(100 × base[category] × intensity × pos_weight_factor × surprise × pref, 0, 100)` where
`base`: results 0.9, management_change 0.8 (CEO/CFO/MD) / 0.5 (others), ma 0.85, fund_raise 0.7, litigation 0.7,
credit_rating 0.75 (0.15 if reaffirmed), pledging 0.7 (increase) / 0.3, insider_trading 0.45, capex 0.5,
press_release 0.4, dividend 0.3, bonus_split 0.35, earnings_call 0.35, investor_meetings 0.1, agm_egm 0.15,
postal_ballot 0.15, unclassified 0.05. `intensity` ∈ [0.3, 1.5] from refinement rules (intimation vs outcome,
upgrade vs reaffirm, size vs market cap). `pos_weight_factor = 0.8 + 2 × weight`. `surprise` ∈ [1, 1.5]
(guidance gap, same-day |z| > 2). `pref` from feedback swipes ∈ [0.5, 1.2]. Tiers: lead ≥ 70, line 40–69, buried < 40.
Keep all constants in one `scoring.yaml` so they're tunable and explainable in the writeup.

**enrich_results.py** — order: (1) XBRL attached to the NSE results filing → parse revenue, finance costs, D&A,
PBT, PAT, other income; (2) pdfplumber table extraction + cheap LLM to map rows → fields (strict JSON, numbers must
appear in page text); (3) cross-check against screener quarterly table; flag mismatch > 2%. Pull prev-quarter and
prev-year values from DB/screener. Compute QoQ/YoY and margins in code. Attach `vs_guidance` from `promises`.

**enrich_people.py** — cheap LLM extracts `{name, role, change, effective_date, profile_text}` from the filing text
(appointment filings usually contain a brief profile). Then one web search (Tavily/Serper/Brave free tier) for
`"<name>" <company> LinkedIn` → take title/snippet only. Produce ≤ 3 bio lines + prior roles; label each source.
Never scrape LinkedIn pages directly.

**anomalies.py + explain_move.py** — after EOD load: flag `|z| ≥ rule.z` or `|ret| ≥ rule.pct` or
`volume ≥ multiple × vol_avg20`. Look up filings for the ticker in [date−2d, date+1d]. If any with priority ≥ 40 →
explained_by; else `unexplained=true`, priority += 15.

**alerts** — evaluate enabled rules on each new card/anomaly; write `alerts`; send Web Push (pywebpush + VAPID) to all
subscriptions; payload = `{title, body, url:"/card/<id>"}`.

**replay_day.py** — given a date, re-emit that day's cards as alerts with 3s spacing (API: `POST /admin/replay?date=`).

### 7.4 Pull / research engine (works for ANY NSE symbol)
Endpoint `POST /research/{ticker}` → SSE stream of progress events, then final `Dossier`. `GET` returns cached.
Steps:
1. Resolve symbol (yfinance `.NS` check + screener page exists). Unknown → clear error.
2. **Code-only sections**: financials, trajectory (5y revenue/EBITDA/PAT, CAGR, margin direction), balance sheet
   (D/E, net debt, working-capital days), cash quality (CFO/PAT, FCF; flag if CFO/PAT < 0.7 for 3 of 5 years).
3. **Docs**: latest annual report + last 4–6 concall transcripts. Chunk transcripts by speaker turn (merge to
   ~800 tokens, keep speaker + page); AR by headings, but only parse: business overview, MD&A, segment note.
   Embed chunks → pgvector.
4. **Guidance extraction** (cheap model, batched 5 chunks/call, JSON mode): only management speakers; output
   PromiseRec drafts with exact `quote`. Prompt file `prompts/extract_guidance.md` (v1). Drop any record whose quote
   isn't found in the chunk text.
5. **Matching** (code): hard promises (revenue growth, margin, capex amount, debt) → compare against screener
   quarterly/annual actuals for the target period → status. Track `later_mentions` by searching subsequent calls'
   chunks for the metric (embedding + keyword). Absent in next 2 calls → `quietly_dropped`.
6. **Synthesis** (strong model, ONE call per ticker per quarter): input = PromiseRecs + code-computed tables + top-k
   chunks for soft promises; output = narrative claims, soft-promise statuses, verdict (3 lines), bull (3), bear (3),
   snapshot text — each as `Claim{text, source_ids}`. Prompt file `prompts/synthesize.md`. System rule: use ONLY the
   supplied material; if not supported, say "not disclosed".
7. **verify.py**: quotes fuzzy-match source text (rapidfuzz partial_ratio ≥ 85); every number in a claim must appear in
   source text or computed tables (±1% tolerance after unit normalisation). Unverified → removed and counted.
8. Cache dossier by `(ticker, latest_doc_sha, prompt_version)`. Record cost.
9. Graceful degradation: missing transcripts → numbers-only dossier + `gaps[]`. Never fill gaps from model memory.

**Q&A** `POST /qa {ticker, question, card_id?}` — retrieve top-8 chunks (filter by ticker, optional period) + relevant
tables; cheap model by default; escalate to strong if question contains why/compare/should/risk or cheap answer has
<2 verified claims. Same verifier. Return claims + sources.

### 7.5 LLM router (`llm/router.py`)
`call(task, prompt_version, inputs, schema)` → looks up `llm_cache` by `sha256(model|prompt_version|canonical_inputs)`;
on miss calls the model mapped for `task` in `config.TASK_MODELS`, validates JSON against pydantic schema (1 repair
retry), stores tokens + ₹ cost. Fallback provider on 429/5xx. `GET /admin/costs` → totals by task/model + cache hit %.
Tasks: `classify`, `one_liner`, `results_map`, `people_extract`, `nl_rule`, `guidance_extract`, `synthesize`, `qa`.

---

## 8. Frontend specs (the heart of the grade)

**Principles:** mobile-first (design at 390×844, test at 360), one-thumb reach, dense but calm, no chat-by-default.
Tabular numerals everywhere numbers align. Green/red ONLY for directional numbers; one accent colour for priority.
Dark mode default + light mode. Respect `prefers-reduced-motion`. Every card readable in < 5 seconds.

**Navigation (bottom bar):** Brief · Alerts · Research · Rules. Settings via avatar.

**Brief screen**
- Header: window chips (24h default, 3d, 7d, custom) · "3 matter · 38 buried · ~19 min saved".
- Card stack (lead cards full, line cards compact rows). Swipe right = noted, left = less like this (toast + undo).
- End state: "You're caught up." + Buried drawer grouped by category with counts (expandable).
- Optional: ▶ Listen (audio brief, stretch).

**Card designs**
- *Results*: ticker + period; 4-row mini table (Revenue, EBITDA, PBT, PAT) × (value ₹ Cr, QoQ %, YoY %), margin line in
  bps; vs-guidance pill (Kept/Missed…); extraction badge (XBRL/PDF); chips: "vs guidance?", "Open filing", "Research".
- *Management change*: "CFO: A → B"; incoming person 3 bio lines + prior roles; flags; sources labelled
  ("From filing", "Web").
- *Move*: price/volume sparkline (20d), z-score badge, "Explained by: <filing>" or **Unexplained** warning style.
- *Generic*: headline + one-liner + source.
- Every card: source chip opens a bottom sheet with the PDF link/page and quote.

**Alerts screen**: chronological inbox of fired alerts; "Replay a day" control (date picker) in a demo menu.

**Research screen** `/research/[ticker]`
- Search any NSE ticker (with recent + suggested list). First run shows a streaming progress log (real SSE events).
- Top: verdict (3 lines) + cost receipt.
- **Promise Ledger (hero)**: summary counts; per-metric vertical timeline (promise dot → actual dot, colour by
  status); tap → quote sheet with speaker, call, page.
- Sections: Snapshot · Financials · Trajectory (sparklines) · Balance sheet · Cash quality · Bull / Bear.
- Sticky ask bar for grounded Q&A; answers render as claims with source chips.
- `gaps[]` shown honestly in a muted note.

**Rules screen**: defaults on; sliders (sensitivity → z, volume multiple, fixed ±%); category toggles; NL rule input
→ preview parsed rule → save. "Enable notifications" button (handles iOS: show Add-to-Home-Screen instructions).

**Copy rules (anti-slop):** no "In a significant development", no "it is worth noting", no emojis, no exclamation
marks, no adjectives without numbers. Headlines are facts. Max lengths enforced in schema.

---

## 9. Portfolio seed (`supabase/seed/portfolio.csv`) — verify every symbol with yfinance in Phase 0

RELIANCE 10, HDFCBANK 10 (lender), INFY 8, BAJFINANCE 8 (lender), LT 7, SUNPHARMA 6, TRENT 6, TITAN 5, ETERNAL 5,
ASIANPAINT 4, INDIGO 4, ADANIPORTS 4, DIXON 6, POLYCAB 4, PERSISTENT 4, CDSL 4, DEEPAKNTR 3, SUZLON 2 (weights %, sum 100).
Research demo set: INFY, BAJFINANCE, POLYCAB + outside portfolio: PIDILITIND, TATAPOWER.
Generalisation test: 3 random tickers incl. one small-cap with thin documents.

---

## 10. Phases and acceptance criteria

**Phase 0 — De-risk + scaffold (Wed 11 Nov)**
- Spikes: NSE fetch (local + GitHub Actions), BSE fallback, yfinance all 18, screener parse INFY, one transcript text
  extraction, one XBRL results file. Findings → DECISIONS.md.
- Repo + layout (§4), Supabase migration, `.env.example`, Vercel + API host deployed "hello world".
- CONTRACTS.md + `types.ts` + pydantic models + 10 fixture cards.
- ✅ Done when: both apps deployed; fixtures served from `/brief?fixture=1`; STATE.md updated.

**Phase 1 — Push backend + app shell (Thu 12 Nov)**
- Ingestion (filings + EOD) with 30-day backfill; classifier; scorer; tiers; anomalies; explain-move; results enrichment.
- PWA shell, bottom nav, Brief screen with swipe on real data.
- ✅ Done when: `/brief?window=7d` returns real ranked cards for the portfolio; ≥ 1 real results card shows all four
  metrics with QoQ/YoY; deployed URL shows it on a phone.

**Phase 2 — Pull engine + people + push delivery (Fri 13 Nov)**
- Screener + documents + chunks + embeddings; guidance extraction; ledger matching; synthesis; verifier; cache; costs.
- People enrichment. Web Push + rules CRUD + NL rule parsing.
- Research screen with Ledger timeline + sections + source sheets.
- ✅ Done when: dossiers for the 5 research tickers + 1 unseen ticker render on phone; a rule fires a real push
  notification; `/admin/costs` shows totals. **This deploy is the safety net — tag it `v0.9`.**

**Phase 3 — Product polish (Sat 14 Nov)**
- Design pass on all cards (density, hierarchy, ₹ Cr/bps formatting, empty/loading/error states, skeletons).
- Follow-up chips + Q&A; Replay a day; cost receipt; time-saved meter.
- Stretch in order (§2). **Feature freeze 20:00 IST.** Run generalisation test.
- ✅ Done when: a stranger can install the PWA and complete Brief → card → Research → ask, with no dead ends.

**Phase 4 — Harden + submit (Sun 15 Nov)**
- Real-device test (Android + iOS installed PWA); fix top 5 issues only.
- Snapshot mode: if a live source fails, serve last good data with an "as of" stamp.
- README (architecture diagram, model routing table, measured costs, local setup, known limits).
- 2-minute demo video; export build history to `docs/build-history/`; WRITEUP.md → email.
- ✅ Done when: email sent with prototype link, repo link, build history, writeup. Target: early evening IST.

---

## 11. Testing and quality gates
- `api/tests`: classifier accuracy on labelled fixtures; scorer ordering snapshot; results math (QoQ/YoY/margins/EBITDA
  method) on 3 known filings; verifier rejects a fabricated quote and a fabricated number; research on a ticker with
  no transcripts degrades cleanly.
- `web`: Playwright smoke at 390px: Brief loads, swipe works, card opens source sheet, research renders ledger.
- Before each deploy: `make test` green; Lighthouse PWA installable; no console errors.

---

## 12. CONTEXT PROTOCOL (survive context limits and new sessions)

The conversation WILL run out of context. Durable memory lives in files, never only in chat.

**Files that carry memory**
- `CLAUDE.md` — stable rules + pointers (auto-loaded by Claude Code every session). Keep ≤ 80 lines.
- `docs/STATE.md` — the living handoff. Sections: Current phase · Last completed · In progress · Next 3 tasks ·
  Blockers · Live URLs & env status · Known issues · "NEXT SESSION STARTS HERE".
- `docs/DECISIONS.md` — append-only, dated: decision · why · alternatives rejected · spike findings.
- `docs/CONTRACTS.md` — frozen schemas; changes require a DECISIONS entry.
- `docs/build-history/` — exported sessions (deliverable for ENAM).

**Rules**
1. **Start of every session:** read `CLAUDE.md`, `docs/STATE.md`, `docs/DECISIONS.md` (last 15 entries), and
   `git log --oneline -15`. Then state in 3 lines: where we are, what you'll do next, any blocker. Then continue.
2. **After every completed task:** commit (`feat|fix|chore(scope): …`) and update STATE.md (move item to Last completed,
   refresh Next 3 tasks). Small diffs, frequent commits.
3. **Every ~45 minutes of work, before any large refactor, and whenever context feels long:** write a full handoff in
   STATE.md under "NEXT SESSION STARTS HERE" (exact next command to run, files mid-edit, failing tests, open questions)
   and commit with `chore(state): handoff`.
4. **When context is nearly full:** stop feature work, do rule 3, then tell me: "Context nearly full — handoff saved.
   Start a new session with RESUME_PROMPT." (In Claude Code you may also use `/compact` with an instruction to keep
   the STATE.md summary.)
5. Never keep important facts only in chat: API quirks, credentials status, URLs, chosen thresholds → files.
6. At the end of each day: export the session transcript to `docs/build-history/<date>-<topic>.md` (Claude Code:
   `/export`, or copy from `~/.claude/projects/`), and push.

---

## 13. Out of scope (say so in the writeup)
Intraday/live prices; news, broker notes, social sentiment; portfolio P&L tracking and holdings import; auth and
multi-user; OCR for scanned PDFs; native apps; forensic AR notes (contingent liabilities, RPTs, auditor
qualifications — listed as "next").

## 14. Writeup skeleton (`docs/WRITEUP.md`)
1. What I built (2 sentences + link). 2. Point of view (attention budget; cards for scanning, chat for follow-ups;
Push and Pull share one memory). 3. Key decisions & trade-offs (rules before models; numbers from code; XBRL before
PDFs; citation verifier; PWA over native; volatility-aware thresholds). 4. Cost (measured ₹ per brief, per dossier,
per day; cache hit %). 5. Left out on purpose. 6. Next (forensic layer; peer ledger; learned priority model;
voice-first).

---

**Start now:** create `CLAUDE.md`, `docs/STATE.md`, `docs/DECISIONS.md` from the templates I provide (or from §12 if
none), then begin Phase 0 with the spikes. Report findings in 5 lines before scaffolding.
