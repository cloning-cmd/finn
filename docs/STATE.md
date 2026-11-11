# FINN — STATE (living handoff)

> Update after every task. The section "NEXT SESSION STARTS HERE" must always be accurate.
> Last updated: 2026-11-12 01:10 IST

## Current phase
Phase 1 — Push backend + app shell. Phase 0 local acceptance met; **deploys still pending user account steps**
(see Blockers). Backend side of Phase 1 is done (ingest, classify, score, collapse, anomalies, explain, results
numbers); the swipe UI on real data remains for Thu.

## Deadline tracker
| Phase | Target | Status |
| --- | --- | --- |
| 0 De-risk + scaffold | Wed 11 Nov | local done; deploys pending accounts |
| 1 Push backend + app shell | Thu 12 Nov | ~75% (backend done incl. results numbers; swipe UI + deploys left) |
| 2 Pull engine + people + push delivery (tag v0.9) | Fri 13 Nov | not started |
| 3 Product polish, freeze 20:00 IST | Sat 14 Nov | not started |
| 4 Harden + submit | Sun 15 Nov | not started |

## Last completed
- **Brief UI on real data** (2026-11-12 01:10): `web/.env.local` fixture off, default window 7d (+30d option),
  `SwipeCard` (framer-motion drag; right=noted, left=less; feedback POST delayed 4s so Undo just cancels),
  `Toast`, `SourceSheet` (bottom sheet: filing PDF, XBRL, related filings), chips wired (open_source → sheet,
  open_research/ask → /research?t=, mute → less), line cards expand on tap. API: collapsed filings ride along as
  `s_rel_*` sources (`with_related` in `api/routers/brief.py`) so the UI shows "+N related" without a contract
  change. `npm run build` clean.
- **Results enrichment** `api/pipeline/enrich_results.py` (2026-11-12 00:30): NSE integrated-filing XBRL → Revenue/
  EBITDA/PBT/PAT (+ margins) or NII/PPOP/Provisions/PAT for banks and NBFCs, QoQ/YoY from the previous quarters'
  XBRL, numeric headlines + one-liners, XBRL source + "Open XBRL" chip, 2-day filed-date guard, loss-aware copy.
  Wired into `jobs/run_filings.py` and `make enrich`. 18/20 primary results cards on the 30-day backfill carry
  numbers (0 LLM calls); tests `api/tests/test_results.py` on trimmed real XBRL fixtures (INFY, HDFCBANK, BAJFINANCE).
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
1. **Deploys + cron** — waiting on user: keys pasted in chat → `.env`; `gh` installed + authed; Vercel token +
   Render API key. Then: migration on Supabase, seed/eod/ingest against Supabase, `gh repo create` + push, Vercel
   (root `web`, `NEXT_PUBLIC_API_URL`), Render blueprint + env vars, `.github/workflows/{filings,eod}.yml`.
2. **Phase 2 kick-off** — LLM router + SQL cache (`api/llm/router.py`), cheap-LLM `one_liner` for generic
   "Disclosure under Reg 30" leads and the SUZLON credit-rating cards, Tier-1 LLM classify for the 5 fallbacks.
3. **Pull engine** — `make research T=INFY`: screener tables → financials/trajectory/balance sheet/cash; annual
   report + concall ingestion → chunks/embeddings; promise ledger; verifier; dossier endpoint + Research screen.

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
- Classifier false positives into `results`: RELIANCE 27 Oct "Trading in equity shares of Jio Platforms…" and the
  SUNPHARMA 12 Oct board-meeting outcome (both mention "financial results" in the body). The enricher rejects them
  (XBRL not filed within 2 days) so they show generic copy, but the category/priority is still wrong → add a
  "subsidiary results / board meeting scheduled" rule in Phase 2.
- SQLite drops timezone on `filings.ts`; `filing_to_card` re-attaches IST. Postgres keeps it.

## Metrics to report in writeup (fill as measured)
| Metric | Value |
| --- | --- |
| Rule classifier coverage | 98.1% (262 real filings, 30 days) |
| Classifier accuracy (labelled) | see `pytest -s api/tests/test_classify.py` (58 labelled) |
| Event collapsing | 56 → 35 leads over 30 days |
| Anomalies (raw z → market-adjusted z) | 13 → 7 price moves; 19 → 5 unexplained (10 days) |
| ₹ per dossier (first run / cached) | — |
| Results cards with XBRL numbers | 18 of 20 primary results filings (30 days), 0 LLM calls, 0 gaps; 2 rejected by the 2-day guard |
| ₹ per day (push side) | ₹0 so far (no LLM calls yet) |
| Cache hit % | — |
| Claims dropped by verifier | — |

## NEXT SESSION STARTS HERE
- Sanity: `PYTHONUTF8=1 api/.venv/Scripts/python.exe -m pytest api/tests -q` → expect all green.
- Servers: `api/.venv/Scripts/python.exe -m uvicorn api.main:app --reload --port 8000`; `cd web && npm run dev`.
  Open http://localhost:3000 (fixture) and http://127.0.0.1:8000/brief?window=7d (real).
- If `.env` now has keys/DATABASE_URL: run migration, `make seed`, `make eod`, `make ingest` against Supabase
  (`make ingest` now also runs results enrichment; `make enrich FORCE=1` rebuilds all results cards).
- Then Next 3 tasks #1 (Brief UI on real data). Start in `web/components/cards/CardView.tsx` (Results renderer
  already exists) and `web/app/page.tsx` (fixture toggle). Real brief: `GET /brief?window=30d` → 35 lead · 35 line ·
  209 buried; 19 visible results cards carry XBRL payloads.
- No files mid-edit. No failing tests (25 passed).
