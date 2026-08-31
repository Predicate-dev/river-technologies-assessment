# Technical approach — competitor benchmarking pipeline

**Audience:** Apex Ridge technical counterpart
**Status:** prototype against live SEC EDGAR · 144 tests · 30 of 40 competitor cells populate at the Q4 2025 anchor

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
                       render ─► board table · coverage · comparison · NAV trend · audit trail
```

`edgar.py` is rate-limited to 8 req/s (SEC's ceiling is 10), sends a descriptive
User-Agent, and caches every response to disk.

Adapters emit **candidates** — a value plus its evidence — never bare numbers.
The split is forced by the filers, not chosen:

| Adapter | Funds | Mechanism |
| --- | --- | --- |
| `xbrl.py`, `xbrl_metrics.py` | GBDC, KREF | XBRL company facts (189 / 283 `us-gaap` tags) |
| `nport.py` | CCLFX, TAKIX | N-PORT XML: net assets, borrowings, monthly returns |
| `highlights.py` | CCLFX, TAKIX | N-CSR/N-CSRS financial highlights — the only class-level source |
| `narrative.py` | all four | Fee tables, anchored prose patterns, optional LLM |
| `discovery.py` | any filer | EDGAR search and evidence-based classification |

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
key and compliance does not block the prototype.

**Every metric carries a `basis`, not just a value.** Forced by KREF, whose
management fee is struck on stockholders' equity and whose "NAV per share" is
GAAP book value. That gap cannot be a footnote bolted on at render time. It has
paid for itself repeatedly since: the leverage question and the unconfirmed basis
of the Apex column are both render-time switches *because* basis is in the schema.

**Multiple candidates per metric.** Leverage is built three ways; the third is a
consistency probe against the second. Disagreement means the filer's
balance-sheet tagging is inconsistent and every derived value should be
downgraded.

**Blanks are typed** and a bare blank raises rather than renders.

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

- **tier** — the mechanism: typed XBRL fact (0.95) through to a model reading a
  footnote (0.55). Scores the *mechanism*, not the filer.
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
expense table and prose); internal consistency; and bound-checking against
TAKIX's seven unlabelled class series.

**Resolution is by weight of evidence, not tier.** Same-basis candidates cluster
by agreement; the cluster with most *independent* extractions wins, then fewest
flags, then tier, then recency. Independence is checked on (mechanism,
accession, transform), so one table matched through two anchors counts once.

Below 0.40 the value is withheld and the blank states why.

## 4. Where sources disagreed

**A correctly-tagged number can still be the wrong one.** GBDC's XBRL reports
its management fee as 0.021% — valid, from a 424B2 notes prospectus rather than
the fund's fee table. Highest tier, wrong number, suppressed at 0.13. This is
why source tier alone cannot be the confidence model.

**Superseded rates sit beside current ones.** GBDC's 10-K says "reduced from
1.375% to 1.0%"; TAKIX's prospectus quotes a fee retired in 2020. Both figures
are emitted and resolved by effective date, and a superseded rate never renders
bare — your own instruction, and correct, since GBDC's superseded 20% and KREF's
live 20% are the same number meaning opposite things.

**Adjacent figures get confused.** TAKIX's catch-up rate (1.765%) sits in the
same sentence as its hurdle (1.500%). KREF's fee is quoted quarterly on adjusted
equity — 0.375%, which is 1.50% a year against peers quoting ~1.0%.

**A quarter BDCs never tag separately** understated GBDC's 1Y return by 265bp
until reconstructed. **CCLFX charges no incentive fee**, established from the
absence of that row in a complete fee table, so its hurdle is inapplicable
rather than missing.

**TAKIX reports zero borrowings against $2.2bn of liabilities.** Its regulatory
cell blanks — zero borrowings against material liabilities measures nothing.
Per your CIO's ruling leverage now reports as two rows, so TAKIX reads blank on
regulatory and 0.45x on economic, with neither standing in for the other.

**Your own leverage basis is the one question that survived Window 3.** Your
confirmation covered share class and fee treatment, which unblocked returns,
fees and yield. It did not say which basis your single `leverage_ratio_dte`
column uses, and the peers now report two differing by more than a factor of two
— CCLFX reads 0.32x regulatory against 0.79x economic. Your leverage figure
renders; its delta is withheld. One flag reverses that.

## 4a. The scope additions

**Custom metrics** are declarations, not code: label, unit, direction, plausible
range, and where the value is found. The original nine are declared the same
way, so a custom metric gets identical provenance and confidence rather than a
weaker side channel. Bad definitions fail the run. Simple ones need no regex —
name the phrase, say what to take, bound the distance. One trap worth knowing:
GBDC states non-accruals as "0.6% and 0.3%, respectively" (cost, then fair
value), so the definition must pin the basis. We ship both as separate metrics.

**Fund discovery** searches EDGAR full-text — the only SEC index that sees
non-traded interval funds; the ticker files omit them entirely — and adds by
CIK. It never auto-resolves a search ("Golub Capital BDC" returns three CIKs,
none of them right) and refuses any filer it cannot classify confidently, since
misclassification runs the wrong extractors and yields wrong numbers rather than
blanks. Fiscal year end comes from the filer's own annual filings, not EDGAR's
registration metadata, which records 12-31 for CCLFX against an N-CSR covering a
year ended 31 March. Peer sets persist as readable JSON.

**Word output** carries the table, coverage, conflicts, comparison and a
provenance appendix. Blank cells carry their reasons there too — the document
that leaves the building must not look more complete than the evidence.

## 5. Limitations

- **26 of 36 cells populate**, classified in `output/coverage_breakdown.md` by
  who owns each gap. **Nothing remains that further extraction would close**:
  4 are cadence-limited, 1 is blocked on your leverage definition, 5 are
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
| **Filers change wording; prose patterns stop matching.** Most likely failure. | A miss produces a blank with a reason, never a wrong number — which is why it goes unnoticed. `--compare-to` diffs a run against the previous quarter's coverage, names what stopped populating and why, and exits non-zero so a scheduled run gates on it. |
| **A filer re-tags XBRL or tags the wrong document.** Already observed. | Cross-mechanism agreement plus plausibility ranges; flagged and suppressed, not trusted on tier. |
| **Non-determinism in rendering.** Found late, and worth naming: the layer choosing each row's reference basis broke ties with `max(set(...))`, whose iteration order varies between processes. Two clones produced different board tables from identical data — a basis label moving on its own, which in a diff is indistinguishable from a number moving, in the metric class that caused your board incident. | Ties now break by first appearance in configuration order. Tested in subprocesses across five hash seeds; an in-process test would have passed against the broken code. Found by running the pipeline twice and comparing, which no test had done. |
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
compliance. **Confirmed in Window 3:** the CIO's leverage ruling (both bases; KREF
non-recourse securitisation out, repo in; two display rows), your column's share
class and fee treatment, the fee-clock label, and custom-metric authorship.
**Still open:** which leverage basis your own ratio uses — the only remaining
suppression, and one nobody could have asked before leverage split in two.
