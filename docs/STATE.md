# FINN — STATE (living handoff)

> Update after every task. The section "NEXT SESSION STARTS HERE" must always be accurate.
> Last updated: 2026-11-11 19:40 IST

## Current phase
Phase 0 — De-risk + scaffold (target: end of Wed 11 Nov; build started 19:28 IST, so running ~half a day late)

## Deadline tracker
| Phase | Target | Status |
| --- | --- | --- |
| 0 De-risk + scaffold | Wed 11 Nov | in progress |
| 1 Push backend + app shell | Thu 12 Nov | not started |
| 2 Pull engine + people + push delivery (tag v0.9) | Fri 13 Nov | not started |
| 3 Product polish, freeze 20:00 IST | Sat 14 Nov | not started |
| 4 Harden + submit | Sun 15 Nov | not started |

## Last completed
- Repo initialised at `ENAM assignment/` (git, layout §4, memory files, .gitignore).

## In progress
- Python venv + deps install (background); Next.js scaffold in `web/` (background); spikes.

## Next 3 tasks
1. Spikes: yfinance 18 tickers, NSE announcements, BSE fallback, screener INFY, one concall PDF, one XBRL → DECISIONS.
2. CONTRACTS.md + `web/lib/types.ts` + pydantic models + 10 fixture cards; `GET /brief?fixture=1`.
3. Supabase migration 001; hello-world deploys (Vercel + Render); `.env.example`.

## Blockers
- `gh` CLI not installed on the dev box → local commits only until user runs `gh auth login`.
- Web-search key (Tavily) not yet available → bio enrichment behind `TAVILY_API_KEY` flag.

## Live URLs & env status
| Item | Value / status |
| --- | --- |
| GitHub repo | TBD (user will install + auth gh) |
| Web (Vercel) | TBD (account exists) |
| API host | TBD (Render account exists) |
| Supabase project | exists; URL/keys not yet in .env |
| Cheap LLM key | user has Gemini/Groq; not yet in .env |
| Strong LLM key | user has Anthropic/OpenAI; not yet in .env |
| Web search API key | not yet |
| VAPID keys | TBD (generate with `make vapid`) |

## Known issues
- (none yet)

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
- Phase 0 in progress. Run spikes in `spikes/` (see Next 3 tasks #1). venv: `api/.venv/Scripts/python.exe`.
