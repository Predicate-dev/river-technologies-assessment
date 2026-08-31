# Technical approach — competitor benchmarking pipeline

**Audience:** Apex Ridge technical counterpart.
**Status:** prototype, built against live SEC EDGAR. 36 tests passing.
**Reporting anchor:** Q4 2025 (period end 2025-12-31).

---

## 1. What the system does

Four competitor funds, nine metrics, one board-format table plus an audit trail.
Every rendered value carries where it came from and how much evidence stands
behind it; every blank carries why it is blank.

The design constraint that shaped everything: **there is no answer key.** The
manual process being replaced was your only source for these numbers, so the
system cannot be validated against a known-correct output. Confidence therefore
cannot be an accuracy measurement. It has to be an auditable statement of the
evidence behind each value — which is what section 4 describes.

## 2. Architecture and data flow

```
EDGAR (live)  ──►  source adapters  ──►  candidates  ──►  eligibility filter
                                                              │
                        reconciliation ◄─────────────────────┘
                              │
              ┌───────────────┴───────────────┐
        resolved value                  suppression
        + confidence + provenance       + typed reason
                              │
                          render ──► board table + audit appendix
```

**`edgar.py`** — rate-limited (8 req/s against SEC's 10/s ceiling), descriptive
User-Agent, disk-cached by URL. Caching is not an optimisation: it makes runs
deterministic and means a live demo cannot be broken by a network hiccup or a
rate-limit trip.

**Source adapters** each emit *candidates* — a value plus its evidence — never a
bare number:

| Adapter | Funds | Mechanism |
| --- | --- | --- |
| `sources/xbrl.py`, `xbrl_metrics.py` | GBDC, KREF | XBRL company facts (189 / 283 `us-gaap` tags) |
| `sources/nport.py` | CCLFX, TAKIX | N-PORT XML — net assets, borrowings, monthly returns |
| `sources/narrative.py` | all four | Fee tables, anchored prose patterns, optional LLM |

The split is forced by the filers, not chosen. GBDC and KREF file 10-K/10-Q with
rich XBRL. CCLFX and TAKIX are interval funds: no 10-K, and between them only
eleven `cef:` XBRL tags, all senior-securities stress figures. For those two,
N-PORT is the only machine-readable source and fee terms exist only in prose.

**`core/periods.py`** reconstructs a non-overlapping distribution ledger by
differencing fiscal-year-to-date cumulatives. **`core/temporal.py`** owns the
reporting anchor and eligibility. **`core/reconcile.py`** resolves candidates and
is the only path that can blank a value. **`core/confidence.py`** scores.

## 3. Key decisions

**Structured-first, LLM last.** XBRL and N-PORT before any model. The LLM tier
is optional and currently unused — the deterministic tiers cover every fee the
system extracts, so `git clone && run` works with no API key. This also means the
compliance answer on third-party model use does not block the prototype.

**Every metric carries a `basis`, not just a value.** Forced by KREF: its
management fee is struck on stockholders' equity, the interval funds' on managed
or net assets; its "NAV per share" is GAAP book value, not an administrator-struck
NAV. That gap cannot be expressed as a footnote bolted on at render time. It has
since paid for itself twice more — the leverage regulatory/economic question and
the unconfirmed basis of the Apex column are both render-time switches rather
than rebuilds *because* basis is in the schema.

**Multiple candidates per metric, deliberately.** Leverage is emitted on three
constructions. The third — `(assets − equity) / equity` — exists purely as an
internal-consistency probe against the second; if they disagree, the filer's
balance-sheet tagging is inconsistent and every derived value for that fund
should be downgraded.

**Blanks are typed.** `NOT_APPLICABLE`, `NOT_YET_FILED`, `STALE`,
`BASIS_DISQUALIFIED`, `SUPPRESSED`. A bare blank is unrepresentable in the
output — the render unit raises rather than emit one.

## 4. Validation strategy and the confidence model

No answer key means no accuracy measurement. What we can observe is the
extraction itself, so the score is built only from that:

```
score = tier × agreement × freshness × ∏(named penalties)
```

- **tier** — how the number was obtained: a typed XBRL fact (0.95), an N-PORT
  schema field (0.92), a derived calculation (0.75), a parsed table cell (0.72),
  an anchored prose pattern (0.66), a model reading a footnote (0.55). This
  scores the *mechanism*, not the filer's judgment. Section 5 shows why that
  distinction matters.
- **agreement** — the only factor that can *raise* a score, and the closest thing
  to ground truth available. Independently-constructed values for the same thing
  on the same basis either converge or they do not. Corroborated ×1.10, single
  source ×0.90, conflicting ×0.70.
- **freshness** — age of the underlying period against the anchor.
- **penalties** — named, published multipliers per observed problem. An
  unrecognised flag takes a default discount, so a new flag can never silently
  pass at full confidence.

Every input is recorded on the resolved value, so a reviewer audits the score
rather than trusting it. **Nothing anywhere asks a model how confident it is.**

Four reconciliations run in practice:

1. **Cross-mechanism.** GBDC NAV/share: XBRL reports 14.25; equity ÷ shares
   outstanding gives 14.2476. Independent constructions agreeing to 0.02% —
   the only value in the current run scoring High.
2. **Cross-document.** CCLFX's management fee appears in the prospectus expense
   table *and* in prose ("at an annual rate of 1.00%"). Two mechanisms, one
   answer.
3. **Internal consistency.** Total liabilities ÷ equity against
   (assets − equity) ÷ equity, per filer, per period.
4. **Bound-checking.** TAKIX publishes seven unlabelled share-class return
   series; their spread (1Y: 3.19%–4.07%) bounds any narrative-sourced
   institutional figure. Retained internally and in the appendix — never
   rendered as a range, per your ruling.

**Resolution is by weight of evidence, not source tier.** Same-basis candidates
are clustered by agreement; the cluster with the most *independent* extractions
wins, then fewest flags, then tier, then recency. Independence is checked on
(mechanism, accession, transform) so the same table matched through two anchor
phrases counts once and cannot vote itself into the deck.

**Below 0.40, the value is withheld and the blank states why.** This follows
directly from the asymmetric-loss rule: a false-confident value costs more than
a gap.

## 5. Where sources disagreed, and what we did

**GBDC's XBRL says its management fee is 0.0213%.** Valid XBRL, correctly tagged
— from a 424B2 notes prospectus rather than the fund's own fee table. Highest
source tier, wrong number. It is emitted as a candidate, flagged for document
context and implausibility, and suppressed at 0.13 confidence. The true rate,
1.0%, comes from the 10-K. **This is the concrete proof that source tier alone
cannot be the confidence model.**

**GBDC's 10-K states both the old and current rates in one sentence** — "the
base management fee rate was reduced from 1.375% to 1.0%", and "incentive fee
rates were reduced from 20.0% to 15.0%". Both figures are emitted as candidates
on the same basis; reconciliation resolves to the current rate and logs the
conflict with its rationale ("kept 1.0: agreed on by 3 independent extractions
vs 1.375 by 1"). This is the exact shape of the misread that reached your board
last year, and it is now a named, tested case rather than a matter of analyst
attention.

**A missing distribution quarter understated GBDC's 1-year return by 265bp.**
BDCs never tag fiscal Q4 as a standalone period — it exists only inside the 10-K
annual total. Filtering to 90-day facts silently drops it (2.05%); differencing
the cumulative recovers it (4.71%). This is `core/periods.py`, and it is the
most heavily tested code in the repository because it is the place a silent
arithmetic error would reach a board deck.

**TAKIX reports zero borrowings while carrying $2.2bn of liabilities on $4.47bn
of net assets.** Gross-debt leverage computes to 0.00 — arithmetically correct,
informationally empty. Rather than render `0.00x, Low`, the cell is
*disqualified*: the elected construction did not measure the metric. Critically,
it does **not** fall through to the total-liabilities basis (0.4939), because
doing so would silently answer the regulatory-vs-economic question currently
with your CIO by picking the economic reading. Both readings are named in the
appendix.

**GBDC's 5-year return is blank.** Its NAV history is quarterly only back to
2021-09-30 — 4.75 years. A 4.75-year window is not a 5-year return, so the cell
states the reason and the coverage it *could* have supported.

**KREF's distribution yield differs by basis.** A Q2 2026 cut from $0.25 to
$0.10 puts run-rate at 2.52% and trailing-twelve-month at 5.34%. Both render, per
your ruling that a cut of that size belongs at the cell rather than in a footnote.

## 6. Known limitations

- **Extractors are not yet anchor-aware.** Eligibility filtering is wired, but
  the XBRL and N-PORT adapters still select the latest observation rather than
  the one nearest the anchor, so filtering currently blanks more than it should.
  This is a known in-flight fix, not a design limit.
- **N-PORT depth is capped at 8 filings** (~8MB each). The 3Y/5Y interval-fund
  windows are therefore limited by *our* download cap, not by data availability
  — the filings exist at EDGAR today. The appendix states this explicitly so the
  limit is never mistaken for a filer gap.
- **Institutional share-class returns are not yet extracted.** Class-level data
  exists only at semi-annual/annual cadence in N-CSR financial-highlights tables.
  Confirmed reachable deterministically; not yet built.
- **CCLFX has a structural cadence gap.** Its March fiscal year-end means that
  for part of each year no institutional-class figure is under six months old.
  Not a bug — a consequence of your six-month rule meeting the filer's calendar.
- **No cross-filer identity resolution.** The fund registry is hand-curated and
  verified against EDGAR. Adding a fund within a handled entity type is a config
  entry; a new entity type needs a new adapter.

## 7. Production risks and mitigations

| Risk | Mitigation |
| --- | --- |
| **Filers change wording; prose patterns silently stop matching.** Highest-likelihood failure. | Patterns are anchored and per-metric, so a miss produces a blank with a reason, never a wrong number. Recommend a per-metric coverage alert: if a value extracted last quarter is absent this quarter, that is a signal, not a gap. |
| **A filer re-tags XBRL, or tags a fee table from the wrong document.** Already observed. | Cross-mechanism agreement plus plausibility ranges; the value is flagged and suppressed rather than trusted on tier. |
| **EDGAR rate-limits or changes URL structure.** | Self-throttled below the published ceiling with backoff; all access is behind one client class. |
| **Silent arithmetic drift in derived metrics.** | Day-count annualization with explicit window tolerances; a window that does not match its label is suppressed, not rounded. Ledger arithmetic is unit-tested against the real failure modes. |
| **Definitional answers arrive after build.** | The `basis` field means definitional questions are render-time switches. Of five open client items, four are config-level; only the leverage definition implies extraction work. |
| **Provenance rots.** A citation must resolve years later for compliance. | Every value carries accession number, form type, period, document URL and an in-document locator (XBRL tag, XPath, or character offset), plus a verbatim excerpt. |

## 8. Provenance in the LLM tier

The LLM tier is built but unused pending your compliance answer. Its guard is
worth stating because it is the mechanism that makes model extraction defensible
at all: the model must return the value **and** a verbatim supporting quote, and
the quote is then checked to be literally present in the source document. An
answer whose quote cannot be found is **discarded, not downgraded** — an
unverifiable extraction is the signature of a fabrication, and no confidence
discount is an adequate substitute for dropping it. Two passes run independently;
disagreement flags the value rather than silently taking one.

---

## Appendix — which decisions are yours and which are ours

Recorded because the distinction matters for anything you inherit.

**Confirmed by Lara (Window 1):** blank-with-stated-reason over a filled cell on
the wrong definition; the six-month staleness line; the anchor running from the
reporting quarter rather than the run date; institutional share class as a hard
requirement for CCLFX/TAKIX; basis divergence rendered at the cell rather than in
a footnote; KREF retained on a row-level mapping, provisionally.

**Consultant defaults, not yet ratified:** the confidence weightings and the 0.40
suppression floor; preferring gross-debt leverage as the primary basis; run-rate
as the primary distribution-yield basis; the N-PORT depth cap; the tier ordering
itself. Each is a single constant and each is documented in `NOTES/decisions.md`.

**Open with your CIO:** the leverage definition (regulatory vs. economic, and
whether KREF's non-recourse securitisation and repo are in scope); the peer-list
selection criteria; whether a labelled fund-level figure is an acceptable
fallback during CCLFX's cadence gap; compliance approval for the LLM tier.

**Unconfirmed and blocking derived comparisons:** the basis of Apex Ridge's own
column. Share class and fee treatment are unknown, so the column renders with
basis `UNCONFIRMED` and peer-minus-Apex deltas are suppressed. A delta between
two numbers of unknown basis is precisely the confidently-wrong number this
system exists to prevent.
