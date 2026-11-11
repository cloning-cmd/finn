# FINN — STATE (living handoff)

> Update after every task. The section "NEXT SESSION STARTS HERE" must always be accurate.
> Last updated: 2026-11-11 20:25 IST

## Current phase
Phase 0 — De-risk + scaffold. Local acceptance met (fixtures served from `/brief?fixture=1`, web shell renders them,
tests green). **Deploys pending user actions** (see Blockers). Build started 19:28 IST, so ~half a day behind the
master-prompt schedule; recover by starting Phase 1 ingestion tonight/first thing Thu.

## Deadline tracker
| Phase | Target | Status |
| --- | --- | --- |
| 0 De-risk + scaffold | Wed 11 Nov | local done 20:25; deploys pending accounts |
| 1 Push backend + app shell | Thu 12 Nov | not started |
| 2 Pull engine + people + push delivery (tag v0.9) | Fri 13 Nov | not started |
| 3 Product polish, freeze 20:00 IST | Sat 14 Nov | not started |
| 4 Harden + submit | Sun 15 Nov | not started |

## Last completed
- Repo + layout, memory files, master prompt copied, `.gitattributes` (LF), git identity set.
- Six spikes run; findings in DECISIONS (NSE all-equities call, XBRL tags, screener sections, transcript format).
- Contracts frozen: `docs/CONTRACTS.md`, `web/lib/types.ts`, `api/models.py` (+ deltas recorded).
- API: `api/main.py`, `api/db.py` (SQLAlchemy, SQLite default), `supabase/migrations/001_init.sql`,
  `GET /brief` (fixture + real path), `POST /feedback`, `/health`. 15 fixture cards. `pytest` 3 green.
- Web: Next 15.5 + Tailwind 4 + framer-motion; tokens (dark default), BottomNav, BriefScreen (window chips, header
  counts, card stack by type, "You're caught up", buried drawer), manifest + SW + icons. `npm run build` clean.
- `render.yaml`, `api/requirements.txt` (pinned), `.env.example`, `Makefile`.

## In progress
- (none — waiting on accounts for deploys)

## Next 3 tasks
1. **Deploys** (needs user): `gh auth login` → `gh repo create` + push; Vercel import (root `web`, env
   `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_FIXTURE=1` until Phase 1 data exists); Render Blueprint from `render.yaml`
   with `DATABASE_URL` = Supabase pooled URL; run `supabase/migrations/001_init.sql` in Supabase SQL editor.
2. **Phase 1 ingestion**: `api/ingest/nse.py` (all-equities call, filter portfolio, 30-day backfill, PDF first 3
   pages → `body_text`), `api/ingest/prices.py` (yfinance 400d, ret/vol60/vol_avg20/z), `jobs/seed.py`,
   `jobs/run_filings.py`, `jobs/run_eod.py`.
3. **Phase 1 pipeline**: `classify.py` (rules, coverage log) + `scoring.yaml` + `score.py` → tiers; `anomalies.py`
   + `explain_move.py`; `enrich_results.py` (XBRL first). Then Brief swipe (framer-motion) on real data.

## Blockers
- `gh` CLI not installed → no remote yet (user will install + `gh auth login`).
- `.env` not yet created: Supabase `DATABASE_URL`, `GEMINI_API_KEY`/`GROQ_API_KEY`, `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`.
  Copy `.env.example` → `.env` and fill; the agent reads it via `api/config.py`, never from chat.
- Tavily key not yet → bio enrichment stays filing-only until present.
- BSE JSON API blocked (403) → not used; NSE from residential IP + snapshot mode is the resilience story.

## Live URLs & env status
| Item | Value / status |
| --- | --- |
| GitHub repo | not created (gh pending) |
| Web (Vercel) | not deployed |
| API host (Render) | not deployed; `render.yaml` ready |
| Supabase project | exists; migration not yet run; URL not in .env |
| Cheap LLM key | not in .env |
| Strong LLM key | not in .env |
| Web search API key | none |
| VAPID keys | not generated (`make vapid`) |
| Local | API `http://127.0.0.1:8000` · web `http://localhost:3000` (`web/.env.local` has FIXTURE=1) |

## Known issues
- Windows console needs `PYTHONUTF8=1` for ₹ output (set in Makefile targets? not yet — add).
- `fitz` import warns to use `import pymupdf`; switch in `documents.py`.
- Playwright smoke tests not set up yet (Phase 3).

## Metrics to report in writeup (fill as measured)
| Metric | Value |
| --- | --- |
| Rule classifier coverage | — |
| Classifier accuracy (50 labelled) | — |
| ₹ per dossier (first run / cached) | — |
| ₹ per day (push side) | — |
| Cache hit % | — |
| Claims dropped by verifier | — |

## NEXT SESSION STARTS HERE
- Run: `PYTHONUTF8=1 api/.venv/Scripts/python.exe -m pytest api/tests -q` (expect 3 passed), then
  `api/.venv/Scripts/python.exe -m uvicorn api.main:app --reload --port 8000` and `cd web && npm run dev`.
- If `.env` now exists with `DATABASE_URL`, run the migration (`supabase/migrations/001_init.sql`) via Supabase SQL
  editor or `psql`, then `make seed` (jobs/seed.py — not written yet; write it first: read
  `supabase/seed/portfolio.csv` → upsert `companies`).
- Then start Next 3 tasks #2 (ingestion). Spike facts to reuse: DECISIONS "Spike findings (Phase 0)".
- No files mid-edit. No failing tests.
