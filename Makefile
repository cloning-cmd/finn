# FINN — developer commands. Works from Git Bash / WSL / macOS. On Windows the venv python is api/.venv/Scripts/python.exe.
PY ?= $(shell if [ -x api/.venv/Scripts/python.exe ]; then echo api/.venv/Scripts/python.exe; else echo api/.venv/bin/python; fi)
T ?= INFY

.PHONY: dev api web ingest eod research test seed vapid spikes

dev: ## run API (8000) and web (3000) together
	@$(MAKE) -j2 api web

api:
	$(PY) -m uvicorn api.main:app --reload --port 8000

web:
	cd web && npm run dev

ingest: ## pull filings for the portfolio (30-day backfill on first run) + classify + score
	$(PY) -m jobs.run_filings

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
