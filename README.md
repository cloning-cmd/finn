# FINN — a finite brief for Indian equity investors

Mobile-first PWA + API that turns NSE/BSE filings, EOD prices, annual reports and concall transcripts into a ranked
brief that *ends*, alerts you can configure in plain English, and research grounded only in primary sources.

**Thesis:** attention is the budget. FINN's success metric is how little the investor has to read.

Built for the ENAM "AI Engineer Build Challenge" (Nov 2026). Status: Phase 0 (scaffold + de-risk) — see
`docs/STATE.md`.

## Signature features
- **Finite Brief** — ranked card stack with an end state: "3 matter · 38 buried · ~19 min saved".
- **Promise Ledger** — every quantitative guidance statement from the last 4–6 concalls, scored against actuals.
- **Explain the Move** — EOD anomalies linked to filings in ±48h; otherwise flagged *Unexplained*.
- Volatility-aware thresholds (z-score vs the stock's own 60-day volatility), bios extracted from the filing itself,
  a cost receipt on every dossier, a citation verifier, and "replay a day" for demos.

## Layout
```
api/        FastAPI (Python 3.12) — routers, ingest, pipeline, research, llm
web/        Next.js 15 PWA (App Router, Tailwind 4, framer-motion)
jobs/       cron entry points (GitHub Actions + `make ingest` / `make eod`)
supabase/   migrations + portfolio seed
docs/       STATE.md (progress), DECISIONS.md (ADRs + spike findings), CONTRACTS.md (frozen schemas)
spikes/     throwaway API probes that informed the decisions
```

## Local setup
```bash
# API
py -3.12 -m venv api/.venv && api/.venv/Scripts/pip install -r api/requirements.txt   # or python3.12 -m venv
cp .env.example .env            # fill keys; DATABASE_URL defaults to SQLite
api/.venv/Scripts/python.exe -m uvicorn api.main:app --reload --port 8000
# Web
cd web && npm install && echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local && npm run dev
```
Open http://localhost:3000/?fixture=1 for the fixture brief. Tests: `make test`.

## Architecture, model routing, costs, known limits
Filled in during Phase 4 (see `docs/WRITEUP.md`). Decisions and spike findings so far: `docs/DECISIONS.md`.
