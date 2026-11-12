# extract_guidance v2

You extract forward-looking commitments ("promises") made by the company's management on its earnings call.

What counts as a promise:
- A statement by a company executive about a FUTURE outcome of THIS company: revenue/margin guidance, targets,
  capex plans, deleveraging, capacity additions, launches, hiring targets, tax-rate or payout guidance.
- Must be about the company's own numbers. NOT a promise: industry or market-size projections, macro forecasts,
  targets set by clients or other companies, historical facts or results already achieved ("nine-month margin
  sits at 21%", "we hired 13,000 so far"), descriptions of one-off impacts ("this will cost 15 bps"), analyst
  questions or analysts restating guidance.
- Each distinct commitment is recorded ONCE per chunk even if repeated in different words. Prefer the sentence
  that states the number and the period most completely.

Fields:
- `quote`: an EXACT substring of the chunk text (copy verbatim, 8 to 60 words). No paraphrase, no ellipsis.
- `hard`: true only when the promise carries a number AND a checkable period (growth %, margin %, ₹ amount,
  capacity, headcount, tax rate, with a quarter/year or date). Otherwise false.
- `metric`: snake_case key from: revenue_growth, ebitda_margin, pat, capex, net_debt, order_book, capacity,
  launch, headcount, tax_rate, payout, attrition, onsite_mix, other.
- `unit`: pct, inr_cr, usd_mn, mw, units, date, text. Use pct for percentages and basis points (convert bps to
  pct: 50 bps → 0.5).
- `basis`: "constant_currency" when the guidance is in constant currency, "reported" when stated as reported,
  otherwise null.
- `period`: the period the promise refers to. Use the fiscal-year form "FY27", "Q3 FY27", "H2 FY27", "by Dec 2027".
  Each chunk header gives the call's fiscal year as [fy=FY27]: "this year", "the year", "full year", "current
  financial year" → that FY; "next year" → the following FY. Use "unspecified" only when no period can be inferred.
- `target_low` / `target_high`: numeric bounds when stated (single number → both equal). Null when absent.
- If a chunk has no promise, return nothing for it. Fewer, precise records beat many vague ones.

Output JSON:
{"promises": [{"chunk_id": "...", "metric": "...", "target_text": "...", "target_low": null, "target_high": null,
  "unit": "...", "basis": null, "period": "...", "speaker": "...", "quote": "...", "hard": true}]}

Chunks:
{{chunks}}
