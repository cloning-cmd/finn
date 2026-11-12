# FINN — developer commands. Works from Git Bash / WSL / macOS. On Windows the venv python is api/.venv/Scripts/python.exe.
PY ?= $(shell if [ -x api/.venv/Scripts/python.exe ]; then echo api/.venv/Scripts/python.exe; else echo api/.venv/bin/python; fi)
T ?= INFY

.PHONY: dev api web ingest enrich eod research test seed vapid spikes deploy

dev: ## run API (8000) and web (3000) together
	@$(MAKE) -j2 api web

api:
	$(PY) -m uvicorn api.main:app --reload --port 8000

web:
	cd web && npm run dev

lan: ## serve API + web on the Wi-Fi address so a phone on the same network can open http://<pc-ip>:3000
	@$(MAKE) -j2 api-lan web-lan

api-lan:
	$(PY) -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

web-lan:
	cd web && npm run dev:lan

ingest: ## pull filings for the portfolio (30-day backfill on first run) + classify + score
	$(PY) -m jobs.run_filings

enrich: ## attach XBRL numbers to results cards (re-run with FORCE=1 to rebuild)
	$(PY) -c "from api.pipeline.enrich_results import enrich_results; print(enrich_results(force=bool('$(FORCE)')))"

eod: ## load EOD prices, compute anomalies, explain moves
	$(PY) -m jobs.run_eod

research: ## build a dossier: make research T=INFY
	$(PY) -m jobs.run_research $(T)

test:
	$(PY) -m pytest api/tests -q

seed: ## load supabase/seed/portfolio.csv into companies
	$(PY) -m jobs.seed

vapid: ## print a fresh VAPID key pair for .env
	$(PY) -c "from py_vapid import Vapid; v=Vapid(); v.generate_keys(); import base64; print('VAPID_PUBLIC_KEY='+base64.urlsafe_b64encode(v.public_key.public_bytes(encoding=__import__('cryptography.hazmat.primitives.serialization',fromlist=['Encoding']).Encoding.X962, format=__import__('cryptography.hazmat.primitives.serialization',fromlist=['PublicFormat']).PublicFormat.UncompressedPoint)).decode().rstrip('=')); print('VAPID_PRIVATE_KEY='+base64.urlsafe_b64encode(v.private_key.private_numbers().private_value.to_bytes(32,'big')).decode().rstrip('='))"

spikes:
	$(PY) spikes/s1_yfinance.py

deploy: ## create GitHub repo + push, set Actions secrets, deploy Render API + Vercel web (tokens from .env). Subset: make deploy S="render vercel"
	$(PY) -m jobs.deploy $(S)

people: ## bios from management-change filings (re-run with FORCE=1 to rebuild)
	$(PY) -c "from api.pipeline.enrich_people import enrich_people; print(enrich_people(force=bool('$(FORCE)')))"
