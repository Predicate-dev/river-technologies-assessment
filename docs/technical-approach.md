# Technical approach

**For:** Apex Ridge technical counterpart
**Status:** live against SEC EDGAR · 144 tests · 30 of 40 competitor cells populate at the Q4 2025 anchor

---

## 1. Architecture

```
                SEC EDGAR   live · rate-limited · cached by URL
                     │
  ┌──────────────┬───┴──────────┬──────────────────┐
  ▼              ▼              ▼                  ▼
XBRL facts   N-PORT XML   N-CSR highlights   Narrative HTML
GBDC · KREF  CCLFX·TAKIX   CCLFX · TAKIX        all four
tagged        fund-level    class-level,     fee tables and
10-K/10-Q     monthly       semi-annual      prose patterns
  └──────────────┴──────────────┴──────────────────┘
                     │   four sources because four filers
                     ▼
   CANDIDATES    value + basis + provenance + flags
                 many per metric · never a bare number
                     ▼
   ELIGIBILITY   period ends on or before the reporting quarter
                     ▼
   RECONCILE     group by basis · cluster by agreement
                 score = tier × agreement × freshness × penalties
                     │
           ┌─────────┴─────────┐
           ▼                   ▼
    RESOLVED VALUE        SUPPRESSION
    + confidence          + typed reason
    + citation            a bare blank raises
           └─────────┬─────────┘
                     ▼
  board table · coverage · comparison · NAV trend · audit · Word
```

The four-way split is forced, not chosen: the interval funds file no 10-K and
have eleven usable `cef:` tags between them, so their fee terms exist only in
prose and class-level figures only in the annual and semi-annual reports.

## 2. Key decisions

- **Every metric carries a `basis`, not just a value.** Forced by KREF, whose fee
  is struck on stockholders' equity and whose "NAV per share" is GAAP book value.
  That gap cannot be a footnote added at render time — and it is why the leverage
  split and your column's unconfirmed basis are render-time switches, not rebuilds.
- **Metrics are declarations, not code.** Label, unit, direction, plausible range,
  and where the value is found. Your PMs' quarterly additions are JSON entries.
- **Blanks are typed**, and a bare blank raises rather than renders.
- **Structured-first, LLM last.** The tier is built but unused — deterministic
  extraction reaches every fee — so the pipeline runs with no API key. Its guard,
  if enabled: the model must return a verbatim quote, checked to be literally
  present in the source. An unverifiable answer is discarded, not discounted.

## 3. Validation strategy: establishing confidence without an answer key

**There is no answer key, and we could not manufacture one.** The manual process
we replaced was your only source for these numbers, so there is nothing to check
the output against. We asked for a prior-quarter pack to reconcile against and
were told — correctly — that live fund data cannot leave the firm without a
compliance sign-off that has not happened. **Nothing here has been checked
against an external reference.** This document says so rather than letting
confidence grades imply otherwise.

Confidence therefore cannot be an accuracy measurement. What it can be is an
auditable statement of how much *evidence* stands behind a value, built only from
things observable about the extraction itself:

```
score = tier × agreement × freshness × ∏(named penalties)
```

**Tier** scores how the number was obtained — a typed XBRL fact (0.95) through
an N-PORT field (0.92), a derived calculation (0.75), a parsed table (0.72), a
prose pattern (0.66), to a model reading a footnote (0.55). It scores the
*mechanism*, not the filer's judgement: §4's first case is a correctly tagged
number that is wrong for our purpose. **Agreement** is the only factor that can
raise a score and the closest thing to ground truth available without a key —
corroborated ×1.10, single source ×0.90, conflicting ×0.70. **Freshness** ages
the period against the reporting quarter. **Penalties** are named and published;
an unrecognised flag takes a default, so a new one cannot silently pass at full
confidence.

Every input is recorded on the value, so a reviewer audits the score rather than
trusting it. **Nothing anywhere asks a model how confident it is.**

### The four reconciliations we run

1. **Cross-mechanism** — the same quantity by two independent routes. GBDC's NAV
   is 14.84 from a tagged XBRL fact and 14.8420 from equity ÷ shares outstanding:
   different tags, different arithmetic, agreeing to 0.02%. This is the only cell
   that scores High, and that is the point — High means convergence, not
   confidence in the source.
2. **Cross-document** — the same figure in two filings or two places in one.
   CCLFX's 1.00% management fee appears in the prospectus expense table *and* in
   prose ("at an annual rate of 1.00%"). Two mechanisms, one answer.
3. **Internal consistency** — a probe with no purpose but to disagree. Leverage
   is computed as liabilities ÷ equity *and* as (assets − equity) ÷ equity from
   an independent pair of tags. If those diverge, the filer's balance sheet
   tagging is inconsistent and every derived value for that fund is downgraded.
4. **Bound-checking** — TAKIX publishes seven unlabelled share-class return
   series; their spread (1Y: 3.19%–4.07%) bounds any narrative-sourced figure for
   that fund. Held internally and in the appendix, never rendered as a range.

**Resolution is by weight of evidence, not source tier.** Same-basis candidates
are clustered by agreement; the cluster with the most *independent* extractions
wins, then fewest flags, then tier, then recency. Independence is checked on
(mechanism, accession, transform), so one table matched through two anchor
phrases counts once and cannot vote itself into the deck. Below 0.40 the value is
withheld and the blank states why — a blank is defensible to a board; a bad
number is not.

## 4. Where sources disagreed, why, and what we chose

Filings disagree for a small number of recurring reasons. Naming the cause is
what makes each resolution defensible rather than ad hoc.

**Right number, wrong document.** GBDC's XBRL reports its management fee as
0.021%. The tag is valid; the filer's agent tagged the fee table of a 424B2 notes
prospectus, not the fund's own. *Chose:* 1.0% from the 10-K. The XBRL value is
emitted, flagged for document context and implausibility, and suppressed at 0.13
— the highest-tier source losing to a lower-tier one on evidence.

**The filing narrates its own history.** GBDC's 10-K says the fee was "reduced
from 1.375% to 1.0%" and rates "from 20.0% to 15.0%"; TAKIX's prospectus quotes a
fee retired in 2020. Both figures are real and both are in the current document.
*Chose:* the rate in force at the reporting quarter, by effective date read from
the same sentence. A superseded rate never renders bare — GBDC's superseded 20%
and KREF's live 20% are the same number meaning opposite things.

**Related figures share a sentence.** TAKIX's catch-up rate (1.765%) sits beside
its hurdle (1.500%) because they are defined together; its hurdle is also stated
both per-quarter and annualized. *Chose:* context measured around the captured
number rather than the match, which is what stops an already-annual 6.00% being
quadrupled to 24%.

**Same concept, different base.** KREF's fee is quoted quarterly on adjusted
equity — 0.375%, which is 1.50% a year, against peers quoting ~1.0% on net or
managed assets. *Chose:* annualize, mark the base, and exclude it from the peer
median rather than average incomparable bases.

**The figure is structurally absent.** BDCs never tag fiscal Q4 distributions
separately; the 10-K reports the year. Filtering to quarterly facts silently
dropped it and understated GBDC's 1Y return by 265bp. *Chose:* reconstruct by
differencing the annual total against the tagged quarters.

**The disclosure does not measure the concept.** TAKIX reports 0.00 in every
N-PORT borrowing field while carrying $2.2bn of liabilities on $4.47bn of net
assets. A regulatory leverage ratio is computable and means nothing. *Chose:*
blank, with the reason — and specifically *not* the economic figure, which would
have answered a definitional question that was the client's to settle.

**We could not establish the basis.** Your own `leverage_ratio_dte` column is
unlabelled, and the peers' two bases differ by more than a factor of two. *Chose:*
render your figure, withhold its delta.

## 5. Limitations

- **30 of 40 cells populate**, attributed in `output/coverage_breakdown.md`.
  Nothing remains that further extraction would close: 4 cadence-limited, 6
  structural.
- **CCLFX's cadence gap is live** — its March year-end puts the annual report 275
  days behind a Q4 2025 anchor, so four cells blank on your six-month rule rather
  than any failure of ours. This recurs annually.
- **The NAV trend is semi-annual**, per your ruling; dates differ by fiscal
  calendar and are labelled per point rather than interpolated.
- **Fund discovery cannot reach every filer** — SEC's ticker files omit
  non-traded interval funds, and an entity type we do not handle has no adapter.

## 6. Production risks

| Risk | Mitigation |
| --- | --- |
| **Filers change wording; patterns stop matching.** Most likely failure, and silent by design. | A miss blanks with a reason, never a wrong number. `--compare-to` diffs against last quarter's coverage, names what stopped and why, exits non-zero so a scheduled run gates on it. |
| **A filer re-tags XBRL or tags the wrong document.** Already observed (§4). | Cross-mechanism agreement plus plausibility ranges. Flagged and suppressed, not trusted on tier. |
| **Non-determinism in rendering.** Two clones produced different board tables from identical data — a basis label moving on its own, indistinguishable in a diff from a number moving. | Ties break by first appearance, tested across five hash seeds in subprocesses. An in-process test would have passed against the broken code. |
| **Scope expands beyond EDGAR.** Likely. | Adopt web sources only as a distinct, lower tier: a filing has an accession number and an immutable version; a web page has neither. |
| **Provenance rots.** | Every value carries accession, form, period, URL, locator and a verbatim excerpt. All resolve today. |

---

**Whose decisions these are.** Confirmed by the client: blank-over-guess; the
six-month staleness line; the reporting-quarter anchor; institutional share class
for the interval funds; basis at the cell; the amendment-based fee clock;
semi-annual NAV; two leverage rows; the KREF perimeter. **Consultant defaults,
unratified:** confidence weightings, the 0.40 floor, the N-PORT depth cap, and
the inclusion of KREF's $632m secured term loan as recourse debt.
