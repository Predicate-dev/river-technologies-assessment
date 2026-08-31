# Open questions for the client

## Window 1 (asked before schema lock)

1. **KREF classification.** ~~Brief calls it a BDC; it is a mortgage REIT~~
   **RESOLVED (Window 1), pending CIO confirmation of the peer list itself.**
   Partner chose (b): keep KREF, populate what maps, explicit caveat in the
   output that it is a REIT and net return is not apples-to-apples. Partner
   will not finalise unilaterally — the CIO put KREF on the list, so any
   scope-down comes from him. Treat as provisional; do not hard-code a drop.
   - **Follow-up I owe the partner (answered in-window):** it is not one
     failure mode, it splits by row. See NOTES/decisions.md "KREF row-level
     mapping".
   - **CLOSED:** partner chose blank + stated reason on the three net-return
     rows. "A blank with an explanation is defensible to the board. A filled
     cell with the wrong definition is not." No TSR substitution.
   - Partner is taking 1a and 1c to the CIO in one conversation. Neither
     blocks the build.
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
2. **Fiscal-year misalignment. RESOLVED (Window 1).** As-reported, with the
   as-of date rendered *on the cell*, not in footnote 1. Partner accepted the
   argument that a half-aligned row (recomputable for CCLFX/TAKIX from N-PORT
   monthlies, not for GBDC/KREF) is worse than an honest as-reported one.
   - **Staleness: hard line at six months.** Older than that => cell blank,
     carrying the as-of date of the last available figure. Blanks are not
     empty; they carry provenance.
   - **Cost asymmetry, stated by the partner and now governing the whole
     confidence model:** last year a misread basis point on a *leverage ratio*
     reached a board presentation and was caught only afterwards. That incident
     is why this engagement exists. "A blank cell generates a question I can
     answer. A confident wrong number generates a question I cannot, and it
     follows me." System is to be conservative: flag uncertainty, suppress when
     stale, never fill a cell to avoid a gap.
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

**Carried to the CIO by the partner (he will not decide these unilaterally):**
- **A. Peer-list intent.** What is KREF on the list for, and what is each of the
  four on the list for? Determines whether one table is the right shape.
- **B. CCLFX institutional cadence gap.** Class-level data is semi-annual at
  best; CCLFX's March FYE leaves two windows a year with no institutional
  figure under six months old (next one projected early-to-late Dec 2026). Is a
  current *fund-level* figure with an explicit basis marker acceptable as a
  named fallback for CCLFX specifically? Partner's own preference is the blank
  (a PM catching a mismatch with footnote 3 is the exact failure he is buying
  this system to prevent) but he says the call is the CIO's. Build proceeds on
  blank + NOT_YET_FILED label; fallback is additive if the CIO wants it.
- **C. Compliance (Q5).** Written answer on third-party model use, timeline in
  days. LLM path descoped from the prototype meanwhile.
- TBD: driven by actual conflicts found in the data.

## Window 3 (pre-delivery)
- TBD: confidence model sign-off, production rollout assumptions for docs.
