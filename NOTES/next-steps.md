# Next steps — single owner from here

Reconciled after the parallel sessions ended. Everything below is in this repo;
nothing is split across sessions any more.

## State

- `python -m apexridge` runs end to end against live EDGAR. 45 tests passing.
- 14 of 36 competitor cells populate at the Q4 2025 anchor; 4 conflicts
  resolved with logged rationale; 6 blanks carry a stated reason.
- All three deliverables exist: README, docs/technical-approach.md,
  docs/solution-brief.md.

## Fixed during reconciliation (was split work, now merged)

1. **Extractors were not anchor-aware** — the single worst bug in the repo.
   Adapters took the newest observation, eligibility then discarded it, and
   three of four funds went to zero structured candidates. Now every adapter
   selects as of the anchor and the filter drops nothing.
2. **A mis-contexted `cef` fee tag won basis selection on source tier alone**,
   displacing the true rate before the confidence model could weigh them.
   Fee metrics now have an explicit basis preference.
3. **A superseded rate was scored as an independent measurement that disagreed**,
   firing the conflict penalty and understating two correct fee cells. It is now
   a non-measurement: retained as evidence, excluded from the agreement maths.
   GBDC fees went from blank/Low to 1.0% and 15.0% at Medium.
4. **Historical-rate wording was not detected.** TAKIX resolved to a 1.50% fee
   retired in 2020. "Prior to <date>, the fee was X%" is now caught alongside
   GBDC's "reduced from X to Y".
5. **A parameter shadowing bug** — the reporting anchor was rebound to a NAV
   record mid-function.

## Blocked on the client (Window 2)

Ordered by cost of guessing wrong. See NOTES/questions.md for full framing.

1. **CIO's leverage definition** — regulatory vs. economic, and whether KREF's
   non-recourse securitisation and repo are in scope. The only open item that
   implies per-filer extraction work rather than a config change, and the same
   metric class as the board incident.
2. **Apex's own column: share class, and net of which fees.** Hard block on all
   derived peer-minus-Apex comparisons.
3. **Do fee terms go stale?** Better framing, adopted from the parallel session:
   should a terms metric's clock run from the last filing that *could* have
   amended it, rather than from the period end of the document we read? Under
   the flat 183-day rule, live and correct fee rates blank.
4. **Confirm the three items recorded as "closed by the partner"** that may
   never have been put to Lara — TAKIX class suppression, KREF dual-basis yield,
   GBDC 5Y blank.
5. **Compliance sign-off on the LLM tier.** Built, off, and not needed for
   anything currently extracted.

## Unblocked build work, highest value first

1. **Class-level extraction for CCLFX and TAKIX** — N-CSR/N-CSRS financial
   highlights and 486BPOS per-class fee tables. This is the largest coverage
   gap: it would fill NAV per share, distribution yield, and the trailing
   returns for both interval funds, and it is what makes the institutional
   share-class requirement satisfiable. Deterministic, no LLM needed.
2. **KREF management fee** — 1.50% on stockholders' equity, in the external
   management agreement narrative. Pattern does not currently fire.
3. **CCLFX 3Y/5Y returns** — the data is at EDGAR today; the limit is our
   8-filing N-PORT cap, not the filer. Re-measure coverage before raising it,
   since anchoring changed which two years the cap covers. The appendix must
   keep stating that this limit is ours.
4. **Incentive fee for the two interval funds** — CCLFX appears to charge none,
   which is worth confirming rather than reporting as an extraction gap.

## Known debt

- The two blank-cell enums (`SuppressionReason`, `ReasonCode`) are near 1:1.
  Kept split for client-facing wording; cheap to collapse later.
- TAKIX hurdle extraction produces one junk candidate (1.765%) that loses the
  conflict correctly but should be pattern-tightened.
- No scheduled-run or alerting layer. A metric that populated last quarter and
  stops populating this quarter is the signal that matters operationally, and
  nothing watches for it yet.
