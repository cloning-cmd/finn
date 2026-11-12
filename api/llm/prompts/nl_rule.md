# nl_rule v1

Turn one sentence of plain English into a FINN alert rule. Output only the JSON object.

Schema:
{"name": "<= 40 chars, factual", "scope": {"type": "portfolio" | "ticker", "value": "<NSE symbol when type=ticker>"},
 "condition": one of
   {"kind": "category", "categories": [<from the list below>], "min_priority": <0-100 or null>}
   {"kind": "price_move", "pct": <percent or null>, "z": <sigma or null>, "direction": "up" | "down" | "both"}
   {"kind": "volume", "multiple": <number>, "lookback_days": 20}
   {"kind": "guidance_gap", "min_gap_pct": <number>},
 "channels": ["push", "inbox"]}

Categories: results, ma, fund_raise, management_change, litigation, insider_trading, earnings_call, investor_meetings,
credit_rating, dividend, bonus_split, capex, press_release, postal_ballot, agm_egm, pledging.

Rules:
- Pick exactly one condition kind. "falls/drops/down" → direction down; "rises/jumps/up" → up; otherwise both.
- "5%" style thresholds go to pct; "sigma"/"standard deviations"/"unusual" go to z (default 2.5 when unusual is said
  without a number). Volume phrases ("2x volume", "double the volume") → kind volume with that multiple.
- Mentions of a company → scope ticker with its NSE symbol if it is written as a symbol; if only a name is given,
  copy the name into value as written (the server resolves it). No company → portfolio.
- "Misses guidance" / "below what they promised" → guidance_gap with min_gap_pct 0 unless a number is given.
- Never invent thresholds that were not stated except the z default above. Use null for absent numbers.

Sentence:
{{text}}
