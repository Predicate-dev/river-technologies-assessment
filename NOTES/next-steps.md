# Next steps

## State

`python -m apexridge` runs end to end against live EDGAR in ~8s cold, one
command, no manual steps. 69 tests passing.
**26 of 36 competitor cells populate** at the Q4 2025 anchor.

Outputs: board table, coverage breakdown, NAV trend (semi-annual), audit trail
(one row per candidate, rejects included).

## Nothing further is extractable

The coverage report's OURS bucket is **empty**. Every metric reachable from
EDGAR for these four filers is extracted. The 10 remaining blanks:

- **CADENCE (4)** — CCLFX distribution yield and all three trailing returns. Its March
  fiscal year-end puts the annual report 275 days behind a Q4 2025 anchor, past
  Lara's six-month line. Her rule, biting where she predicted. Live case for the
  fund-level fallback with the CIO.
- **CLIENT (1)** — TAKIX leverage, pending the CIO's regulatory-vs-economic
  ruling. All three constructions are computed and held.
- **STRUCTURAL (5)** — KREF's three return rows (a mortgage REIT publishes no
  fund-style return), GBDC's 5Y (tagged history spans 4.3y), CCLFX's hurdle
  (charges no incentive fee, so no hurdle exists).

Closed in the final pass: TAKIX incentive fee (15%, stated only in the worked
fee examples), TAKIX hurdle (6%, was losing to an adjacent catch-up rate),
CCLFX hurdle (reclassified from gap to inapplicable), KREF management fee
(1.50%, quoted quarterly on adjusted equity).

## For the last consultation window

Only these need her. Nothing here can be resolved by building.

1. **The two answers she owes.** CIO leverage definition; and the basis of Apex's
   own column (share class, net of which fees) — still blocking every
   peer-minus-Apex delta.
2. **Fee-clock sign-off.** She asked to confirm it holds for the other funds
   before production. Built and running. Confirm she accepts the weaker claim it
   supports: "no amendment disclosed through <date>", not "confirmed in force".
3. **Cell-by-cell source review.** Which manual-pack cells came from fund
   websites or IR pages rather than filings. This is the only thing that could
   change the coverage picture, and it can only shrink scope, not grow it.
4. **Corrections to pass her.** GBDC and KREF publish NAV *quarterly*, not
   monthly. And both GBDC incentive tiers are 15.0% — if 15/20 reached her as a
   two-tier structure, the example is wrong; 20% is the superseded rate.

## Known debt

- Two blank-cell enums (SuppressionReason, ReasonCode) are near 1:1. Kept split
  for client-facing wording; cheap to collapse, no deliverable benefit.
- No scheduling or alerting. A metric that populated last quarter and stops is
  the operationally important signal, and nothing watches for it. Deliberately
  descoped (NOTES/descoped.md): it needs a prior quarter's run to compare
  against before the signal means anything.

## Fixed in the final pass

- **Board table and coverage report disagreed on one cell.** CCLFX's 1Y return
  resolved to a fund-level figure, which render blanked for being the wrong
  share class while coverage still counted it. Reconciliation now ranks the
  institutional class above fund-level, and coverage derives from the rendered
  cells so the two can never drift. True count was 26, not 27.
- **A blank on the Apex column with no reason crashed the whole render.** A
  missing CSV column turned into a total failure rather than one empty cell.
- **CCLFX lost a year of NAV history** because one filing labelled its class
  "Class\n        I" and the comparison was on raw strings.
