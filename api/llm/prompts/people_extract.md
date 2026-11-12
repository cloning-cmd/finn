# people_extract v1

Read one stock-exchange filing about a change in a company's management or board. Output only the JSON object.

Schema:
{"changes": [
  {"name": "<person's name as written, without Mr./Ms./Shri/Dr.>",
   "role": "<position concerned, as written, e.g. Managing Director and CEO, Chief Financial Officer, Independent Director>",
   "change": "appointment" | "resignation" | "retirement" | "cessation",
   "effective_date": "<date as written in the filing, or null>",
   "profile_lines": ["<up to 3 sentences copied verbatim from the filing that describe this person's background>"],
   "prior_roles": ["<earlier positions or employers named in the filing, each as a short phrase copied from it>"],
   "replaces": "<name of the person being replaced, if the filing says so, else null>"}
]}

Rules:
- One entry per person whose position changes. A filing can contain several (an appointment that follows a retirement).
- "change" is about this person: the one joining is an appointment; the one leaving is a resignation, retirement or
  cessation (end of term, removal, death).
- Copy, never paraphrase: profile_lines and prior_roles must be text that appears in the filing. If the filing has
  no profile, use an empty list. Never add facts from memory.
- Dates: copy the wording used in the filing. Use null when no date is given.
- Ignore the sender address block, the regulation citations and the signature.

Filing text:
{{text}}
