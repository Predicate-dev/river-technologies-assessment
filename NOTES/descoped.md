# Deliberately descoped

- **LLM extraction path — cut entirely (Lara, Window 1).** Compliance review is
  required before building against any third-party model and will take days; she
  explicitly refused to set a provisional default. Prototype is
  deterministic-only. The integration point is built and specified in the
  technical doc so it can be switched on after compliance rules, but nothing
  depends on it and no API key is required to run. In the event the
  deterministic tiers reached every fee in the peer set, so the compliance answer
  costs no coverage.
- **A plug-in framework for new fund types.** Flex was signalled on funds and
  metrics, unofficially. The config-driven registry already makes an added fund
  cheap *within a filer type already handled*; a general framework for funds
  nobody has named would have consumed the time that went into the confidence
  model. Two genuine cliffs named for the client instead: a new entity type has
  no source adapter, and any metric living in prose is gated behind the same
  compliance answer as the LLM path.
- **A review UI.** Scoped as option C in the original three-way and cut: it would
  have eaten the document budget. The audit trail CSV carries everything a
  reviewer needs — every candidate, winners and rejects, with provenance and
  score inputs — and is the input a UI would render.
- **Quarterly scheduling** (the cron half). The *detection* half was built --
  `--compare-to` diffs a run against a previous quarter's coverage and exits
  non-zero on lost coverage, so whatever scheduler the client already runs can
  gate on it. Choosing and operating that scheduler is their infrastructure
  decision, not an evidence problem.
- **Interpolating the NAV trend onto a shared calendar grid.** Would have made a
  cleaner chart. Rejected because no calendar date exists on which all four
  filers report, so every interpolated point would be an observation no filer
  published.
- **Market-price total return as a substitute for KREF's net return.** Would have
  filled three blank cells and made the table look complete. Rejected on Lara's
  ruling and on the merits: it is a different measure, not the same one under
  another name.
- **Raising the N-PORT download cap to reach deeper history.** 8MB per filing;
  the trailing windows it would extend are now sourced from the financial
  highlights instead, which is both cheaper and class-level.

- **Weighted average spread extraction.** Explicitly not authorised (Lara,
  Window 3): "I am not authorizing extraction work on a metric nobody has
  defined yet." The definition question -- spread over benchmark vs all-in yield
  -- goes to the PMs first. Worth noting the metric is also not a config entry:
  GBDC's 10-K states the phrase once and the figures live in per-filer tables,
  so it is real extraction work whenever it is authorised.
- **Word document styling.** Deliberately left generic pending their house
  template, fonts and logo. Guessing was ruled out: "the IC committee will
  notice immediately."
