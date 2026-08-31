# Next steps

## State

`python -m apexridge` runs end to end against live EDGAR. 59 tests passing.
**25 of 36 competitor cells populate** at the Q4 2025 anchor.

Outputs: board table, coverage breakdown (by gap ownership), NAV trend
(semi-annual footing), audit trail (one row per candidate, rejects included).

All three deliverables current: README, docs/technical-approach.md,
docs/solution-brief.md.

## Remaining gaps

**Ours (3)** — TAKIX incentive fee and hurdle, CCLFX hurdle. All fee terms,
which Lara ranked lowest. TAKIX's incentive *rate* is genuinely not stated in
its prospectus summary; it may be in the SAI or may be a website-sourced figure.

**Cadence-limited (3)** — CCLFX distribution yield and 3Y/5Y returns. Its March
fiscal year-end puts the annual report 275 days behind a Q4 2025 anchor, past
the six-month line. Not an extraction failure: Lara's own rule, biting where she
predicted. This is the live case for the fund-level fallback with the CIO.

**Client (1)** — TAKIX leverage, pending the CIO's regulatory-vs-economic ruling.

**Structural (4)** — KREF's three return rows, GBDC's 5Y.

## For the last consultation window

Only one window left. Spend it on things that cannot be resolved any other way.

1. **The two answers she owes** — CIO leverage definition, and the basis of
   Apex's own column (share class, net of which fees). The second still blocks
   every peer-minus-Apex delta.
2. **The fee-clock sign-off she asked for.** She said "run it by me before
   production and I will confirm it holds for the other funds." It is built.
   Also confirm she accepts the weaker claim it can support: "no amendment
   disclosed through <date>", not "confirmed in force at <date>".
3. **The cell-by-cell source review.** Which cells in the manual pack came from
   fund websites or IR pages rather than filings. Until this lands, the OURS
   backlog is not a committed backlog.
4. **Corrections to pass her:** GBDC and KREF publish NAV *quarterly*, not
   monthly — her drill-down footnote would overclaim. And if a two-tier
   incentive fee reached her as 15%/20% for GBDC, the example is wrong: both
   tiers are 15.0%, and 20% is the superseded rate.

## Known debt

- Two blank-cell enums (SuppressionReason, ReasonCode) are near 1:1. Kept split
  for client-facing wording; cheap to collapse.
- TAKIX hurdle extraction produces one junk candidate (1.765%) that loses the
  conflict correctly but drags the cell just under the confidence floor.
- CCLFX's NAV trend has 3 points where 4 were expected; older N-CSRS filings are
  not all being parsed. Cosmetic, not wrong.
- No scheduling or alerting. A metric that populated last quarter and stops is
  the operationally important signal, and nothing watches for it.
