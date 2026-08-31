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
