# qa v1

Answer a question about {{ticker}} using ONLY the material below.

Rules:
- Each answer is 1 to 4 claims. Each claim is one sentence (max 30 words) with `source_ids` from the material
  (chunk ids like "d_...", or "s_screener" for the tables). A claim without a source is deleted.
- Numbers must appear verbatim in the cited chunk or the tables. Do not compute or convert numbers.
- If the material does not answer the question, return one claim: "Not disclosed in the available filings and
  calls." with source_ids [] — it will be shown as a gap. Never use outside knowledge.
- No adjectives without numbers, no exclamation marks, no filler.

Question: {{question}}

Output JSON: {"claims": [{"text": "...", "source_ids": ["..."]}]}

## Tables (source id: s_screener)
{{tables}}

## Chunks
{{chunks}}
