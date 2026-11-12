# FINN — DECISIONS (append-only, newest at bottom)

Format: `## YYYY-MM-DD — title` · Decision · Why · Rejected alternatives · Notes/spike findings

## 2026-11-11 — Product thesis: attention budget
- Decision: FINN optimises for how little the investor reads. Finite Brief with an end state; buried count; minutes saved.
- Why: brief says the scarce skill is filtering; makes product sense visible.
- Rejected: infinite feed; chat-first UI (poor for scanning — chat kept for follow-ups via chips).

## 2026-11-11 — Signature features
- Decision: Promise Ledger (hero of Pull, feeds results alerts), Explain the Move, volatility-aware thresholds,
  bio-from-filing, cost receipt, citation verifier, replay-a-day.
- Why: each maps to a graded criterion (creativity, judgment, efficiency) at low build cost.

## 2026-11-11 — Platform: PWA, not native
- Decision: Next.js installable PWA on Vercel with Web Push.
- Why: one link works on any phone for graders; no app-store/TestFlight delay.
- Rejected: Expo (build/distribution overhead in a 4-day window).
- Note: iOS Web Push only after Add to Home Screen → show install hint; in-app inbox always works.

## 2026-11-11 — Backend: FastAPI + Supabase + GitHub Actions
- Why: Python ecosystem for yfinance/PDF/scraping; Supabase gives Postgres + pgvector + storage free; Actions = free cron.

## 2026-11-11 — Model routing
- Decision: rules → parsers → cheap model (Gemini Flash-class / Groq Llama) → strong model (Claude Sonnet / GPT-class)
  only for synthesis, once per ticker per quarter. All calls cached by (model, prompt_version, input hash).
- Why: efficiency is bonus-graded; most work is extraction, not reasoning.

## 2026-11-11 — Numbers from code
- Decision: financial/trajectory/balance-sheet/cash sections computed from screener tables; results via XBRL first,
  PDF table + cheap LLM fallback; EBITDA computed as PBT + finance costs + D&A when not reported (method recorded).
- Lenders (banks/NBFCs) use NII / PPOP / provisions / PAT variant.

## 2026-11-11 — Data resilience
- Decision: app reads only from DB; scrapers run in jobs. NSE primary, BSE fallback. Snapshot mode with "as of" stamp.
- Why: NSE often blocks cloud IPs; a demo that doesn't run is the worst outcome.

## 2026-11-11 — Management bios
- Decision: extract profile from the appointment filing (primary), enrich with one web-search snippet; never scrape LinkedIn.

## 2026-11-11 — Portfolio
- 18 stocks (weights sum 100): RELIANCE 10, HDFCBANK 10, INFY 8, BAJFINANCE 8, LT 7, SUNPHARMA 6, TRENT 6, TITAN 5,
  ETERNAL 5, ASIANPAINT 4, INDIGO 4, ADANIPORTS 4, DIXON 6, POLYCAB 4, PERSISTENT 4, CDSL 4, DEEPAKNTR 3, SUZLON 2.
- Research set: INFY, BAJFINANCE, POLYCAB, PIDILITIND, TATAPOWER. Verify all symbols in yfinance (Zomato → ETERNAL;
  avoid Tata Motors post-demerger).

## 2026-11-11 — Scope cuts
- Out: intraday prices, news/broker notes, portfolio P&L, auth/multi-user, OCR, native apps, forensic AR notes.

## 2026-11-11 (19:30) — Repo root and runtime
- Decision: the folder `ENAM assignment` is the repo root (layout from master prompt §4 directly inside it).
  Python 3.12 via `py -3.12` with venv at `api/.venv` (3.11 not installed; 3.12 is fine for every dep).
- Why: user choice; avoids a nested folder graders must navigate.

## 2026-11-11 (19:30) — DB access layer: SQLAlchemy + DATABASE_URL, no pgvector dependency
- Decision: all DB access through SQLAlchemy 2. `DATABASE_URL` defaults to `sqlite:///data/finn.db` for local dev
  and tests; production uses the Supabase Postgres URL. Embeddings stored as float32 bytes in `chunks.embedding`;
  similarity search = numpy cosine over the ticker's chunks (at most a few thousand rows per ticker).
- Why: one code path that works offline, in CI, and in prod; removes pgvector + Supabase as a blocker for every
  local test; per-ticker chunk counts are far too small to need an ANN index.
- Rejected: pgvector-only (breaks local/CI without network); Supabase client SDK (ORM gives SQLite parity).
- Note: `supabase/migrations/001_init.sql` still ships (Postgres DDL) and is the schema of record; SQLAlchemy
  `create_all` mirrors it for SQLite.

## 2026-11-11 (19:30) — Embeddings: fastembed (ONNX) instead of sentence-transformers
- Decision: `fastembed` with `BAAI/bge-small-en-v1.5` (384-dim), ONNX runtime, ~100 MB, no torch.
- Why: Render free tier is 512 MB RAM; torch alone is >1 GB on disk and slow to cold-start.
- Rejected: sentence-transformers (torch); hosted embedding APIs (another key, another failure mode).

## 2026-11-11 (20:00) — Spike findings (Phase 0)
**yfinance** (`spikes/s1_yfinance.py`): all 20 symbols (18 portfolio + PIDILITIND, TATAPOWER) resolve with `.NS`;
batch `yf.download(period="400d")` returns 400 rows each in one call; `Ticker.info` gives sector/industry in 0.6s
(`industry="Banks - Regional"` for HDFCBANK → usable for lender detection alongside the seed's `is_lender`).

**NSE announcements** (`spikes/s2_nse.py`): works from a residential IP. Warm-up: GET the corporate-filings page
(the bare homepage returns 403 but the filings page sets cookies). Endpoint
`/api/corporate-announcements?index=equities[&symbol=]&from_date=DD-MM-YYYY&to_date=DD-MM-YYYY`.
Fields: `symbol`, `sm_name` (company), `desc` (exchange category text, e.g. "Updates", "Copy of Newspaper
Publication"), `attchmntText` (subject), `attchmntFile` (PDF on nsearchives.nseindia.com), `an_dt`/`sort_date`
("2026-11-04 21:01:36", IST), `hasXbrl`, `smIndustry`, `seq_id`. **Omitting `symbol` returns the whole market for
the window (17,506 rows / 30 days in 2.8s)** → ingestion = ONE call per window, filtered to the portfolio in code.
Decision: `nse.py` uses the all-equities call; `content_hash = sha256(symbol|sort_date|attchmntText|attchmntFile)`.

**NSE results + XBRL** (`spikes/s6_xbrl.py`): `/api/corporates-financial-results?index=equities&symbol=X&period=Quarterly`
returns 144 rows for INFY with `consolidated` ("Consolidated"/"Non-Consolidated"), `fromDate`, `toDate`,
`relatingTo`, `bank` (Y/N), and an `xbrl` URL. The XBRL (Ind-AS taxonomy) parses with lxml; tags:
`RevenueFromOperations`, `OtherIncome`, `Income` (total), `FinanceCosts`,
`DepreciationDepletionAndAmortisationExpense`, `ProfitBeforeTax`, `TaxExpense`, `ProfitLossForPeriod`;
context `OneD` = current quarter (startDate/endDate), `FourD` = YTD; prev-quarter / prev-year contexts to be
confirmed in enrich_results (fall back to the previous filing's XBRL or screener quarterly table).
Decision: results enrichment = XBRL for the current quarter + DB/screener for comparatives. Pick the
`consolidated` row when present, else standalone, and record `basis`.

**BSE announcements API** (`spikes/s3_bse.py`): 403 for a plain httpx client; attempts with browser-fingerprint
headers were out of bounds for this build, so BSE's JSON API is NOT used. BSE-hosted PDFs
(`bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=…`, `bseplus/AnnualReport/…`) download fine with a plain GET.
Decision: fallback for cloud-IP blocking of NSE is **run `make ingest` from a residential machine** (writes to
Supabase) plus snapshot mode; GitHub Actions cron is best-effort.

**screener.in** (`spikes/s4_screener.py`): `/company/{SYM}/consolidated/` returns 200 in 0.2s without login.
Sections with tables: `#quarters` (Sales, Expenses, Operating Profit, OPM, Other Income, Interest, Depreciation,
PBT, Tax, Net Profit, EPS — 13 quarters), `#profit-loss` (12 years), `#balance-sheet`, `#cash-flow`, `#ratios`
(debtor/inventory days, CCC, ROCE), `#shareholding`; `#insights` is login-gated (ignored). `#top-ratios` li list
gives Market Cap, P/E, ROCE, ROE etc. `#documents` lists annual reports (BSE/NSE PDFs) and per-quarter concall
links labelled "Transcript" / "PPT" / "REC". Use `selectolax.lexbor` (the `parser` backend is deprecated).

**Transcript PDFs** (`spikes/s5_pdf.py`): PyMuPDF text layer is present (2.1k chars/page). Format: participant
roster on page 1–2, then each speaker turn starts with the speaker's name on its own line (no colon); 104 turns in
the INFY Q2 FY27 call. Chunker: split on roster-name lines, merge to ~800 tokens, keep speaker + page.
Caveat: NSE's "Earnings Call Transcript" filing for INFY was the *media* call; prefer screener "Transcript" links.

**NSE annual reports**: `/api/annual-reports?index=equities&symbol=X` → `data[].fileName` (nsearchives PDF),
`fromYr`/`toYr`. Preferred over BSE links (same host as filings, already warmed up).

**Windows console**: set `PYTHONUTF8=1` for any script printing ₹ (cp1252 default).

## 2026-11-11 (21:00) — Market-adjusted z-score for Explain the Move
- Decision: `z = (ret − NIFTY ret) / std60(ret − NIFTY ret)`, std over the prior 60 sessions (excluding the day).
  NIFTY 50 (`^NSEI`) is stored in `prices_eod` under ticker `NIFTY`. Volume multiple = volume / prior-20-session mean.
- Why: with raw z, a broad rally day (NIFTY +2.4% on 2026-11-0x) flagged 13 "unexplained" leads across 18 stocks in
  10 days; market-adjusted z cut that to 7 moves / 5 unexplained and the survivors were genuinely stock-specific
  (DIXON +12% on 6× volume, BAJFINANCE +7.6%). A move explained by the index is not news.
- Price-move priority: base 0.6, intensity = 0.6 + 0.15·|z| (cap 1.5), +15 if unexplained. So an explained 2.5σ
  move is a line card (the filing itself is the lead), an unexplained one is a lead.

## 2026-11-11 (21:00) — Event collapsing + classifier findings on 262 real filings
- Decision: same ticker + category within 48h = one event. Highest-priority filing stays; the rest are demoted to
  buried with `payload.collapsed_into`; the primary gets `related_count`/`related_ids` (UI shows "+N related").
  Not applied to investor_meetings/unclassified (already buried).
- Why: results day produces 3–5 filings (outcome, press release, media release, presentation, newspaper copy).
  Without collapsing the brief had 56 leads in 30 days; with it, 35 leads / 24 line / 203 buried.
- Classifier: rule coverage 98.1% on the 30-day backfill (5 fallbacks, all "General Updates" with
  letterhead-only first pages → Tier 1 LLM in Phase 2). Hand-labelled set: `api/tests/fixtures/filings_labelled.json`
  (58 labelled of 60 random real filings); test asserts coverage ≥ 80% and accuracy ≥ 90%.
- NSE `desc` values seen (for the writeup): "Analysts/Institutional Investor Meet/Con. Call Updates" (64 of 262),
  "General Updates" (34), "Updates" (22), "Outcome of Board Meeting" (21), "Copy of Newspaper Publication" (15),
  "Press Release" (14), "Credit Rating" (8), "Allotment of Securities" (8), "Investor Presentation" (8) …
- Caveat for the writeup: the labelled set was also used to tune rules (100% after tuning). The honest claim is
  "≥ 90% on filings seen during development"; a held-out check on a fresh day's filings is a Phase 3 task.
- Ordering matters: earnings_call/investor_meetings rules run BEFORE results (transcripts mention "financial
  results"); routine buckets (ESOP, trading window, newspaper, certificates) run first of all.
- Buyback → `bonus_split` bucket (capital-return corporate action; taxonomy has no buyback category), intensity 1.4.
- Order wins → `press_release` (no "order" category); rumour verifications → `press_release` at full intensity.

## 2026-11-12 (12:30) — Promise ledger v2: dedupe, period normalisation, code-only later mentions
- Finding (INFY, first Gemini run, ₹4.54): 58 promises from 355 management chunks, but the same guidance was
  recorded up to 5× per call ("1.5% to 3.5% FY27" quoted five ways), non-guidance facts slipped in (nine-month
  margin, a client's $450 mn target, a market-size projection), "this year" / "the year" were left unnormalised so
  the code matcher skipped them, and the embedding-based later-mention check marked obvious reiterations "absent"
  (20,000 freshers mentioned in every call) or "lowered" on a stray "21%".
- Decision: prompt v2 (own-company forward commitments only; one record per commitment per chunk; `basis` field;
  fiscal year of the call given as [fy=FYnn] so "this year" → FY of the call). Code: `normalize_period`, `dedupe`
  by (call, metric, period, band), `hard` requires a period, later mentions come first from the extracted promises
  of later calls (same metric + horizon → raised/lowered/reiterated by band comparison), embedding search only as
  fallback; `revised_down` only when the latest mention is lower; bps-sized "margin" deltas are not compared with OPM.
- Decision: constant-currency growth guidance is compared with reported INR growth with a wider tolerance (±3 pp)
  and the caveat written into `actual_text` ("guidance is constant currency, not directly comparable"). The
  PromiseStatus enum is frozen, so no new "not comparable" status; the words carry the caveat.

## 2026-11-12 (12:15) — Supabase transaction pooler: disable psycopg prepared statements
- Finding: the first bulk insert through the pooler (port 6543, pgbouncer transaction mode) failed with
  `DuplicatePreparedStatement "_pg3_0" already exists`. Single-row writes worked, so seed/eod passed and only the
  258-row filings upsert failed.
- Decision: `create_engine(..., connect_args={"prepare_threshold": None})` for `+psycopg` URLs. Also: the router
  retries one transient 429/5xx/timeout per model after 4 s, and parses model JSON with `json_repair` when strict
  parsing fails (Gemini 3 flash-preview returned a JSON object with a missing comma; the repair round-trip failed).

## 2026-11-12 (11:15) — Gemini model IDs: 2.5 family is closed to new keys; pro tier needs billing
- Finding (first real run): `gemini-2.5-flash-lite`, `-flash`, `-pro` return 404 "no longer available to new users".
  `gemini-3.1-pro-preview`, `gemini-pro-latest`, `gemini-4-*` return 429 quota on this (free-tier) key.
  `gemini-3.8-flash` and `gemini-flash-latest` time out / "high demand". Working with JSON mode:
  `gemini-3.5-flash-lite` (≈2.6 s, priced by LiteLLM), `gemini-3.1-flash-lite` (1.7 s), `gemini-3.5-flash`
  (3.6 s, ~360 reasoning tokens per call), `gemini-3-flash-preview` (2.6 s).
- Decision: CHEAP = `gemini/gemini-3.5-flash-lite` → fallback `gemini/gemini-3.1-flash-lite`;
  STRONG = `gemini/gemini-3.5-flash` → fallback `gemini/gemini-3-flash-preview`. Groq fallback dropped from the
  defaults (no key). Model IDs live only in env/config, so this is a config change, not a code change.
- Why: the only free-tier models that answer reliably; flash-class is adequate for synthesis over code-computed
  numbers and verified quotes. Revisit if billing is enabled (pro preview) before the Sat freeze.

## 2026-11-12 (10:45) — Strong model on Gemini too
- Decision (user): `STRONG_MODEL=gemini/gemini-2.5-pro`, fallback `gemini/gemini-2.5-flash`; cheap tier unchanged
  (`gemini-2.5-flash-lite`, Groq fallback). One provider key (`GEMINI_API_KEY`) runs the whole app; Anthropic/OpenAI
  keys stay supported but optional.
- Why: one billing account and one key to manage before the deadline. Routing tiers and caching are unchanged;
  the 2.5-pro call is still limited to synthesis once per ticker per quarter.

## 2026-11-12 (00:30) — Results numbers: NSE integrated-filing XBRL, comparatives from earlier quarters
- Finding: `/api/corporates-financial-results` stops at the Dec-2024 quarter. From the quarter ended 31 Dec 2024
  (SEBI integrated filing) results live at `/api/integrated-filing-results?index=equities&symbol=X&period=Quarterly&size=100`
  → `data[]` with `type` ("Integrated Filing- Financials" / "- Governance"), `qe_Date` (DD-MON-YYYY), `consolidated`
  ("Consolidated"/"Standalone"), `audited`, `broadcast_Date`, `xbrl` (plain XML, the one we parse) and `ixbrl` (HTML).
  7 quarters are listed (Mar-2025 → Sep-2026), enough for QoQ and YoY; the legacy endpoint is merged in for older quarters.
- XBRL contexts: only `OneD` (the quarter, also for Q4), `FourD` (YTD), `OneI`/`PY_I` (instants). No prior-period facts
  in the file → comparatives come from the previous quarter's and the year-ago quarter's XBRL (same basis).
  Values are in rupees (÷1e7 → ₹ Cr) even though `LevelOfRounding` says Crores.
- Three tag sets (format detected from tags, not from `Company.is_lender`): Ind-AS corporate (`RevenueFromOperations`,
  `ProfitBeforeTax`, `FinanceCosts`, `DepreciationDepletionAndAmortisationExpense`, `OtherIncome`, `ProfitLossForPeriod`);
  banking (`InterestEarned`, `InterestExpended`, `OperatingProfitBeforeProvisionAndContingencies`,
  `ProvisionsOtherThanTaxAndContingencies`, `ProfitLossForThePeriod`); NBFC Ind-AS (`InterestEarned`, `FinanceCosts`,
  `ImpairmentOnFinancialInstruments`, `ProfitBeforeTax`, `ProfitLossForPeriod`).
- Decision: standard card = Revenue, EBITDA (= PBT + finance costs + D&A − other income, `computed_excl_other_income`),
  PBT, PAT + EBITDA/PAT margins. Lender card = NII, PPOP, Provisions, PAT (bank: NII = interest earned − expended,
  PPOP reported; NBFC: NII = interest earned − finance costs, PPOP = PBT + impairment). No margins for lenders.
- Decision: consolidated row preferred, else standalone; `basis` recorded. The XBRL must be broadcast within 2 days of
  the filing, otherwise the filing is not the results (a 12 Oct SUNPHARMA board-meeting notice would otherwise have
  carried numbers filed on 30 Oct) → card reverts to the generic form with `payload.results.gaps`.
- Decision: % change = (cur − prev) / |prev|; for a loss the headline states amounts ("loss ₹1,879 Cr (vs ₹2,582 Cr
  loss)") instead of a percentage against a negative base. Missing comparatives → 0 with a gap, never invented.
- Headline template: "{T} Q2 FY27: rev ₹49,244 Cr +10.7% YoY, PAT ₹7,838 Cr +6.3%" (falls back to %-only, then
  PAT-only, to stay ≤ 70). One-liner: EBITDA margin + bps deltas (or PPOP for lenders). Indian digit grouping.
- Result on the 30-day backfill: 18 of 20 primary results filings enriched, 0 LLM calls, 0 gaps; 2 correctly rejected.
