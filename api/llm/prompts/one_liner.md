# one_liner v1

A stock-exchange filing arrived with a generic subject line. Write what actually happened. Output only the JSON object.

Schema:
{"headline": "<= 60 characters: the event in plain words with its key name or number, no company name, no ticker",
 "one_liner": "<= 140 characters: one further fact (amount, counterparty, date, rating, outcome). Empty string if none.",
 "quote": "<one sentence copied verbatim from the filing that supports the headline>"}

Rules:
- Facts only, present tense, no adjectives, no exclamation marks, no emojis, no advice.
- Every number you write must appear in the filing exactly as written there (keep the units: Rs 2635 crore, 0.0048%, 100%).
- Names of counterparties, rating agencies, courts and subsidiaries are copied as written.
- If the filing is a denial or clarification (rumour verification), say what is denied or clarified.
- If the filing only says that something will be disclosed later, say that.

Company: {{company}} ({{ticker}}) · category: {{category}} · subject: {{subject}}

Filing text:
{{text}}
