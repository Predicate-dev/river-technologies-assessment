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

- **KREF stays in, provisionally, on a row-level mapping (Window 1, partner).**
  Rejected dropping KREF (CIO put it on the list; a missing column invites the
  "why did it disappear" question) and rejected filling every row by
  substituting the nearest REIT metric (that is the failure mode the engagement
  exists to remove). Provisional until the CIO confirms — flagged open.
- **KREF row-level mapping — the ask is not one problem, it is three.**
  Verified against EDGAR submissions: KREF is SIC 6798, entityType `operating`,
  files 10-K/10-Q/DEF 14A only. No NPORT-P, no N-CSR, no 486BPOS — i.e. none of
  the fund-reporting forms CCLFX/TAKIX file.
  - *Absent, not merely relabelled (net return 1Y/3Y/5Y):* a 10-K contains no
    NAV-based total-return series. The substitutes are market total shareholder
    return (price-driven, moves with the premium/discount to book) and ROE
    (GAAP earnings). Neither is the interval funds' number under another name.
  - *Present but differently defined (mgmt fee, incentive fee, NAV/share):*
    fees live in the external management agreement narrative, not an N-2 fee
    table — 1.50% on *stockholders' equity* vs. the funds' % of managed/net
    assets, and no "total annual expenses" line that includes interest.
    "NAV per share" is book value per share under GAAP/CECL, not an
    administrator-struck NAV under investment-company accounting.
  - *Maps with the footnote the deck already carries (leverage, distribution
    yield):* deck footnote 2 already concedes regulatory vs. economic basis.
    KREF's D/E includes non-recourse securitisation and repo; yield is on price
    vs. on NAV.
- **Schema consequence: every metric carries a `basis` field, not just a value.**
  Forced by the above — the KREF/interval-fund gap cannot be expressed as a
  footnote string bolted on at render time. Cheap now, expensive after lock.
- **Proceeding on KREF without the CIO; the answer is the same under both
  readings.** Partner could not say why KREF is on the list — the CIO set the
  peer list before the partner joined. Under his guess (KREF as an LP-facing
  alternative, not a performance comparable) the current design is already
  final. Under the other reading the CIO either accepts the blank return rows
  or asks for TSR — which the `basis` field makes a rendering change, not a
  rebuild. So the escalation gates a label, not the build. Rejected waiting.
- **Risk for the technical doc: the peer list has no documented selection
  criteria.** Not a KREF problem — no stated rationale exists for any of the
  four. The system therefore reports what each filer actually publishes and
  refuses to substitute near-metrics, rather than encoding an assumed intent.
- **Multiple candidates per metric on purpose.** Leverage is emitted on three
  constructions (gross debt/equity, liabilities/equity, (assets-equity)/equity).
  The third is a pure internal-consistency probe: if it disagrees with the
  second, the filer's balance-sheet tagging is inconsistent and every derived
  value for that fund should be downgraded.
- **Distribution ledger with cumulative differencing.** Filers tag YTD
  cumulatives and, in a 10-K, never tag fiscal Q4 standalone. Naive quarterly
  filtering understated GBDC's 1Y return by ~265bp (2.05% vs 4.71% corrected).
  Rejected "sum all facts" (double counts) and "90-day facts only" (drops Q4).
- **Day-count annualization with a window tolerance, not quarter counting.**
  A 5Y return measured over 4.75 years is not a 5Y return. GBDC's NAV history
  is quarterly only back to 2021-09-30, so 5Y is *suppressed with a logged
  reason* rather than mislabelled. Honest gap > plausible number.
- **Distribution yield reported on two bases (run-rate, TTM), not collapsed.**
  KREF cut its Q2 2026 distribution 0.25 -> 0.10; run-rate says 2.52%, TTM says
  5.34%. Collapsing them hides exactly the signal a PM benchmarks for.
- **cef:ManagementFeesPercent is a trap and is treated as one.** GBDC's tag
  reads 0.0213% from a 424B2 notes prospectus, not the fund's own fee table.
  Highest source tier, wrong number. Emitted with flags so reconciliation can
  overrule it -- proof that tier alone cannot be the confidence model.
- **Basis divergence is rendered at the cell, not in a footnote (partner,
  Window 1).** Explicit requirement: "I do not want a PM reading that row and
  assuming it is on the same basis as CCLFX without noticing the footnote."
  The deck's existing bottom-of-slide footnotes are exactly that failure mode.
  Rule enforced at render: any cell whose `basis` differs from the row's
  reference basis cannot render bare — it carries an inline marker resolving to
  a stated basis. Applies to KREF fees (on stockholders' equity) and KREF
  NAV/share (GAAP book value), not just the blank return rows.
- **Asymmetric loss is the design principle, not a tuning parameter (partner,
  Window 1).** A false-confident value costs far more than a gap — their board
  incident was a misread leverage basis point. Everywhere the pipeline faces
  report-vs-suppress, it suppresses. Rejected any "best guess" fill; rejected
  tuning a confidence threshold toward coverage. This also pre-answers Q4: on
  an unresolvable source conflict, do not silently pick a winner.
- **Temporal policy: as-reported + per-cell as-of date; blank beyond 6 months.**
  Rejected aligning to Apex quarter-end — recomputable from N-PORT monthlies for
  CCLFX/TAKIX but not for GBDC/KREF, so alignment would be method-inconsistent
  across a single row with nothing on the slide disclosing which cells were
  recomputed. A suppressed cell still renders the last-available as-of date.
- **Leverage gets the strictest treatment of any metric.** It is both the metric
  that caused their board incident and the one with the worst basis ambiguity
  (regulatory vs. economic; KREF's non-recourse securitisation and repo). Every
  leverage cell states its basis unconditionally — including when bases agree,
  where the general rule would let it render bare.
- **Client contact is an expert in their own benchmarking workflow.** Do not
  explain the domain to him; press him on definitional judgment instead. The
  deliverable docs should assume a reader who knows the workflow cold.
- **Institutional share class is a hard requirement, and it is reachable
  without the LLM.** Partner's reason: LPs enter at institutional minimums, so
  a blended fund-level number understates fee drag and flatters the competitor;
  and a number that contradicts deck footnote 3 gets caught by a PM. Since the
  LLM path is compliance-blocked, class-level comes from N-CSR / N-CSRS
  financial-highlights tables and 486BPOS per-class fee tables, parsed
  deterministically with bs4 (already a dependency). TAKIX files inline-XBRL
  N-CSR/N-CSRS (ctac-20260630.htm), which is cleaner still. Verified both
  filers publish these forms.
- **CONFLICT FOUND between two of the partner's own rules — needs his call.**
  Class-level data exists only at semi-annual/annual cadence, while N-PORT
  fund-level is monthly. CCLFX's March fiscal year-end means its freshest
  class-level source is the N-CSR for period 2026-03-31 (filed 2026-06-08,
  5 months old today) and the next class-level filing is the N-CSRS for
  2026-09-30, landing ~Dec 2026. So for part of each year CCLFX has no
  institutional-class figure under six months old, and the six-month rule
  blanks a cell the extraction did not fail on. TAKIX is unaffected right now
  (N-CSRS period 2026-06-30, filed 2026-08-21, two months old).
- **N-PORT parsed with a pull parser over the first ~7KB.** Each primary_doc.xml
  is ~8MB of holdings; everything we need precedes <invstOrSecs>. Rejected
  truncate-and-append-closing-tags (guesses wrong) and full-document parse (slow).
- **TAKIX share classes are unattributable, so no point estimate is emitted.**
  Its N-PORT carries 7 monthlyTotReturn rows with NO classId attribute. Document
  position is not a class identifier. Instead we publish the spread as a
  corroboration band (1Y: 3.19%-4.07%) and use it to bound-check whatever the
  narrative source claims for the institutional class. Rejected "take the first
  row" and "average the classes" -- both fabricate an attribution.
- **N-PORT depth capped at 8 filings (2 years).** 8MB each; 20 filings x 2 funds
  is not a demo. 3Y/5Y for the interval funds therefore come from the annual
  report's stated performance table, not from 20 more downloads.
- **"Reported zero" is distinguished from "field absent".** TAKIX reports 0.00
  in every N-PORT borrowing field while carrying $2.2bn of total liabilities on
  $4.47bn net assets. Emitting 0.00 leverage silently would be misleading, so it
  carries a zero_borrowings_but_material_total_liabilities flag. Open item for
  the client (NOTES/questions.md, Window 2).
