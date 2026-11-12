# FINN — STATE (living handoff)

> Update after every task. The section "NEXT SESSION STARTS HERE" must always be accurate.
> Last updated: 2026-11-12 10:30 IST

## Current phase
Phase 2 — Pull engine + people + push delivery. Phase 1 local acceptance met (real ranked brief, results cards
with XBRL numbers, swipe UI on real data); **deploys still pending user keys** (see Blockers). Pull engine backend
and the Research screen are built and run end-to-end locally in numbers-only mode (no LLM keys yet).

## Deadline tracker
| Phase | Target | Status |
| --- | --- | --- |
| 0 De-risk + scaffold | Wed 11 Nov | local done; deploys pending accounts |
| 1 Push backend + app shell | Thu 12 Nov | local done; deploys pending keys |
| 2 Pull engine + people + push delivery (tag v0.9) | Fri 13 Nov | ~50% (research backend + screen done; LLM sections, people, push, rules left) |
| 3 Product polish, freeze 20:00 IST | Sat 14 Nov | not started |
| 4 Harden + submit | Sun 15 Nov | not started |

## Last completed
- **Research screen** (2026-11-12 10:30): `web/components/research/{ResearchScreen,DossierView,Ledger,ClaimList}.tsx`,
  `web/app/research/page.tsx`. Ticker search + recent (localStorage) + suggested list; GET cached → else POST SSE
  with a live progress log (`researchStream` in `web/lib/api.ts`, fetch + ReadableStream, ignores `: ping` lines);
  verdict + cost receipt; Promise Ledger hero (counts, per-promise timeline said → later mentions → actual, tap →
  quote sheet with speaker/call); Snapshot · Financials (TTM + ratios grid) · Trajectory / Balance sheet / Cash
  quality (sparkline rows + code-written notes) · Bull/Bear · Sources · "Not covered" gaps; sticky ask bar → `/qa`
  claims with source chips; deep links `/research?t=INFY&q=…` from Brief chips. `SourceSheet` now takes any
  `{ticker, headline, sources}`. `npm run build` clean.
- **`.env` created** (2026-11-12): all secrets named with where-to-get-them comments; VAPID pair generated and
  filled; deploy tokens (GITHUB_TOKEN, VERCEL_TOKEN, RENDER_API_KEY) listed for CLI deploys. Waiting on user to fill.
- **Research backend** (2026-11-12 00:50, commits 51848c7 + b35f8dd): `api/llm/router.py` (SQL cache by
  sha256(model|prompt_version|inputs), JSON repair retry, provider fallback, ₹ cost, `/admin/costs`),
  `api/ingest/screener.py` (24h-cached tables + AR/concall links), `api/research/financials.py` (TTM, ratios,
  5y trajectory, D/E, net debt, WC days, CFO/PAT, FCF — all code), `docs.py` (PDF → speaker-turn chunks →
  fastembed bge-small → numpy cosine), `promises.py` (cheap-model extraction + quote verification + code-only
  matching vs screener actuals + later-mention tracking), `verify.py` (fuzzy quote + number check), `synthesize.py`,
  `qa.py`, `dossier.py` (progress callback, gaps[], cost receipt, cache by doc sha + prompt version),
  `routers/research.py` (GET cached / POST SSE / POST /qa), `jobs/run_research.py`. Prompts in `api/llm/prompts/`.
  INFY dossier without keys: 6 documents found, all numeric sections filled, 2 gaps (guidance, synthesis), ₹0.
- **Brief UI on real data** (2026-11-12 01:10): swipe with undo, source sheet, related filings, chips wired.
- **Results enrichment** `api/pipeline/enrich_results.py` (2026-11-12 00:30): XBRL → 4 metrics + margins, QoQ/YoY,
  lender variant; 18/20 results cards carry numbers with 0 LLM calls.
- Ingestion/pipeline/tests from Phase 1 (NSE filings, EOD prices, classifier 98.1%, scorer, collapsing, anomalies).

## In progress
- (none)

## Next 3 tasks
1. **Keys in → first LLM run**: once `.env` has a cheap + strong key, `make research T=INFY FORCE=1` and check
   the ledger (promises extracted, quotes verified, statuses), verdict/bull/bear, cost receipt; then the 5 research
   tickers + 1 unseen; fix prompt/verify issues; record ₹ per dossier in Metrics. Also cheap-LLM `one_liner` for
   generic "Disclosure under Reg 30" leads and SUZLON credit-rating cards.
2. **Deploys + cron** (needs DATABASE_URL + tokens): migration on Supabase, seed/eod/ingest against Supabase,
   `gh repo create` + push (or GITHUB_TOKEN via git), Vercel (root `web`, `NEXT_PUBLIC_API_URL`), Render blueprint +
   env vars, `.github/workflows/{filings,eod}.yml`.
3. **People + push + rules**: people enrichment (bio from filing), Web Push subscribe + VAPID send, rules CRUD +
   NL rule parsing, Rules screen, Alerts screen + replay a day.

## Blockers (user actions)
- Fill `.env` (repo root, git-ignored, already created with every key named): `GEMINI_API_KEY` (runs both the
  cheap and strong tiers), Supabase pooled `DATABASE_URL`, and GITHUB_TOKEN / VERCEL_TOKEN / RENDER_API_KEY
  for CLI deploys. Run `supabase/migrations/001_init.sql` in the Supabase SQL editor.
- A stale API server from an earlier session (PID 28484, started before the research router existed) still holds
  port 8000, so the web app's `/research` gets 404 from it. Stop it (close that terminal or
  `taskkill /PID 28484 /F`) and restart `uvicorn api.main:app --reload --port 8000`.
- Tavily key (optional) for bios.

## Live URLs & env status
| Item | Value / status |
| --- | --- |
| GitHub repo | not created |
| Web (Vercel) | not deployed |
| API host (Render) | not deployed; `render.yaml` ready |
| Supabase project | exists; migration not run; URL not in .env |
| Cheap / strong LLM keys | both tiers on Gemini; `GEMINI_API_KEY` blank in `.env` |
| Web search API key | none |
| VAPID keys | generated, in `.env` |
| Local | API `http://127.0.0.1:8000` · web `http://localhost:3000` · DB `data/finn.db` |

## Known issues
- Unknown ticker over SSE takes ~40 s to fail (screener retries) before the error event; UI shows the log meanwhile.
- Two "SUZLON: Credit Rating" leads (no detail in subject) → cheap-LLM one-liner (task 1).
- Generic headlines for "Disclosure under Regulation 30…" filings → cheap-LLM `one_liner` (task 1).
- Anomalies computed with default thresholds only; user rules must re-run `run_anomalies` with overrides.
- Classifier false positives into `results`: RELIANCE 27 Oct Jio Platforms notice, SUNPHARMA 12 Oct board-meeting
  outcome; enricher rejects them (2-day XBRL guard) but category/priority still wrong → add a rule.
- SQLite drops timezone on `filings.ts`; `filing_to_card` re-attaches IST. Postgres keeps it.
- `fitz` deprecation warning in `spikes/s5_pdf.py` only.

## Metrics to report in writeup (fill as measured)
| Metric | Value |
| --- | --- |
| Rule classifier coverage | 98.1% (262 real filings, 30 days) |
| Classifier accuracy (labelled) | see `pytest -s api/tests/test_classify.py` (58 labelled) |
| Event collapsing | 56 → 35 leads over 30 days |
| Anomalies (raw z → market-adjusted z) | 13 → 7 price moves; 19 → 5 unexplained (10 days) |
| ₹ per dossier (first run / cached) | ₹0 numbers-only (no keys yet) / — |
| Results cards with XBRL numbers | 18 of 20 primary results filings (30 days), 0 LLM calls, 0 gaps; 2 rejected by the 2-day guard |
| ₹ per day (push side) | ₹0 so far (no LLM calls yet) |
| Cache hit % | — |
| Claims dropped by verifier | — |

## NEXT SESSION STARTS HERE
- Sanity: `PYTHONUTF8=1 api/.venv/Scripts/python.exe -m pytest api/tests -q` → expect 34 passed.
- Servers: `api/.venv/Scripts/python.exe -m uvicorn api.main:app --reload --port 8000` (stop the stale PID 28484
  first); `cd web && npm run dev`. Open http://localhost:3000/research?t=INFY (cached dossier renders) and try
  PIDILITIND (streams a fresh build).
- Check `.env`: if a cheap + strong key are present → Next task 1. If `DATABASE_URL` is Postgres → task 2.
  If still blank → task 3 (people/push/rules) which needs no keys except VAPID (already generated).
- No files mid-edit. No failing tests.
