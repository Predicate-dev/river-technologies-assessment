# Next steps

## State

`python -m apexridge` runs end to end against live EDGAR in ~8s cold, one
command, no manual steps. 144 tests passing.
**30 of 40 competitor cells populate**, 35 of 60 with the custom metrics enabled,
at the Q4 2025 anchor.

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

## Scope update — all three delivered

- **Custom metrics.** Declarative registry; a metric is a JSON definition, not
  code. `metrics/custom_metrics.json` ships the three named. Portfolio turnover
  and GBDC's non-accrual rate extract with no code change.
- **Fund discovery.** `--find` searches and classifies, `--add-cik` adds. Refuses
  filers it cannot classify. Ares Capital added cold populates 8 of 9.
- **Word output.** `output/benchmark_report.docx` on every run, blanks carrying
  their reasons.

Coverage with custom metrics enabled: 28 of 48 cells.

## For the last consultation window

Eleven questions, in NOTES/questions.md under "Window 3 (final)". The four
carried over are unchanged. The six new ones come from the scope update, and one
of them is bigger than it looks:

**Who authors a custom metric definition?** A highlights-table metric needs a row
label a PM could write. A prose metric needs a regex a PM will not write. The
feature as built assumes they send us the metric and we add the definition. If
they expect a self-service format, that is real additional work and should be
scoped before the demo rather than discovered at it.

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
