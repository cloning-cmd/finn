# FINN — agent memory (read first, every session)

FINN = mobile-first financial investment agent (PWA) for the ENAM AI Engineer Build Challenge.
Deadline: **Sun 15 Nov 2026**, email to assessment@enam.com, subject `IIT Delhi – AI Engineer - 2027`.
Full spec: `FINN_MASTER_PROMPT.md` (repo root). Progress: `docs/STATE.md`. Decisions: `docs/DECISIONS.md`.

## Session start (always)
1. Read this file, `docs/STATE.md`, last 15 entries of `docs/DECISIONS.md`, `git log --oneline -15`.
2. Say in 3 lines: where we are · what's next · blockers. Then continue from "NEXT SESSION STARTS HERE".

## Non-negotiables
- Keep `main` deployable. Thin-but-working beats broad-but-broken.
- Numbers come from code; words come from models. LLMs never do arithmetic or recall company facts.
- Routing: rules → parsers (XBRL, tables) → cheap LLM → strong LLM (once per ticker per quarter). Cache every call.
- Pull side uses ONLY annual reports + concall transcripts (+ screener tables). No news/broker notes/model memory.
- Every claim has a source; `verify.py` drops unverified quotes/numbers.
- Research must work for ANY NSE ticker; degrade gracefully with `gaps[]`.
- Contracts in `docs/CONTRACTS.md` are frozen; change only with a DECISIONS entry.
- No AI slop in UI copy: facts, numbers, ≤ 70-char headlines, no emojis/exclamations.

## Stack (as built — see DECISIONS for deltas from the master prompt)
Next.js 15 PWA (web/) on Vercel · FastAPI (api/, Python 3.12, venv at api/.venv) · SQLAlchemy 2 with
`DATABASE_URL` (SQLite locally, Supabase Postgres in prod) · chunk retrieval via hashed TF-IDF in numpy (`EMBED_BACKEND=hash`, default; `fastembed` bge-small opt-in) with
cosine search in numpy · GitHub Actions cron (jobs/) · LiteLLM router with SQL cache · PyMuPDF/pdfplumber ·
yfinance · NSE API (BSE fallback) · screener.in.

## Environment quirks (Windows dev box)
- Use `py -3.12` / `api/.venv/Scripts/python.exe`. Shell is Git Bash or PowerShell 5.1 (no `&&` in PS).
- Long multi-heredoc bash scripts fail to parse here; write files with the editor tool, keep bash commands short.
- `gh` CLI not installed as of 2026-11-11 evening; local commits only until it is.

## Signature features
Finite Brief (ends; buried count; minutes saved) · Promise Ledger (kept/on track/missed/revised/quietly dropped) ·
Explain the Move (unexplained moves flagged) · volatility-aware thresholds · bio from filing · cost receipt ·
citation verifier · replay a day.

## After every task
Commit (`feat|fix|chore(scope): …`) → update `docs/STATE.md` (Last completed, Next 3 tasks).

## Context limit protocol
Every ~45 min, before big refactors, or when context is long: write full handoff under
"NEXT SESSION STARTS HERE" in `docs/STATE.md` (next command, files mid-edit, failing tests, open questions),
commit `chore(state): handoff`. If nearly full: stop, save handoff, tell the user to start a new session with
`RESUME_PROMPT.md`. Never keep important facts only in chat.

## End of day
Export session to `docs/build-history/<date>-<topic>.md` (`/export`), push.

## Commands
`make dev` · `make ingest` · `make eod` · `make research T=INFY` · `make test` · `make seed` (see Makefile)
