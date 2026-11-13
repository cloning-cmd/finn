# FINN — STATE (living handoff)

> Update after every task. The section "NEXT SESSION STARTS HERE" must always be accurate.
> Last updated: 2026-11-13 04:40 IST

## Current phase
Phase 2 — Pull engine + people + push delivery. Deployed: web on Vercel, API on Render (free, 512 MiB), DB on
Supabase. Research builds with Gemini 3.x end to end (INFY, PIDILITIND). Rules, alerts inbox, Web Push and replay
are built and committed. Left in Phase 2: people enrichment (bio from filing), cheap-LLM one-liners.

## Deadline tracker
| Phase | Target | Status |
| --- | --- | --- |
| 0 De-risk + scaffold | Wed 11 Nov | local done; deploys pending accounts |
| 1 Push backend + app shell | Thu 12 Nov | local done; deploys pending keys |
| 2 Pull engine + people + push delivery (tag v0.9) | Fri 13 Nov | ~85% (research + LLM sections, rules, alerts, push, replay done; people left) |
| 3 Product polish, freeze 20:00 IST | Sat 14 Nov | not started |
| 4 Harden + submit | Sun 15 Nov | not started |

## Last completed
- **UI redesign** (2026-11-13, commit bead29c): design tokens + `web/components/ui.tsx`; Brief stats + metric
  tiles, Research build stepper + tabbed dossier + collapsible ledger, Alerts notification centre, settings-style
  Rules; light/dark, desktop width. See DECISIONS 2026-11-13 UI redesign. Screenshot loop for review: a dev server
  on 3100 with `NEXT_DIST_DIR=.next-preview NEXT_PUBLIC_API_URL=http://localhost:8000` (the user's own dev server
  on 3000 uses `.next` and the LAN API address in `web/.env.local`).
- **.zip attachments** (2026-11-13): `fetch_pdf` takes the largest PDF inside a zip (read in memory, 60 MB cap,
  `%PDF-` check); ingest now fetches `.zip` bodies; `enrich_people` backfills `body_text` for filings ingested
  before this. TRENT 19 Oct KMP filing → "Harish Bhat resigns as Non-Executive Non-Independent Director"; local
  people coverage 16/16. 48 tests. Note: the same resignation also arrived as an 18 Oct filing; both show.
- **Brief 30-day crash fixed** (2026-11-13, commit 3fda0da): `CardView` picked the renderer by card type, so a
  management change with the generic payload (TRENT .zip) and a guard-rejected "results" filing (RELIANCE) threw
  on missing arrays and blanked the page. Now chosen by payload shape, arrays guarded, per-card error boundary.
  `web/scripts/render-check.tsx` server-renders a saved Brief JSON (`npx tsx --tsconfig
  scripts/tsconfig.check.json scripts/render-check.tsx brief.json`): production 30d → old 2/68 failed, new 0.
- **Specific headlines for generic filings** (2026-11-13): `api/pipeline/enrich_oneliner.py` + prompt
  `one_liner.md` v1. Lead/line cards whose headline is "Disclosure under Regulation 30…", "Credit Rating",
  "Rumour Verification…" etc. get a model-written headline + one-liner + one verbatim supporting sentence; code
  rejects the output unless the sentence is in the filing (rapidfuzz ≥ 85) and every number in headline/one-liner
  is in the filing text. The sentence becomes the filing source's `quote` (shown in the source sheet). Runs at the
  end of `run_filings`; `make headlines`. Local: 9 of 9 generic cards rewritten and verified, ₹0.48 total.
  Verifier fix: `numbers_in` now reads "Rs.2635" / "INR.500" (the currency period hid the number). 45 tests.
- **Research SSE client fix** (commit 4e29e29): sse-starlette ends lines with `\r\n`; the web client split on
  `\n\n`, so every fresh build from the browser failed with a JSON parse error. Deployed and confirmed by the user.
- **People enrichment** (2026-11-13 05:10): `api/pipeline/enrich_people.py` + prompt `people_extract.md` v1. Cheap
  model locates name / role / change / verbatim profile lines / prior roles / replaced person; code verifies every
  line against the filing text (rapidfuzz ≥ 85, numbers must match), parses the effective date, picks the most
  senior change (a courtesy "Emeritus" title never wins over the departure), pairs incoming/outgoing, writes the
  ≤ 70-char headline (senior clause, then CEO/CFO/MD/CISO abbreviations) and one-liner, flags `top role` /
  `immediate effect` / `no successor named` / `no profile in filing` / `interim`, bumps top-role changes to
  priority ≥ 57 idempotently (`people.base_priority`). Optional Tavily snippet (one line, domain-labelled, never
  LinkedIn). Runs at the end of `run_filings`; `make people`. 15 of 16 local filings enriched for ₹0.89 (one .zip
  attachment skipped); 3 cards carry 3 verified bio lines each. 41 tests pass.
- **Research on Render fixed** (2026-11-13 04:40): the deployed API was OOM-killed (512 MiB) on every fresh
  research build while loading the fastembed model (measured 684 MB peak locally). New `api/research/embed.py`:
  `EMBED_BACKEND=hash` (default) = hashed TF-IDF in numpy, no model; `fastembed` opt-in. Stale vectors re-embed
  lazily on first search; per-ticker chunk cache; keyword synthesis queries; short-chunk damping. The web client now
  says "build stopped before it finished… retry" when a stream ends without a dossier. 37 tests pass.
  Also killed the stale 11 Nov uvicorn (PID 28484) that returned 404 for `/research` locally.
- **Rules + alerts + push + replay** (2026-11-13 04:00, commit be655be): `/rules` CRUD, `/rules/parse` (regex →
  cheap LLM, ₹0.03), `/alerts`, `/alerts/evaluate` (also run at the end of `run_filings`/`run_eod`), `/push/*`
  (VAPID via pywebpush, `sw.js` shows notifications), `/admin/replay?date=` fires a past day's alerts with spacing.
  Rules screen (sliders, category chips, plain-English box, notifications toggle) and Alerts screen (by day, Demo
  replay). Verified locally: parse both paths, evaluate over 283 cards, 3 default rules seeded, push key served.
- **Deploy tooling** (2026-11-12 11:40, commit 6512099): `jobs/deploy.py` (`make deploy`) does repo create + push,
  Actions secrets/variables, Render service `finn-api`, Vercel link + env + prod deploy from the tokens in `.env`.
  The agent's sandbox is not allowed to create repos / upload, so **the user runs it**. Workflows
  `.github/workflows/filings.yml` (every 30 min 08:30–20:00 IST Mon–Fri) and `eod.yml` (18:15 IST) written.
- **Gemini model switch** (2026-11-12 11:15): 2.5 family is 404 for new keys, pro tier 429 on the free tier →
  cheap `gemini-3.5-flash-lite` (fb `3.1-flash-lite`), strong `gemini-3.5-flash` (fb `3-flash-preview`). First
  real INFY run with 2.5 ids failed cleanly into `gaps[]` (0 calls billed); rerun with 3.x ids: see Metrics.
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
1. **Dossier review on production** (Render fix confirmed 13 Nov 04:50: POLYCAB built live, no `oomKilled`):
   build BAJFINANCE, TATAPOWER + 1 unseen ticker from the Vercel app; review ledgers/verdicts; record ₹ per
   dossier. Run `make people` and `make enrich` once against Supabase (or dispatch the filings workflow) so the
   production Brief carries people and results payloads.
2. **Phase 3 polish**: Brief loading state for the Render cold start (~50 s), card copy pass, collapse the same
   people event filed on consecutive days (TRENT Harish Bhat 18 + 19 Oct) by person name, reclassify the RELIANCE
   Jio notice that sits in `results`.
3. **Push delivery check on the phone**: Vercel app → Rules → Enable (iOS needs Add to Home Screen first); fire
   `/admin/replay` for 12 Nov from the Alerts Demo control and confirm notifications arrive; trigger both Actions
   workflows once via workflow_dispatch and confirm NSE is reachable from the runners (BSE fallback otherwise).

## Blockers (user actions)
- `.env`: Gemini key + GitHub/Vercel/Render tokens are in (verified 12 Nov). **`DATABASE_URL` is still SQLite** →
  paste the Supabase transaction-pooler URI (`postgresql+psycopg://…:6543/postgres?sslmode=require`). Tables are
  created by the API on startup (`init_db`), so the SQL migration is optional.
- Run `make deploy` (the sandbox is blocked from creating repos / uploading). If Render says the repo is not
  accessible, install the Render GitHub app on the repo and re-run `make deploy S="render vercel"`.
- Vercel needs `NEXT_PUBLIC_ADMIN_TOKEN` (= the API's `ADMIN_TOKEN`) for the Alerts "Demo → Replay a day" control;
  without it the replay call uses the dev default and Render returns 401.
- Tavily key (optional) for bios.

## Live URLs & env status
| Item | Value / status |
| --- | --- |
| GitHub repo | https://github.com/cloning-cmd/finn (private; Actions secrets + variables set 12 Nov) |
| Web (Vercel) | https://finn-six-bay.vercel.app (project `finn`, prod alias, public; deployed 12 Nov via `jobs/deploy.py vercel`). Per-deployment `finn-xxxx-….vercel.app` URLs sit behind Vercel login; always share the alias |
| API host (Render) | https://finn-api-3bj2.onrender.com (service `finn-api`, Singapore, free plan; created 12 Nov) |
| Supabase project | exists; migration not run; URL not in .env |
| Cheap / strong LLM keys | Gemini key in `.env`; models `gemini-3.5-flash-lite` / `gemini-3.5-flash` |
| Web search API key | none |
| VAPID keys | generated, in `.env` |
| Local | API `http://127.0.0.1:8000` · web `http://localhost:3000` · DB `data/finn.db` |

## Known issues
- Retrieval is lexical by default (`EMBED_BACKEND=hash`); Q&A phrased without the document's words can miss. Set
  `EMBED_BACKEND=fastembed` on a host with ≥ 1 GB for semantic recall (chunks re-embed lazily).
- Render free instance sleeps after 15 min idle; the first request takes ~50 s. The research screen shows the
  progress log meanwhile, but the Brief's first load is a blank skeleton for that long.
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
| ₹ per dossier (first run / cached) | INFY: ₹5.31 first run (122k tokens in, 37 extraction calls) / ₹0.60 rerun with 49% cache hits / ₹0 cached open. PIDILITIND: ₹2.03 first run (34k in, 9 promises from 48 mgmt chunks, 2 claims dropped). POLYCAB on Render: ₹2.93 (20 promises from 68 mgmt chunks, 2 dropped) |
| Results cards with XBRL numbers | 18 of 20 primary results filings (30 days), 0 LLM calls, 0 gaps; 2 rejected by the 2-day guard |
| ₹ per day (push side) | ₹0 so far (no LLM calls yet) |
| Cache hit % | — |
| Claims dropped by verifier | INFY synthesis: 2 of ~12 claims dropped (unverified number/quote) |

## NEXT SESSION STARTS HERE
- **Deploys are user-run** (sandbox blocks push and production deploys): `api\.venv\Scripts\python.exe -m jobs.deploy repo`
  pushes with the token (`make` is not installed in PowerShell); `… -m jobs.deploy render vercel` redeploys both.
  Render auto-deploy does not fire on push (GitHub app not installed on the repo), so the render step is needed
  after every push. Deployed as of 13 Nov 04:50: a45579f on both hosts.
- Still to set on Vercel: `NEXT_PUBLIC_ADMIN_TOKEN` (= `ADMIN_TOKEN`), then redeploy, for the Alerts replay control.
- Sanity: `PYTHONUTF8=1 api/.venv/Scripts/python.exe -m pytest api/tests -q` → expect 41 passed.
- Servers: `api/.venv/Scripts/python.exe -m uvicorn api.main:app --reload --port 8000`; `cd web && npm run dev`.
  Open http://localhost:3000/research?t=PIDILITIND (cached), /rules, /alerts.
- Deployed check (Next task 1): `curl -N -X POST https://finn-api-3bj2.onrender.com/research/POLYCAB` must end
  with an `event: dossier`, not a silent close. Render events: scratch script pattern in this session was
  `GET /v1/services?name=finn-api` → `/services/{id}/events`; `oomKilled` means the hash backend is not active
  (check `EMBED_BACKEND` is unset or `hash` on Render).
- Then Next task 2 (people enrichment). No files mid-edit. No failing tests.
