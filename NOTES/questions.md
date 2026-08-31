# Open questions for the client

## Window 1 (asked before schema lock)

1. **KREF classification.** ~~Brief calls it a BDC; it is a mortgage REIT~~
   **ANSWERED PROVISIONALLY (Window 1) — OPEN, escalated to CIO.**
   Partner chose (b): keep KREF, populate what maps, explicit caveat in the
   output that it is a REIT and net return is not apples-to-apples. Partner
   will not finalise unilaterally — the CIO put KREF on the list, so any
   scope-down comes from him. Treat as provisional; do not hard-code a drop.
   - **Follow-up I owe the partner (answered in-window):** it is not one
     failure mode, it splits by row. See NOTES/decisions.md "KREF row-level
     mapping".
   - **Still open for the CIO (Window 2 unless he answers sooner):** on the
     three net-return rows, does he want (i) blank + stated reason, or
     (ii) market total shareholder return shown in a visibly separate,
     differently-labelled row? Not the same cell either way.
   - **1a. What is KREF on the list FOR? — ASKED, partner does not know.**
     CIO set the peer list before the partner was looped in and did not walk
     through it name by name. Partner's *guess* (explicitly not from the CIO):
     KREF appears in the same LP conversations Apex does — allocators holding
     both private credit and CRE debt — so the CIO tracks it as an alternative
     the LPs are seeing, not as a performance comparable. If that guess is
     right the escalation resolves in favour of what is already being built:
     leverage / distribution yield / fees are exactly the right rows and the
     three blank return cells cost nothing. NOT BLOCKING — build proceeds.
   - **1c. NEW, and bigger than KREF: what is each of the four on the list
     for?** Nobody on the client side has stated the selection criteria for
     ANY peer; KREF merely exposed it. If the names were chosen for different
     reasons, a single 8-metric table is the wrong shape for at least one of
     them. Partner is meeting the CIO anyway — one extra sentence, no extra
     window.
   - **1b. Rule, not a ruling.** KREF is not a one-off — GBDC is a BDC on
     10-K/10-Q, not N-CSR, so its fee and return bases differ from the interval
     funds too. Does the CIO want to set the policy once (metric absent for a
     peer => blank + reason, never a substituted near-metric), or adjudicate
     cell by cell each quarter? The first is a system; the second is the manual
     process they are paying to remove.
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
