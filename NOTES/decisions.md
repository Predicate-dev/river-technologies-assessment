# Decisions & tradeoffs

- **Scope B of three proposed.** A (structured-only) has no evidence to build a
  confidence model on; C (full 8q series + UI) eats the document budget.
  B = structured-first + multi-source reconciliation, which *is* the confidence
  model.
- **Structured-first source hierarchy.** XBRL companyfacts (GBDC/KREF: 189/283
  us-gaap tags) and N-PORT XML (CCLFX/TAKIX: netAssets, borrowings, monthly
  returns) before any LLM. Rejected LLM-first: unverifiable, and the two
  structured sources are free and exact.
- **No new dependencies.** requests/pandas/bs4/pydantic/anthropic/dotenv already
  present in the target env. Rejected lxml (bs4 covers the HTML tables),
  tabulate (pandas.to_markdown suffices).
- **LLM path is optional, not required.** Deterministic table-parser fallback so
  `git clone && run` works with no API key. Graders must be able to run it.
- **Disk-cached EDGAR client.** Re-runs are offline; a live demo cannot be
  broken by a network hiccup or SEC rate limiting.
- **Candidate/resolution split in the data model.** Every extracted value is a
  Candidate with provenance; resolution to a single reported value is a separate,
  logged step. Rejected single-value-per-metric: destroys the disagreement
  evidence the client said they would press on.
