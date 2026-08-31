# Open questions for the client

## Window 1 (asked before schema lock)

1. **KREF classification.** Brief calls it a BDC; it is a mortgage REIT (SIC:
   REIT, externally managed by KKR, no N-2 fee table, no BDC leverage limit,
   no fund-style "net return"). Keep on TSR/ROE with caveat, keep only on
   mapping metrics (leverage/yield/fees), or drop?
   - Default if unanswered: keep, restrict to mapping metrics, label basis.
2. **Fiscal-year misalignment.** CCLFX FYE Mar, GBDC FYE Sep, TAKIX/KREF Dec,
   Apex calendar. As-reported (current deck footnote 1) or aligned to nearest
   period-end before Apex quarter close? And: stale figure with age flag, or
   blank cell?
   - Default if unanswered: as-reported + age flag.
3. **Share class.** Deck footnote 3 says institutional for CCLFX/TAKIX.
   N-PORT gives fund-level returns cheaply; class-level needs narrative
   parsing. Hard requirement or is labelled fund-level acceptable?
   - Default if unanswered: fund-level, clearly labelled.
4. **Conflict presentation.** Resolved single value + appendix conflict log,
   or both values in-cell?
   - Default if unanswered: resolved value in-cell, conflict log appendix.
5. **LLM / compliance.** Constraint on sending public EDGAR text to a
   third-party model? API key available or must run key-free?
   - Default if unanswered: LLM optional, deterministic fallback always works.

Bonus if time: what does a wrong number cost vs. a blank cell? (calibrates
the confidence threshold for suppression)

## Window 2 (mid-build, after pipeline runs)
- TBD: driven by actual conflicts found in the data.

## Window 3 (pre-delivery)
- TBD: confidence model sign-off, production rollout assumptions for docs.
