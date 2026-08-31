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
- **Blanks are typed, not uniform (partner, Window 1).** He asked for the CCLFX
  cadence gap to read as "institutional figure not yet filed" rather than as a
  system failure. Generalised rather than special-cased: every suppressed cell
  carries a reason code — NOT_APPLICABLE (metric absent for this filer, e.g.
  KREF net return), NOT_YET_FILED (structural class-level cadence gap; carries
  expected filing window), STALE (figure exists, exceeds the six-month line;
  carries last-available as-of date), SUPPRESSED (unresolved source conflict or
  below confidence). A bare blank is unrepresentable in the output.
- **Expected filing window is derived, not hardcoded.** Median/min/max lag from
  reportDate to filingDate over the filer's own prior filings of that form.
  Observed: CCLFX N-CSRS 66-70d (n=7), N-CSR 68-84d (n=7); TAKIX N-CSRS 52-68d
  (n=9), N-CSR 58-66d (n=8). So CCLFX's next institutional figure (period
  2026-09-30) is projected to land early-to-late Dec 2026, from its own history.

## Window 1 continued — partner rulings, and the CIO boundary

- **Escalation boundary is now explicit: the partner owns the workflow, the CIO
  owns definitions and the peer list.** Partner will flag and route, not rule,
  on anything definitional. Practical consequence for the build: any question
  whose answer is a *metric definition* is a CIO item on a ~1-week cadence
  (single batched conversation, end of week), so the pipeline must be
  structured so definitional answers are render-time switches, not rebuilds.
  This is the second time the `basis` field has paid for itself.
- **Not-a-point-estimate is a label, never a rendered value (partner ruling,
  general).** Asked about TAKIX's unattributable class returns; answered as a
  rule. The 1Y corroboration band (3.19%-4.07%) is *not* rendered in-cell.
  Cell is suppressed and carries "could not attribute to institutional class".
  Partner's reason: a band generates a question he cannot answer cleanly,
  whereas the attribution failure is itself information the PM needs to see.
  Band is retained internally as a bound-check on any narrative-sourced figure
  and surfaced in the appendix, not on the slide. Rejected in-cell range.
- **KREF distribution yield: both bases in-cell, run-rate primary, TTM
  alongside (partner).** Not a footnote. Reason given: a 0.25 -> 0.10 cut is
  material enough that the context belongs at the cell. Confirms the earlier
  "render at the cell, not in a footnote" rule and extends it from basis
  divergence to basis *multiplicity*.
- **GBDC 5Y: blank, with the reason AND the actual coverage period stated
  (partner).** Explicitly must not be labelled 5Y when it is 4.75 years.
  Strengthens the existing day-count rule: a suppressed cell renders the
  reason and the window it *could* have covered, not just an as-of date.
- **CCLFX class-level staleness: blank + explanatory label is the build
  target; fund-level as a named fallback is a CIO decision.** Partner's ruling
  stands on its own (blank), so the deterministic path is unblocked. If the CIO
  approves a named fund-level fallback it is an additive labelled path, not a
  change to the blank logic. NOT BLOCKING.
- **TAKIX leverage basis (regulatory vs economic) is escalated and will not be
  guessed.** Partner: the CIO gestured at the distinction without defining it,
  and this is the exact metric class behind the board incident. Build proceeds
  by emitting *all* constructions as candidates (borrowings/equity, total
  liabilities/equity, (assets-equity)/equity) with the
  zero_borrowings_but_material_total_liabilities flag intact, and leaving
  selection to a single render-time policy constant. NOT BLOCKING; one line
  changes when the definition arrives.
- **Peer list is CIO-owned; the partner flags, he adds/removes.** Confirms the
  earlier decision to proceed on KREF without a ruling and to document the
  absent selection criteria as a risk rather than encode an assumed intent.
- **Temporal anchor is the reporting quarter (2025-12-31), not the run date.**
  Staleness measured against the anchor; a candidate is eligible when
  period_end <= anchor, irrespective of filing date. Rejected anchoring on
  today: it would blank Apex's own column under Apex's own rule while peers
  populated from mid-2026 N-PORT data, making the competitors look fresher
  than the client.
- **The Apex column gets the same basis discipline as the peers, because its
  basis is unknown.** Partner cannot confirm the share class or whether the
  stated net return is net of both fees or management only. Renders with basis
  UNCONFIRMED. Values still display — they are the client's own reported
  figures — but any *derived* comparison (peer-minus-Apex deltas, rankings) is
  suppressed until confirmed: a delta between two numbers of unknown basis is
  precisely the confidently-wrong number the engagement exists to prevent.
  Rejected assuming institutional/fully-net on the partner's explicit
  instruction.
- **Scope-change cost is asymmetric, and that is by construction.** Of the five
  open client items, four are config-level by design: Apex basis is a label on
  an already-rendering UNCONFIRMED column; the CCLFX fund-level fallback is a
  disabled flag; KREF's fate is an entry in the FUNDS registry; the LLM path is
  specified-but-unbuilt, so approving it later is net-new work with zero
  rework. Only the CIO's leverage definition implies real per-filer extraction
  work. Stated to the partner so he can prioritise which answers to chase.
- **Flex signalled on funds and metrics; NOT building for it.** Partner passed
  on an unofficial signal that the four funds and eight metrics may grow. The
  existing config-driven registry already makes an added fund or metric cheap
  *within a filer type already handled*. Deliberately not building a plugin
  system on a rumour — that is scaffolding nobody asked for, on an 8-hour
  clock. Two genuine cliffs named for him instead: (1) a new *entity type*, or
  any fund without an EDGAR presence, has no source adapter and no filings at
  all; (2) any new metric that lives in narrative prose rather than structured
  data is gated behind the same compliance answer that blocks the LLM path.
  The scope-flex question and the compliance question are therefore the same
  question, which he did not appear to realise.
- **Client contact is Lara, Apex Ridge's benchmarking expert.** Every Window 1
  answer above is hers. She knows the workflow cold — do not explain the domain
  back to her; spend her time on definitional judgment only. She routes the
  peer-list and leverage-definition questions to the CIO rather than ruling on
  them herself.
- **`temporal.py` vs `periods.py` are separate concerns, not a duplication.**
  `periods.py` reconstructs non-overlapping distribution intervals;
  `temporal.py` holds the reporting anchor, the staleness cliff and projected
  filing windows. The six-month limit itself is imported from `confidence.py`
  rather than redeclared — one source of truth for a client-set rule.

## Suppression mechanism (build)

- **A blank cell is a first-class value (`Suppression`), not a missing one.**
  Carries reason code, board-safe prose, the as-of date of the last available
  figure, and the actual coverage window. `ResolvedMetric.value is None` now
  always implies a populated `suppression`; `_suppress()` is the only path that
  blanks a value, so a bare blank cannot reach the deck by omission.
- **Reasons were being thrown away in `log.info`.** GBDC's 5Y diagnosis and
  TAKIX's class-attribution diagnosis existed only as log lines — the useful
  sentence is known upstream, where the data runs out, but died there.
  Extractors now write to a `SuppressionLog` that reconciliation reads.
  Rejected returning `(candidates, notices)` tuples from every extractor
  (churns every call site for one metric's benefit).
- **Suppression precedence: not-applicable > extractor diagnosis > hard
  staleness > confidence floor.** Ordered by what the reader can act on. A
  structural absence is not a data problem; "the data stops here" tells the
  partner what to do next, "confidence 0.31" does not.
- **The client's six-month rule was never implemented; it is now, as a cliff
  separate from the freshness factor.** Those answer different questions —
  freshness asks how much we trust a number, `STALE_LIMIT_DAYS` asks whether
  the client will put it in front of a board. A 521-day-old GBDC fee figure now
  blanks despite clean XBRL evidence, carrying its as-of date.
- **`internal_note` splits appendix evidence from cell prose.** Forced by the
  partner's ruling that the TAKIX class spread must not render as a range: the
  band is retained as a bound-check and for the appendix, and cannot leak into
  `cell_label`. A suppressed-but-computed value is also stashed there so the
  audit trail survives the blanking.
- **Bug found and fixed in this build: `SuppressionLog.__len__` made an empty
  log falsy**, so `if notices:` dropped every notice on exactly the runs that
  had none yet — silent, and it would have shipped a generic "no candidate
  value found" over every specific diagnosis. Guards are `is not None` and
  `__bool__` is pinned True. Regression test added.
- **Window-mismatch coverage reports the computable window, not the raw span.**
  First cut printed GBDC 5Y as "8.7y available" next to a blank 5Y cell, because
  NAV history reaches 2017 but is annual-only before 2021. A blank contradicting
  its own label is the failure mode this system exists to remove; it now states
  4.7y from the nearest usable anchor (2021-09-30).
- **Narrative tier: tables > anchored regex > LLM, with quote verification.**
  Fees and hurdles exist only in prose. LLM answers must return a verbatim
  supporting quote that is then checked to be literally present in the source;
  an unverifiable answer is discarded, not downgraded. Pipeline runs with no
  API key -- the deterministic tiers cover every fee currently extracted.
- **Superseded rates are the live hazard in a 10-K.** GBDC's states "reduced
  from 1.375% to 1.0%" and "from 20.0% to 15.0%". Patterns resolve to the
  CURRENT rate and flag superseded_rate_present_in_source. Reading the first
  number is precisely the misread-basis-point failure that caused this
  engagement.
- **Hurdle period qualifiers resolved by nearest-context.** "equal to 1.50% per
  quarter, or an annualized hurdle rate of 6.00%" contains both a quarterly and
  an annual rate. Context is measured around the captured NUMBER, not the match
  start; anchoring on the match start quadrupled an already-annual 6.00% to 24%.
- **Resolution is by weight of evidence, not tier alone.** Same-basis candidates
  are clustered by agreement; the cluster with the most *independent*
  extractions wins, then fewest flags, then tier, then recency. A repeated match
  of the same table through two anchors counts once, so a duplicate cannot vote
  itself into the deck.
- **"stated_as: quarterly" moved out of `basis` into `transforms`.** As a basis
  key it split conflicting hurdle values into separate groups so they never got
  reconciled against each other -- a silent way to ship a wrong number.

## Basis disqualification (TAKIX leverage)

- **A flag that means "this construction measured nothing" is not a confidence
  penalty.** TAKIX's gross-debt leverage is 0.00 — arithmetically correct,
  informationally empty, since the fund reports zero borrowings while carrying
  $2.2bn of total liabilities on $4.47bn net assets. Discounting it to 0.46
  left it above the 0.40 floor and it rendered as `0.00x, Low`. That is the
  "confident wrong number" on the exact metric behind the client's board
  incident. `DISQUALIFYING_FLAGS` in reconcile.py now blanks it outright.
  Rejected lowering the global floor (would blank unrelated good cells).
- **A disqualified primary basis is never replaced by the next basis down.**
  Falling through to total_liabilities_to_equity (0.4939) would have silently
  answered the regulatory-vs-economic question the partner escalated to the
  CIO, by choosing the economic reading and not saying so. The cell blanks and
  names both readings; the alternative is preserved in `internal_note` for the
  appendix. This is the one place the pipeline holds a computable number back
  purely because the *question* is open rather than the data.
- **Renders as its own reason code, not as "basis unconfirmed".** Settled with
  the render session: "we know the basis exactly and it fails to measure the
  thing" (TAKIX leverage) and "we do not know what basis this number is on"
  (the Apex column, where the client could not state share class or fee
  treatment) are opposite states. Collapsing them would understate the only
  case where the pipeline withholds a computable number.
- **Gate requires the whole basis to be disqualified.** One bad extraction
  alongside a clean one on the same basis is an ordinary conflict and resolves
  normally. Tested.
- Unaffected: CCLFX 0.29x, GBDC 1.23x, KREF 3.25x.

## Working split with the parallel session

- **Pipeline / render split.** This session owns reconcile, confidence, the
  Suppression block in models, and the XBRL/N-PORT extractors. The parallel
  session owns render (Cell/ReasonCode/ShareClass), temporal (anchor,
  eligibility), and narrative extraction. Agreed explicitly after both sessions
  independently started pipeline orchestration.
- **Two blank-cell enums kept deliberately, not collapsed.** `SuppressionReason`
  (8 values) is the pipeline diagnosis and carries the coverage arithmetic;
  `ReasonCode` (5 values) is the client-facing render vocabulary in the
  partner's own wording. An explicit documented map between them, failing loudly
  on an unmapped reason. Rejected merging: loses either the granularity or the
  wording.
- **Open correctness bug, owned by the other session: `temporal.is_eligible` is
  not wired.** Nothing filters candidates whose period_end is after the deck's
  anchor (2025-12-31), so the deck currently shows peers at mid-2026 against
  Apex's Q4 2025 column — peers look fresher than the client. Flagged; the
  reconciler will take the anchor as its `reference_date` once the filter lands.

- **Known debt, recorded rather than argued away: the two blank-cell enums are
  near 1:1** (8 `SuppressionReason` vs 9 `ReasonCode`). The split's remaining
  value is client-facing wording plus two render-only states that no suppression
  produces. One enum with a label table would be simpler and would remove a
  class of mapping bug; we kept the split because collapsing it mid-engagement
  churns the test suite, not because it is load-bearing. Cheap to collapse later.
- **Filing-lag projections must not be computed from XBRL companyfacts.** A
  period's earliest appearance there is often a *comparative* restatement in a
  later filing: GBDC's 2020-09-30 and 2021-09-30 periods both first appear in
  the FY2022 10-K, implying 782d and 417d lags against a true cadence of ~50d
  (52/51/50/49d for FY2022-FY2025). Projected "expected filing" windows must
  come from the submissions index, which has one row per actual filing.

## Window 2 — Lara's rulings

- **Terms metrics get an amendment-based staleness clock (Lara, Window 2).**
  Ruling: a fee rate cannot change without a filing, so the question is whether
  an amendment has landed, not how old the read document is. If the rate is
  stable and the last amendable filing is within six months, it shows. Applies
  to *terms metrics generally* — management fee, incentive fee, hurdle, anything
  that can only move by filing — not a per-metric carve-out. Output must label
  it "rate per current advisory agreement as of <amendment date>" so the
  provenance is visible. To be re-confirmed by her before production.
  Rejected the original framing (exempt fees from staleness) — that treats the
  rule as having an exception rather than the clock as measuring the wrong thing.
- **Verification limit stated to Lara rather than papered over.** We can confirm
  a later amendable filing exists and does not restate the rate; we cannot
  confirm that silence means unchanged, since a filer need not repeat an
  unamended fee. Label is therefore "no amendment disclosed through <date>",
  never "confirmed in force". A rate not itself restated within the window is
  flagged so a reader can distinguish a re-read rate from an unchanged-by-
  omission one.
- **Leverage: all three constructions stay computed, cell stays blank, no
  default (Lara -> CIO, Window 2).** She is taking regulatory-vs-economic, the
  KREF securitisation/repo scope, and the TAKIX zero-borrowings case to the CIO
  as one question, explicitly not as a menu. Confirms the existing
  BASIS_DISQUALIFIED behaviour is what she wants; no code change.
- **Apex column deltas stay suppressed (Lara, Window 2).** She confirmed
  suppression is correct and owns closing the share-class / fee-basis question
  this week. No derived comparison ships before it lands.
- **Three prior resolutions CONFIRMED as hers, not consultant drafts (Window 2).**
  TAKIX class-range suppression; KREF yield showing both bases with run-rate
  primary; GBDC 5Y blank with actual coverage stated. The flag in
  NOTES/questions.md recording them as unverified is now resolved -- they were
  genuinely her decisions.

## Window 2 — Lara's rulings (confirmed, not consultant defaults)

- **Fee timing: the rate in effect DURING the reporting quarter, not the current
  rate.** "The PMs are benchmarking that period's performance against that
  period's fee burden." Affects GBDC (1.375% -> 1.0%) and TAKIX. The pipeline
  currently resolves fee conflicts by source majority, which is the wrong
  mechanism entirely for a rate change — majority vote on a time series is
  meaningless. Extractor/reconcile lane.
- **Two-tier incentive fees: show BOTH components, labelled.** GBDC's 15% and
  20% are almost certainly income vs. capital-gains tiers, not a conflict.
  "A single blended rate destroys information the PMs need, and 'we resolved a
  conflict' when it was actually a structure is exactly the kind of silent
  decision I do not want in the output." Reconcile must not collapse a
  structure into a conflict.
- **TAKIX drops out of the main table and becomes a footnote.** "A column with
  one cell is not a comparison, it is noise, and a PM will ask why it is there."
  What is absent and why must stay visible — the zero reported borrowings
  against $2.2bn of liabilities especially. Render lane.
- **Confidence floor holds at 0.40 for now.** She wants the blank breakdown
  first; if coverage improves once the CIO items resolve, the floor question may
  answer itself. Revisits with the PMs before production.
- **Adoption test, stated by her:** if the blanks concentrate in TAKIX/KREF and
  CCLFX/GBDC are substantially populated, the PMs will adopt. If CCLFX is
  half-blank, "that is a different conversation."

- **Blank taxonomy at the Q4 2025 anchor (17/36 populated).** The headline
  number understates the position badly, because most blanks are OURS:
  - *Structural, nothing to be done:* KREF x3 return rows; GBDC 5Y (NAV history
    begins 2021-09-30); TAKIX leverage (pending the CIO's basis). = 5
  - *Possibly ours:* TAKIX x3 class attribution — N-PORT carries unlabelled
    class series, but N-CSR financial highlights DO name classes. Worth one
    attempt before accepting it as structural.
  - *Ours:* CCLFX 3Y/5Y (our 8-filing N-PORT depth cap; data is at EDGAR) and
    8 x "no figure located" across CCLFX/TAKIX/KREF fee, NAV and yield fields
    that are in filings already downloaded. = 11
  So CCLFX's 3/9 fails Lara's adoption test, but all six of its blanks are our
  extraction coverage, not Cliffwater's disclosure. The honest report is "not
  yet, and the gap is ours" — not "the filings do not support it".
- **"None charged" is extracted, not taken on the client's word (Window 2).**
  Lara confirmed CCLFX charges no carry. Rather than encode her recollection,
  the fee-table parser now treats the *absence* of an incentive row in a
  demonstrably complete N-2 fee table (management fee row + total + other
  expenses present) as affirmative evidence of none charged. Renders as
  "none charged", not "0.00%" -- a fee of zero and a measured zero are
  different statements on a slide. Flagged inferred_from_absence at 0.80.
  Rejected a client-attested override tier: the point of the system is that
  figures trace to filings.
- **Coverage classification is by who owns the gap, not by count (Lara,
  Window 2).** "The shape matters more than the count." Every empty cell is
  labelled FILLED / OURS / CADENCE / CLIENT / STRUCTURAL. Corrected one
  misclassification before it reached her: TAKIX's class-attribution failures
  were marked STRUCTURAL, implying unfixable, when the class-level source
  (N-CSR financial highlights) exists and simply is not built yet. Telling a
  client a gap is permanent when it is our backlog is the same category of
  error as reporting a wrong number.
- **Build priority set by Lara (Window 2):** net returns, leverage, distribution
  yield -- "the three the PMs act on in every quarterly conversation". Fees
  matter but move rarely; NAV trend is context. Thin confidence gets fixed in
  that order.
- **NAV per share is an 8-quarter trend, not a point (Lara, Window 2).** The
  board excerpt was a simplified version; the metric spec is authoritative.
  Accepted as a materially larger extraction job for the interval funds.
- **Pack is built ~2 weeks after quarter close (Lara, Window 2).** Ruling: run
  on time with explicit gaps and expected filing dates rather than wait for
  stragglers. "A partially populated table on time is more useful than a
  complete one late." Makes the projected-filing-window machinery in
  temporal.py load-bearing rather than decorative.
- **No prior-quarter pack for reconciliation — compliance, not reluctance.**
  Lara will not share live fund data outside the firm without sign-off. The
  redacted format reference is all we get. Consequence for the technical doc:
  the validation section rests on internal cross-source agreement and on
  reasoning, not on any external check. Say so plainly rather than implying a
  validation we never ran.
- **SOURCE SCOPE IS NOW AN OPEN QUESTION, and it was not before.** The analysts
  "sometimes pull from fund websites, investor relations pages, and press
  releases in addition to the EDGAR filings". The engagement brief scopes the
  system to EDGAR. So some cells the manual deck filled may have no EDGAR
  source at all, and my Window 2 claim that CCLFX "should reach 8 or 9 of 9"
  was over-confident — it assumed every gap was our extraction coverage.
  Retracted pending her analyst conversation this week.
- **Lara's own conclusion, and the line the solution brief should be built on:**
  "Do not assume the manual deck was accurate just because it had no blanks —
  that is precisely what I can no longer assume either." The system is not
  adding blanks to a previously complete picture. It is producing the first
  honest accounting of which cells were ever actually sourced.
- **Warn her before she talks to the analysts:** if non-EDGAR sources come into
  scope, it is not a small addition. The entire confidence model is built on
  filing-level provenance — accession, in-document locator, verbatim excerpt.
  A fund website has no accession, no immutable version, and no audit trail; a
  fact sheet is replaced silently. Anything sourced that way cannot carry the
  same confidence grade, and mixing the two without labelling would reintroduce
  exactly the untraceable number the engagement exists to remove.
- **NAV trend renders on a common semi-annual footing (Lara, Window 2).**
  Class-level NAV exists only in N-CSR/N-CSRS for the interval funds, i.e.
  semi-annually (CCLFX Mar/Sep, TAKIX Dec/Jun); N-PORT carries no per-share or
  per-class field at all. Rejected a mixed-cadence chart on her instruction:
  "a mixed-cadence chart will generate a question from the PMs about why the
  lines have different intervals before they get to the numbers." Semi-annual
  is the lowest common denominator across the set and is therefore the
  standard. Cadence to be labelled on the chart.
- **Span assumption, stated not assumed silently:** she ruled on cadence, not
  span. Defaulting to the spec's 2-year window (8 quarters) at semi-annual
  cadence = 4 points per fund, with Apex's own column downsampled to the same
  footing so the comparison is genuinely like-for-like. Flagged to her; a
  4-year / 8-point span is a one-line change if she wants more depth.
- **CORRECTION owed to the client: GBDC and KREF have QUARTERLY NAV data, not
  monthly.** Her drill-down footnote would have overclaimed. Their NAV per share
  is tagged in 10-Q/10-K on a quarterly cadence; no monthly per-share series
  exists for any fund in the set. N-PORT's monthly figures are total returns and
  net assets, not NAV per share, and only for the interval funds.

## Client rulings on fees (relayed via the render session, Window 2)

Recorded as client decisions, not consultant defaults. Provenance note: these
reached this session relayed by the parallel session, not heard directly.

- **Fee timing: the rate in force DURING the reporting quarter, not the current
  rate.** Client's reason: "the PMs are benchmarking that period's performance
  against that period's fee burden. A current rate that changed after the fact
  is a different number." Consequence for the pipeline: fee resolution must be
  by effective date against the anchor, NOT by source count.
- **Majority vote across sources is the wrong mechanism for a rate change, and
  it was never measuring what it appeared to.** GBDC's fee resolved to 1.0%
  because it was "agreed on by 3 independent extraction(s) vs 1.375 (1)". Three
  mentions of a new rate do not make the old rate wrong for a period it
  governed. Worse, the 10-K states 15.0% as the incentive *rate* and separately
  15.0% as the incentive fee *cap*, and repeats its amendment sentence many
  times — so the "independent extractions" were largely one document repeating
  itself. Apparent corroboration from a single document is not corroboration.
- **Two-tier fee structures are emitted as two labelled components, never
  blended or resolved as a conflict.** Client: "a single blended rate destroys
  information the PMs need, and 'we resolved a conflict' when it was actually a
  structure is exactly the kind of silent decision I do not want." Same family
  as the existing basis-vs-conflict distinction — a two-tier fee is two
  measurements of different things, like gross-debt vs total-liabilities
  leverage.
- **Confidence floor holds at 0.40 pending the coverage picture.**

### Correction to the ruling's worked example — verified against source

- **GBDC's 15% and 20% are NOT income vs capital-gains tiers. 20% is the prior
  rate.** Checked in the cached FY2025 10-K (gbdc-20250930.htm): "the incentive
  fee rates were reduced from 20.0% to 15.0%" (plural — both tiers moved
  together), with the Income Incentive Fee at "15.0% of Pre-Incentive Fee Net
  Investment Income" and "the Capital Gain Incentive Fee, equals (a) 15.0% of
  our Capital Gain Incentive Fee Base". GBDC does have the two-tier structure
  the client described; both tiers are 15.0%. Rendering 15/20 as two tiers
  would have invented a capital-gains tier that does not exist — a fabricated
  fee number on a board deck, i.e. the failure this engagement exists to remove.
  The ruling's *policy* is adopted; its worked example is not.
- **At the 2025-12-31 anchor the mechanism is wrong but the output is right by
  coincidence.** Management fee 1.375% -> 1.0% effective 2024-07-01; incentive
  20% -> 15% amended June 2024 and restated May 2025. Both in force at the
  anchor, so effective-date resolution returns the same 1.0% and 15% that the
  majority vote returned. It breaks the moment the deck reports an earlier
  quarter.
- **Dropped before building: the planned "exclude superseded_rate from the
  agreement computation" fix.** It would have entrenched the wrong answer
  whenever the anchor predates a rate change — exactly the case the client just
  ruled on. Superseded by effective-date selection.
- **GBDC's hurdle is extractable and currently blank everywhere:** "hurdle rate
  of 2.0% quarterly (8.0% annualized)", same document.

## Open regression (blocking, in this session's lane)

- **Eligibility filtering landed before the extractors were anchor-aware, and
  it empties the deck.** Structured candidates surviving `is_eligible` at the
  2025-12-31 anchor: CCLFX 3->0, TAKIX 2->0, GBDC 11->2, KREF 6->0. Cause is
  not the filter: `facts.latest()` and `reports[-1]` take the newest
  observation (mid-2026), eligibility correctly discards it, and nothing falls
  back to the newest *eligible* observation. Fix is anchor-aware extraction in
  xbrl_metrics and nport. Not yet started — awaiting go-ahead.
- **The 28 passing tests do not catch this**, because they exercise
  reconciliation with synthetic candidates and nothing runs the extractors
  against an anchor. That test gap is why it landed green.

## Named defect in the confidence model: agreement rewards verbosity

- **`confidence.independent()` treats two candidates from the SAME filing as
  independent whenever their transforms differ.** So a filer that repeats a
  sentence, or states a figure in several places, manufactures corroboration:
  the agreement factor rises to 1.10 with no second observation behind it.
  GBDC's "agreed on by 3 independent extraction(s)" was one 10-K repeating its
  own amendment sentence, and counting the incentive fee *cap* (15.0%) as if it
  were the incentive *rate* (15.0%).
- **This is separate from the fee-timing ruling and must not be absorbed into
  it.** Effective-date resolution fixes which rate wins; it does not stop a
  verbose filer inflating confidence on every other metric. Recorded as its own
  defect so it survives the fee fix in the technical doc.
- **Direction of fix (not yet built):** corroboration requires a genuinely
  separate observation — a different accession, or a different source tier.
  Same-accession/different-transform is a re-reading, not a second reading, and
  should score as `AGREEMENT_SINGLE` at most.
- **Worth keeping in the technical doc even after it is fixed:** at the current
  anchor the broken fee mechanism returns the right values by coincidence, so
  the output looks correct. "The output looks right" is not evidence that the
  mechanism is right — this is the cleanest illustration of it in the project.

- **Correction to an earlier note here: `incentive_hurdle_pct` is not blank
  across the board.** That note predated the narrative extractor landing. Live:
  GBDC 8.00%, KREF 7.00%, TAKIX 6.00%, CCLFX blank (no_candidate).

## Class-level extraction (financial highlights)

- **N-CSR/N-CSRS financial highlights is the only class-level source, and now
  the largest single coverage win.** Closed CCLFX and TAKIX on NAV per share,
  distribution yield and all three trailing returns at Class I. Coverage
  18/36 -> 24/36; OURS gaps 13 -> 4. Satisfies the institutional-class
  requirement that was agreed in Window 1 but unmet until now.
- **Trailing returns are chain-linked from stated annual returns.** The filings
  publish each fiscal year's total return but never an annualized trailing
  figure, so the arithmetic is ours and is recorded on every candidate.
- **Returns are taken only from ANNUAL tables.** An N-CSRS leading column is a
  part-year stub that looks identical to an annual figure; chain-linking it
  would understate a trailing return with no visible symptom. Point-in-time NAV
  still uses the freshest report, so CCLFX's NAV comes from the Sept N-CSRS
  while its returns come from the March N-CSR.
- **NAV read by column position, not by year.** A semi-annual table repeats the
  fiscal year for its stub column ("2025", "2025"); keying by year collapsed
  the two and silently returned the older figure.
- **pick_class returns None rather than substituting another class.** A blended
  or retail figure understates fee drag and flatters the competitor, which is
  precisely what the institutional requirement exists to prevent.
- **Two table layouts, both handled.** TAKIX uses bare year headers and labels
  the class in the header row; CCLFX uses period phrases, names the class only
  in the heading above the table, and splits negatives across cells as "(0.90"
  then ")". A dropped sign turns a distribution into a gain.
- **NAV trend built on the client's semi-annual footing.** Semi-annual cadence
  for every fund, plotted at each filer's own reporting dates rather than
  interpolated onto a shared grid -- there is no calendar date on which all four
  report (CCLFX Mar/Sep, TAKIX and KREF Jun/Dec, GBDC Mar/Sep). Interpolating
  would invent observations no filer published. Cadence and per-point dates are
  stated on the output.
- **KREF's management fee is quoted quarterly on adjusted equity.** "the greater
  of $62,500 or 0.375% of weighted average adjusted equity" -> 1.50% annualized,
  carrying a pct_of_adjusted_equity basis marker. Reported raw it would read
  0.375% beside peers quoting ~1.0% annually: a wrong number that looks
  plausible, which is the worst kind. Bug found in the detector: a `[^.]` gap
  cannot span the rate because the rate itself contains a decimal point.
  Regression test added for exactly that.
- **TAKIX's incentive fee RATE is not in its prospectus summary** -- the hurdle
  (6.00% annualized) and catch-up are stated, the rate is not. Reported as an
  honest gap rather than inferred. Lara could not recite it from memory either
  and asked the system to pull it; the correct answer is that this document does
  not state it.

## Final consistency pass

- **Coverage now derives from the rendered cells, not the resolved metrics.**
  They disagreed on CCLFX's 1Y return: the pipeline resolved a fund-level
  figure, render blanked it for being the wrong share class, and coverage still
  counted it as populated. Two client-facing documents disagreeing about which
  cells are filled is worse than either number being wrong, because nobody reads
  them side by side. Invariant now enforced by test.
- **Institutional share class ranks above fund-level in reconciliation.** The
  root cause of the above: a fund-level N-PORT candidate out-ranked a
  class-level one from the financial highlights on tier alone, so render blanked
  a cell whose correct value we already had. Corrected count: 26 of 36, not 27.
- **A blank on Apex's own column carried no reason and crashed the render.** The
  Cell type raises on a bare blank, which is the right behaviour -- but it meant
  a missing CSV column became a total failure rather than one empty cell. Found
  by the consistency test, not in production.
- **Share-class labels are normalized before comparison.** One CCLFX filing
  labels its class "Class\n        I"; raw string comparison dropped that table
  and the fund silently lost a year of NAV history from its trend.

## Peer comparison

- **Side-by-side columns are adjacency, not comparison.** The brief asks the
  system to compare against Apex's own data; until now it only placed the
  columns next to each other. `render/comparison.py` produces peer median,
  range, ordering, and Apex's delta and rank.
- **Comparability is decided on what a figure measures, not how it was derived.**
  A first cut compared whole basis strings and excluded TAKIX's returns for being
  chain-linked annual rather than NAV total return — both are net returns on NAV.
  That left most rows with a single "peer" and quietly defeated the very
  normalization the system exists to do. Now a narrow per-metric key: fee base,
  NAV measure, yield denominator, leverage basis. Exclusions are down to the two
  genuinely incomparable cases, both KREF.
- **Rankings only where direction is defined.** Returns, yields and fee terms
  have a better and a worse. NAV per share is a share price and leverage is a
  risk posture; both are ordered without a ranking claim.
- **The Apex gate is a real switch, and now provably so.** Peer-to-peer
  statistics do not depend on Apex's basis and render today; Apex-versus-peer
  deltas are computed and withheld behind `APEX_BASIS_CONFIRMED`. A test flips
  the flag and asserts the output changes -- the technical doc tells the client
  this is one flag rather than a rebuild, so that claim is now tested rather
  than asserted.

## Window 3 — Lara's rulings

- **A superseded rate never renders bare (Lara, Window 3).** Her words: "a
  reader who sees 20% without context will treat it as live." GBDC's superseded
  20% and KREF's *live* 20% are the same number meaning opposite things, so the
  label travels with the value rather than living in a caption. Where the filing
  states an effective date the label carries it; where it does not, the label
  says so rather than claiming a date we do not have. Tested in both directions,
  including that a live rate is not over-labelled.
- **The GBDC 15/20 "conflict" was never a conflict.** It was a current rate and
  a historical one, which she correctly identified from the correction. The
  two-tier display holds -- both tiers really are 15.0% -- and the cell now
  states which tiers the rate applies to, detected at document level because a
  BDC names its tiers pages away from where the rate is matched.
- **NAV drill-down footnote: "Quarterly data available on request" (her
  wording).** Monthly was never accurate and must not appear in print.
- **Fee-clock label confirmed for all funds.** "No amendment disclosed through
  this date", never "confirmed in force". She would rather own the limitation
  than have the deck imply a confirmation nobody made.
- **TAKIX leverage stays blank until the CIO rules.** Reconfirmed; do not move.
- **Weighted average spread: extraction work NOT authorised.** She will take the
  definition question (spread over benchmark vs all-in yield) to the PMs first.
  No per-filer table work until a definition exists.
- **Custom metric authorship: we write the definitions, not the PMs.** The
  regex-free `match` form stays -- it costs nothing and makes definitions
  readable to a reviewer -- but self-service is not the workflow.
- **Word styling: do not guess.** House template, fonts and logo coming by end
  of week. The IC committee would notice immediately.

Due from her today: leverage definition with the KREF perimeter, the Apex column
basis, and the analyst sourcing results.

## Window 3 close — client rulings and one corrected inference

- **Cadence blanks now name their source.** `_stale_detail` puts form type,
  period end, filing date and the limit on the cell. Chose period-end-to-anchor
  as the stated distance and rejected the client's own draft wording ("filed 275
  days prior"), which would have described a rule the system does not implement:
  decision D makes a source eligible on the period it covers, whenever filed.
  CCLFX's report is 275d back on period end but 209d on filing date, so the
  wrong version fails on the first follow-up question in the room.

- **Leverage: two rows, not one.** CIO ruled both bases. Client chose separate
  regulatory and economic rows over a single row carrying a basis note --
  "exactly the kind of thing a tired reader misses". Rejected the one-row form
  for the same reason the engagement exists. KREF: non-recourse securitisation
  excluded, repo included. This is the only ruling implying per-filer extraction
  rather than a config switch.

- **Apex column basis confirmed:** institutional share class, net of both
  management and incentive fees. Unblocks every peer-minus-Apex delta;
  `APEX_BASIS_CONFIRMED` flips from False.

- **Fee-clock claim accepted at its true strength.** Client accepts "no
  amendment disclosed through <date>" rather than "confirmed in force at
  <date>". A filer need not restate an unamended fee, so the stronger phrasing
  claimed more than the filings support. Wording already implemented this way.

- **Sourcing review: the client's conclusion was wrong and was corrected before
  it reached leadership.** She read "analyst sourced this from a fund website"
  as "this is not in EDGAR" and moved six cells to structural. Six of the eight
  are populated from EDGAR in the current run; the remaining two blank for
  unrelated reasons (CCLFX hurdle -- no incentive fee exists, so no hurdle;
  CCLFX distribution yield -- cadence). Net movement to structural: zero. The
  review answers where an analyst went, not what a filing contains. Recorded
  because the same conflation will recur every quarter.
  - Genuine yield from it: TAKIX incentive fee, unsourced in the client's pack,
    is now EDGAR-sourced at 15.0% (2025-04-28) with provenance -- their
    highest-risk cell closed. And CCLFX incentive fee is a real conflict: their
    pack carries a website figure, the filings say no incentive fee is charged.
    Filing wins; the client is briefing the CIO that the pack was wrong.
  - The review was also aimed at the wrong cells. The 13 possibly-not-in-EDGAR
    cells are the expanded metrics (non-accrual x3 funds x2 bases, weighted
    average spread x4, GBDC portfolio turnover, TAKIX/KREF total annual
    expenses). Client is re-running the question against that list.

- **Apex's leverage basis is gated separately from the rest of her column.**
  Her Window 3 confirmation covered share class and fee treatment, which
  legitimately unblocked returns, fees and yield. It said nothing about which
  leverage basis her single unlabelled ratio uses. With the peers now on two
  bases that differ by more than a factor of two, publishing a delta between her
  ratio and a median of one of them would be a materially wrong number on the
  exact metric behind the board incident. `APEX_LEVERAGE_BASIS_CONFIRMED` is a
  separate flag, defaulting False; the value renders, the delta does not.
- **Apex's ratio maps to the regulatory row only, not both.** Considered showing
  it against both rows and comparing against neither; rejected in favour of the
  parallel session's sharper argument -- reusing a borrowings-over-equity figure
  on the economic row would put a number understated by construction beside
  peers computed the other way, which flatters the house. The economic row's
  Apex cell blanks with that reason.
- **Client rulings relayed between sessions were verified with the user before
  being built on.** `APEX_BASIS_CONFIRMED` publishes every peer delta, and it
  was flipped on a client confirmation this session did not witness. The
  verification cost one question and the downside of being wrong was the one
  outcome the client was most explicit about. Confirmed genuine.

## Leverage: the CIO's ruling, built

- **Two metrics, not one row with a basis label.** `leverage_regulatory_dte` and
  `leverage_economic_dte`. This deleted the `BASIS_PREFERENCE` entry for
  leverage, which had been silently choosing gross-debt over total-liabilities.
  A preference answers the question; a second row asks it out loud.
- **KREF's perimeter is per-filer extraction, and had to be.** The excluded
  balance is `kref:CollateralizedLoanObligationsNet` -- a company-extension tag.
  The SEC company-facts API serves only us-gaap/dei/srt, so it is invisible to
  `XbrlFacts` and the perimeter is computed from the 10-K's own inline XBRL
  (`narrative.inline_facts`). This is why the item was half a day rather than a
  switch. KREF: 2.45x -> 2.98x regulatory, 4.47x -> 3.45x economic. The old
  economic figure carried $1.2bn of debt with no recourse to KREF.
- **The perimeter applies to both rows.** A perimeter states which obligations
  are this filer's leverage; applying it to one row would leave the excluded
  balance visible on the other, so the two rows would describe different
  entities.
- **ASSUMPTION, stated not hidden: KREF's $632m secured term loan is IN, on both
  rows.** The CIO ruled on securitisation (out) and repo (in) and said nothing
  about the term loan. It is plain recourse corporate debt and excluding it
  would need a reason nobody has given. Logged as a question, not a blocker.
- **`load_docs` selects narrative documents by FILING date, which is wrong for a
  balance sheet.** It picked KREF's 2024 balance sheet for a Q4 2025 anchor,
  because the 2025-12-31 10-K is filed in early 2026; the cell blanked as stale
  rather than rendering a year-old number, which is the good failure. Added
  `balance_sheet_doc`, selecting on report_date per decision D. Filing-date
  selection is still correct for the terms documents it was written for.
- **Confirming the share class did NOT confirm the leverage basis.** Flipping
  `APEX_BASIS_CONFIRMED` would have published an Apex-versus-peer leverage delta
  struck against a median whose basis nobody has stated -- Apex's CSV has one
  unlabelled `leverage_ratio_dte` column. The bases differ by more than 2x
  (CCLFX 0.32x regulatory vs 0.79x economic), on the metric behind the board
  incident. Added `APEX_LEVERAGE_BASIS_CONFIRMED`, separately gated: the figure
  renders on the regulatory row marked `[leverage basis unconfirmed]` and is
  held out of every leverage median, range and delta. Caught by a peer session
  reviewing the split.
- **BASIS_DISQUALIFIED reclassified CLIENT -> STRUCTURAL.** It described TAKIX's
  blank regulatory cell as "withheld pending a definition the client is
  deciding". She decided; the ruling did not rescue the cell, because TAKIX
  reports 0.00 in every borrowing field and its own disclosure holds no
  regulatory figure to extract. The CLIENT bucket is now empty.

## KREF leverage perimeter (CIO ruling, Window 3)

- **Ruling: non-recourse securitisation out, repo in.** Implemented per-filer
  rather than as a config switch, and the reason is worth recording: the excluded
  balance is `kref:CollateralizedLoanObligationsNet`, a *company-extension* tag.
  The SEC company-facts API serves only us-gaap, dei and srt, so the number is
  invisible to the XBRL adapter and exists only in the 10-K's own inline XBRL.
  That is what made the perimeter real extraction work rather than a definition
  change -- the same distinction we drew for weighted average spread.
- **Effect is material, in both directions.** KREF moves from 2.45x to 2.98x
  regulatory and from 4.47x to 3.45x economic. The unadjusted economic figure
  was carrying $1.2bn of debt with no recourse to KREF, which is exactly the
  overstatement the CIO's perimeter exists to remove.
- **ASSUMPTION MADE AND STATED, not a blocking question: KREF's $632m secured
  term loan is included on both rows.** The CIO ruled on securitisation and repo
  and said nothing about the term loan. It is included on the grounds that it is
  plain recourse corporate debt and excluding it would need a reason nobody has
  given. That is our reasoning, not his ruling. It belongs in the next batch to
  the client alongside the weighted-average-spread definition and the house Word
  template. It did not block anything and no cell waited on it.
- **Document selection bug found en route, and it generalises.** Narrative
  document selection picks by *filing* date, which is right for terms documents
  -- a prospectus states the fee in force from when it is filed -- but wrong for
  a point-in-time measurement. It silently selected KREF's 2024 balance sheet for
  a Q4 2025 anchor, because the 2025-12-31 10-K is filed in early 2026. The
  figure blanked as stale rather than rendering wrong, which is the good failure
  mode, but the rule is now explicit: **balance-sheet figures are eligible on the
  period they cover, whenever filed** -- decision D applied to measurements
  rather than terms. Checked `sources/highlights.py` against the same bug: it
  selects on `report_date <= anchor`, so it is clean.

- **The board table was not deterministic, and the moving part was a basis
  label.** `max(set(values), key=values.count)` picked each row's reference
  basis and each row's reference comparability key. Set iteration order over
  strings varies between processes under hash randomisation, so a two-way tie
  resolved differently run to run: the basis annotation jumped between TAKIX and
  GBDC on the trailing-return rows with no data change behind it, and in
  `comparison.py` the same call decided which peers were excluded from the
  medians. Replaced both with `cells.modal`, which counts in a dict and breaks
  ties by first appearance -- funds are iterated in configuration order, so the
  earliest-listed fund's basis becomes the reference.
  - Pinned by `tests/test_determinism.py`, which runs subprocesses under
    different `PYTHONHASHSEED` values. An in-process assertion would have passed
    against the broken code: one interpreter has one hash seed, so a set
    iterates consistently for the life of a run and only differs between runs.
  - Verified end to end: four pipeline runs at seeds 0/1/42/7777 produce
    byte-identical `benchmark_table.md` and `apex_vs_peers.md`.
  - Pre-existing, not caused by the leverage split. Worth saying plainly to the
    client: the README promised reproducible runs and did not deliver them, and
    a basis marker that moves on its own is indistinguishable in a diff from a
    number that moved -- in the one metric class that put this engagement here.
