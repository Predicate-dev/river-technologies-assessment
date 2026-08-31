# Technical approach — competitor benchmarking pipeline

**Audience:** Apex Ridge technical counterpart
**Status:** prototype against live SEC EDGAR · 63 tests · 27 of 36 competitor cells populate at the Q4 2025 anchor

---

## 1. Architecture

```
EDGAR (live) ─► source adapters ─► candidates ─► eligibility filter
                                                       │
                     reconciliation ◄─────────────────┘
                           │
             ┌─────────────┴─────────────┐
       resolved value              suppression
       + confidence + provenance   + typed reason
                           │
                       render ─► board table · coverage · NAV trend · audit trail
```

`edgar.py` is rate-limited to 8 req/s (SEC's ceiling is 10), sends a descriptive
User-Agent, and caches every response to disk. Caching makes runs deterministic
and means a demo cannot be broken by a network hiccup.

Adapters emit **candidates** — a value plus its evidence — never bare numbers.
The split is forced by the filers, not chosen:

| Adapter | Funds | Mechanism |
| --- | --- | --- |
| `xbrl.py`, `xbrl_metrics.py` | GBDC, KREF | XBRL company facts (189 / 283 `us-gaap` tags) |
| `nport.py` | CCLFX, TAKIX | N-PORT XML: net assets, borrowings, monthly returns |
| `highlights.py` | CCLFX, TAKIX | N-CSR/N-CSRS financial highlights — the only class-level source |
| `narrative.py` | all four | Fee tables, anchored prose patterns, optional LLM |

GBDC and KREF file 10-K/10-Q with rich XBRL. The interval funds file no 10-K and
have eleven usable `cef:` tags between them, so their fee terms exist only in
prose and their class-level figures only in the annual and semi-annual reports.

`core/periods.py` rebuilds a non-overlapping distribution ledger by differencing
fiscal-year-to-date cumulatives; `core/temporal.py` owns the anchor, eligibility
and staleness; `core/reconcile.py` is the only path that can blank a value;
`core/confidence.py` scores.

## 2. Key decisions

**Structured-first, LLM last.** The LLM tier is built but unused — the
deterministic tiers cover every fee extracted — so the pipeline runs with no API
key and the compliance question does not block the prototype.

**Every metric carries a `basis`, not just a value.** Forced by KREF, whose
management fee is struck on stockholders' equity and whose "NAV per share" is
GAAP book value. That gap cannot be a footnote bolted on at render time. It has
paid for itself repeatedly since: the leverage question and the unconfirmed basis
of the Apex column are both render-time switches *because* basis is in the schema.

**Multiple candidates per metric, deliberately.** Leverage is built three ways;
the third exists purely as a consistency probe against the second. Disagreement
between them means the filer's balance-sheet tagging is inconsistent and every
derived value for that fund should be downgraded.

**Blanks are typed** — `NOT_APPLICABLE`, `NOT_YET_FILED`, `STALE`,
`BASIS_DISQUALIFIED`, `SUPPRESSED`. A bare blank raises rather than renders.

## 3. Validation and the confidence model

**We asked for external validation and could not have it.** A prior-quarter
manual pack to reconcile against was declined on compliance grounds. Nothing here
has been checked against an external reference. Validation rests entirely on
internal cross-source agreement and on reasoning we can show, and this document
would rather say so than let confidence grades imply otherwise.

So the score is built only from what we can observe about the extraction:

```
score = tier × agreement × freshness × ∏(named penalties)
```

- **tier** — the mechanism: typed XBRL fact (0.95), N-PORT schema field (0.92),
  derived calculation (0.75), parsed table (0.72), prose pattern (0.66), model
  reading a footnote (0.55). This scores the *mechanism*, not the filer.
- **agreement** — the only factor that can raise a score, and the closest thing
  to ground truth available. Corroborated ×1.10, single source ×0.90,
  conflicting ×0.70.
- **freshness** — age of the period against the anchor.
- **penalties** — named, published multipliers. An unrecognised flag takes a
  default discount, so a new flag can never silently pass at full confidence.

Every input is recorded on the value, so a reviewer audits the score rather than
trusting it. **Nothing asks a model how confident it is.**

Reconciliations that run: cross-mechanism (GBDC NAV — XBRL 14.84 vs
equity÷shares, agreeing to 0.02%); cross-document (CCLFX's fee in both the
expense table and prose); internal consistency (liabilities÷equity vs
(assets−equity)÷equity); and bound-checking (TAKIX's seven unlabelled class
series bound any narrative figure — retained internally, never rendered).

**Resolution is by weight of evidence, not tier.** Same-basis candidates cluster
by agreement; the cluster with most *independent* extractions wins, then fewest
flags, then tier, then recency. Independence is checked on (mechanism,
accession, transform), so one table matched through two anchors counts once.

Below 0.40 the value is withheld and the blank states why.

## 4. Where sources disagreed

**GBDC's XBRL reports its management fee as 0.021%.** Valid XBRL, correctly
tagged — from a 424B2 notes prospectus, not the fund's fee table. Highest tier,
wrong number, suppressed at 0.13. *This is why tier alone cannot be the model.*

**GBDC's 10-K states old and current rates in one sentence** — "reduced from
1.375% to 1.0%", "from 20.0% to 15.0%". Both are emitted; reconciliation resolves
by effective date and logs the conflict. This is the exact misread that reached
your board. Note both incentive tiers are 15.0%; 20% is the prior rate, not a
second tier.

**TAKIX's prospectus quotes a management fee retired in 2020**, paragraphs from
the current one. Same hazard, different grammar.

**A distribution quarter BDCs never tag separately** understated GBDC's 1Y return
by 265bp until reconstructed.

**KREF's management fee is quoted quarterly** on adjusted equity — 0.375%, which
is 1.50% a year against peers quoting ~1.0%. Annualized and basis-marked.

**CCLFX charges no incentive fee**, established from the absence of an incentive
row in a complete fee table rather than from anyone's recollection. Its hurdle is
therefore reported as inapplicable, not as a gap — a fund with no carry has no
hurdle, and calling that an extraction failure would imply a figure exists.

**TAKIX states its incentive rate only inside the worked fee examples** ("there
is a 15% incentive fee on pre-incentive fee net investment income"), and its
catch-up rate sits adjacent to its hurdle in the same sentence. Both are
extracted and distinguished; reading the catch-up as the hurdle was a live
failure until it was.

**TAKIX reports zero borrowings against $2.2bn of liabilities.** Computable,
withheld: falling through to the total-liabilities basis would silently answer
the regulatory-vs-economic question now with your CIO.

## 5. Limitations

- **27 of 36 cells populate**, classified in `output/coverage_breakdown.md` by
  who owns each gap. **Nothing remains that further extraction would close**:
  3 are cadence-limited, 1 is blocked on your leverage definition, 5 are
  structural. Every metric reachable from EDGAR for these filers is extracted.
- **That is contingent on EDGAR being the whole scope.** Analysts also source
  from fund websites and IR pages. If cells in the manual pack came from there,
  they are outside this system's reach by design, not by omission — and the
  recommended treatment if they come into scope is in §6.
- **CCLFX's cadence gap is live.** Its March year-end puts the annual report 275
  days behind a Q4 2025 anchor, past the six-month line, so three cells blank on
  your rule rather than any failure of ours. Recurs annually.
- **The NAV trend is semi-annual.** Class-level NAV exists only in the annual and
  semi-annual reports. Dates still differ by fiscal calendar and are labelled per
  point; interpolating to a shared grid would invent observations.
- **GBDC and KREF publish NAV quarterly, not monthly.** No fund here publishes a
  monthly per-share NAV.

## 6. Production risks

| Risk | Mitigation |
| --- | --- |
| **Filers change wording; prose patterns stop matching.** Most likely failure. | A miss produces a blank with a reason, never a wrong number. Add a per-metric alert: a value that populated last quarter and stops is the signal. |
| **A filer re-tags XBRL or tags the wrong document.** Already observed. | Cross-mechanism agreement plus plausibility ranges; flagged and suppressed, not trusted on tier. |
| **Silent arithmetic drift.** | Day-count annualization with window tolerances; a window that does not match its label is suppressed, not rounded. Ledger arithmetic is unit-tested against real failure modes. |
| **Source scope expands beyond EDGAR.** Likely. | Adopt web sources only as a distinct, visibly lower tier. A filing has an accession number, an immutable version and a retrievable audit trail; a web page has none. Never blend silently — that would undermine the one property making this defensible. It is a new tier value and a penalty, not a redesign. |
| **Provenance rots.** | Every value carries accession, form, period, URL, in-document locator and a verbatim excerpt. |

## 7. The LLM tier

Built, unused, pending compliance. Its guard is what makes model extraction
defensible: the model must return a value **and** a verbatim quote, and the quote
is checked to be literally present in the source. An answer whose quote cannot be
found is **discarded, not downgraded** — no confidence discount substitutes for
dropping a probable fabrication. Two passes run; disagreement flags the value.

---

**Whose decisions these are.** Confirmed by Lara: blank-over-guess; the six-month
staleness line; the anchor as the reporting quarter; institutional share class
for the interval funds; basis rendered at the cell; the amendment-based fee clock;
semi-annual NAV footing; KREF retained on a row-level mapping. Consultant
defaults, unratified: confidence weightings, the 0.40 floor, gross-debt leverage
as primary, run-rate as the primary yield basis, the N-PORT depth cap. Open with
your CIO: the leverage definition, peer-list criteria, the CCLFX fallback, LLM
compliance. **Unconfirmed and blocking:** the basis of Apex Ridge's own column —
share class and fee treatment — so its deltas are suppressed.
