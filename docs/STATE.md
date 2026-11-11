# FINN — STATE (living handoff)

> Update after every task. The section "NEXT SESSION STARTS HERE" must always be accurate.
> Last updated: 2026-11-11 21:10 IST

## Current phase
Phase 1 — Push backend + app shell (started early, evening of Wed 11 Nov). Phase 0 local acceptance met;
**deploys still pending user account steps** (see Blockers). Schedule: roughly on track again — ingestion,
classifier, scorer, anomalies and explain-move are done a day early; results enrichment + swipe UI remain for Thu.

## Deadline tracker
| Phase | Target | Status |
| --- | --- | --- |
| 0 De-risk + scaffold | Wed 11 Nov | local done; deploys pending accounts |
| 1 Push backend + app shell | Thu 12 Nov | ~60% (ingest, classify, score, collapse, anomalies, explain done) |
| 2 Pull engine + people + push delivery (tag v0.9) | Fri 13 Nov | not started |
| 3 Product polish, freeze 20:00 IST | Sat 14 Nov | not started |
| 4 Harden + submit | Sun 15 Nov | not started |

## Last completed
- Ingestion: `api/ingest/nse.py` (one market-wide call per window, portfolio filter, dedupe, PDF first 3 pages via
  `documents.py`), `api/ingest/prices.py` (yfinance 400d incl. NIFTY; market-adjusted z), `jobs/seed.py`,
  `jobs/run_filings.py`, `jobs/run_eod.py`. Local DB has 262 filings (30d), 7,599 price rows, 18 anomalies.
- Pipeline: `classify.py` (rules, 98.1% coverage), `scoring.yaml` + `score.py` (priority, tiers, fiscal-label
  headlines, 48h event collapsing), `anomalies.py` + `explain_move.py` (market-adjusted z, ±48h filing link).
- Tests: `api/tests/test_brief.py`, `test_classify.py` (58 hand-labelled real filings; coverage/accuracy gates).
- Real brief works: `GET /brief?window=7d` → 3 lead · 10 line · 51 buried · 25.5 min saved.

## In progress
- (none)

## Next 3 tasks
1. **enrich_results.py** — XBRL from `/api/corporates-financial-results` (fields per DECISIONS spike), compute
   Revenue/EBITDA/PBT/PAT + QoQ/YoY + margins in code; lender variant (HDFCBANK, BAJFINANCE); comparatives from
   previous filings' XBRL (contexts) else screener quarterly table; attach `ResultsPayload` + headline with numbers.
   Acceptance: ≥ 1 real results card shows all four metrics with QoQ/YoY.
2. **Brief UI on real data** — swipe (framer-motion drag: right=noted, left=less → `POST /feedback`, toast+undo),
   "+N related" chip, source bottom sheet (PDF link), `NEXT_PUBLIC_FIXTURE` off by default once API deployed.
3. **Deploys + cron** — user steps below; then `.github/workflows/{filings,eod}.yml` (best-effort; NSE may block
   Actions IPs → fallback is `make ingest` locally against Supabase).

## Blockers (user actions)
- Install GitHub CLI → `gh auth login` → tell the agent; it will `gh repo create` + push.
- Create `.env` from `.env.example` with Supabase pooled `DATABASE_URL`, `GEMINI_API_KEY` (or `GROQ_API_KEY`),
  `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`). Run `supabase/migrations/001_init.sql` in the Supabase SQL editor.
- Vercel: import repo, root directory `web`, env `NEXT_PUBLIC_API_URL=<render url>`.
- Render: New → Blueprint → repo (picks `render.yaml`); set env vars (DATABASE_URL etc.).
- Tavily key (optional) for bios.

## Live URLs & env status
| Item | Value / status |
| --- | --- |
| GitHub repo | not created |
| Web (Vercel) | not deployed |
| API host (Render) | not deployed; `render.yaml` ready |
| Supabase project | exists; migration not run; URL not in .env |
| Cheap / strong LLM keys | not in .env |
| Web search API key | none |
| VAPID keys | not generated |
| Local | API `http://127.0.0.1:8000` · web `http://localhost:3000` · DB `data/finn.db` |

## Known issues
- Two "SUZLON: Credit Rating" leads (no detail in subject; body not parsed for the rating action) → needs LLM
  one-liner or deeper body regex in Phase 2.
- Generic headlines for "Disclosure under Regulation 30…" filings → Phase 2 cheap-LLM `one_liner`.
- `fitz` deprecation warning in `spikes/s5_pdf.py` only (prod code uses `pymupdf`).
- Anomalies computed with default thresholds only; user rules (Phase 2) must re-run `run_anomalies` with overrides.

## Metrics to report in writeup (fill as measured)
| Metric | Value |
| --- | --- |
| Rule classifier coverage | 98.1% (262 real filings, 30 days) |
| Classifier accuracy (labelled) | see `pytest -s api/tests/test_classify.py` (58 labelled) |
| Event collapsing | 56 → 35 leads over 30 days |
| Anomalies (raw z → market-adjusted z) | 13 → 7 price moves; 19 → 5 unexplained (10 days) |
| ₹ per dossier (first run / cached) | — |
| ₹ per day (push side) | ₹0 so far (no LLM calls yet) |
| Cache hit % | — |
| Claims dropped by verifier | — |

## NEXT SESSION STARTS HERE
- Sanity: `PYTHONUTF8=1 api/.venv/Scripts/python.exe -m pytest api/tests -q` → expect all green.
- Servers: `api/.venv/Scripts/python.exe -m uvicorn api.main:app --reload --port 8000`; `cd web && npm run dev`.
  Open http://localhost:3000 (fixture) and http://127.0.0.1:8000/brief?window=7d (real).
- If `.env` now has keys/DATABASE_URL: run migration, `make seed`, `make eod`, `make ingest` against Supabase.
- Then Next 3 tasks #1 (`api/pipeline/enrich_results.py`). Reuse `NSEClient.financial_results()` in
  `api/ingest/nse.py` and the XBRL tag list in DECISIONS "Spike findings". Spike script: `spikes/s6_xbrl.py`.
- No files mid-edit. No failing tests.
