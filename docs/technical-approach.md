# Technical approach

**For:** Apex Ridge technical counterpart
**Status:** live against SEC EDGAR · 144 tests · 30 of 40 competitor cells populate at the Q4 2025 anchor

---

## 1. Architecture

```
EDGAR ─► source adapters ─► candidates ─► eligibility filter ─► reconciliation
                                                                      │
                                          ┌───────────────────────────┘
                                    resolved value              suppression
                                    + confidence + provenance   + typed reason
                                                  │
                                    board table · coverage · comparison · NAV trend · audit trail · Word
```

`edgar.py` throttles to 8 req/s (SEC's ceiling is 10), sends a descriptive
User-Agent and caches by URL. Adapters emit **candidates** — a value plus its
evidence — never bare numbers. The split is forced by the filers:

| Adapter | Funds | Source |
| --- | --- | --- |
| `xbrl.py`, `xbrl_metrics.py` | GBDC, KREF | XBRL company facts |
| `nport.py` | CCLFX, TAKIX | N-PORT XML |
| `highlights.py` | CCLFX, TAKIX | N-CSR/N-CSRS financial highlights — the only class-level source |
| `narrative.py` | all | Fee tables, anchored prose patterns, optional LLM |

The interval funds file no 10-K and have eleven usable `cef:` tags between them,
so their fee terms exist only in prose and their class-level figures only in the
annual and semi-annual reports.

## 2. Key decisions

**Every metric carries a `basis`, not just a value.** Forced by KREF, whose fee
is struck on stockholders' equity and whose "NAV per share" is GAAP book value.
That gap cannot be a footnote added at render time. It has paid for itself
repeatedly since — the leverage split and the unconfirmed basis of your own
column are both render-time switches *because* basis is in the schema.

**Metrics are declarations, not code.** Label, unit, direction, plausible range,
and where the value is found. Your PMs' quarterly additions are JSON entries.

**Blanks are typed**, and a bare blank raises rather than renders.

**Structured-first, LLM last.** The LLM tier is built but unused — deterministic
tiers reach every fee — so the pipeline runs with no API key. Its guard, if
enabled: the model must return a verbatim quote, checked to be literally present
in the source. An unverifiable answer is discarded, not discounted.

## 3. Validation and the confidence model

**We asked for external validation and could not have it.** A prior-quarter pack
to reconcile against was declined on compliance grounds. Nothing here has been
checked against an external reference, and this document would rather say so than
let confidence grades imply otherwise.

So the score uses only what we can observe about the extraction:

```
score = tier × agreement × freshness × ∏(named penalties)
```

**Tier** scores the mechanism — a typed XBRL fact (0.95) through a model reading
a footnote (0.55) — not the filer. **Agreement** is the only factor that can
raise a score and the closest thing to ground truth available. **Penalties** are
named and published; an unrecognised flag takes a default, so a new one cannot
silently pass at full confidence. Every input is recorded, so a reviewer audits
the score rather than trusting it. Nothing asks a model how confident it is.

Reconciliations that run: cross-mechanism (GBDC NAV — XBRL 14.84 vs
equity÷shares, agreeing to 0.02%); cross-document (CCLFX's fee in both the
expense table and prose); internal consistency; and bound-checking against
TAKIX's seven unlabelled class series. Resolution is by weight of evidence —
the cluster with most *independent* extractions wins, then fewest flags, then
tier. Below 0.40 the value is withheld and the blank states why.

## 4. Where sources disagreed

**A correctly-tagged number can be the wrong one.** GBDC's XBRL reports its
management fee as 0.021% — valid, from a notes prospectus rather than the fund's
fee table. Highest tier, wrong number, suppressed at 0.13. This is why tier alone
cannot be the model.

**Superseded rates sit beside current ones.** GBDC's 10-K says "reduced from
1.375% to 1.0%"; TAKIX's prospectus quotes a fee retired in 2020. Both are
emitted and resolved by effective date, and a superseded rate never renders bare
— GBDC's superseded 20% and KREF's live 20% are the same number meaning
opposite things.

**Adjacent figures get confused.** TAKIX's catch-up rate (1.765%) shares a
sentence with its hurdle (1.500%). KREF's fee is quoted quarterly on adjusted
equity — 0.375%, which is 1.50% a year against peers quoting ~1.0%.

**A quarter BDCs never tag separately** understated GBDC's 1Y return by 265bp
until reconstructed by differencing the annual total.

**TAKIX reports zero borrowings against $2.2bn of liabilities**, so its
regulatory cell blanks — that basis measures nothing. Per your CIO's ruling
leverage reports as two rows, with neither standing in for the other.

**Your own leverage basis is the one question that survived Window 3.** Your
confirmation covered share class and fee treatment. It did not say which basis
your single `leverage_ratio_dte` column uses, and the peers' two bases differ by
more than a factor of two. Your figure renders; its delta is withheld.

## 5. Limitations

- **30 of 40 cells populate**, classified in `output/coverage_breakdown.md` by
  who owns each gap. Nothing remains that further extraction would close: 4 are
  cadence-limited, 6 structural. Every metric reachable from EDGAR is extracted.
- **CCLFX's cadence gap is live.** Its March year-end puts the annual report 275
  days behind a Q4 2025 anchor, so four cells blank on your six-month rule rather
  than any failure of ours. This recurs annually.
- **The NAV trend is semi-annual**, per your ruling. Dates differ by fiscal
  calendar and are labelled per point; interpolating would invent observations.
- **Fund discovery cannot reach every filer.** SEC's ticker files omit non-traded
  interval funds entirely, and an entity type we do not handle has no adapter.

## 6. Production risks

| Risk | Mitigation |
| --- | --- |
| **Filers change wording; prose patterns stop matching.** Most likely failure. | A miss produces a blank with a reason, never a wrong number — which is why it goes unnoticed. `--compare-to` diffs against the previous quarter's coverage, names what stopped populating and why, and exits non-zero so a scheduled run gates on it. |
| **A filer re-tags XBRL or tags the wrong document.** Already observed. | Cross-mechanism agreement plus plausibility ranges; flagged and suppressed, not trusted on tier. |
| **Non-determinism in rendering.** Found late: tie-breaking with `max(set(...))` varies between processes, so two clones produced different board tables from identical data — a basis label moving on its own, indistinguishable in a diff from a number moving. | Ties break by first appearance. Tested in subprocesses across five hash seeds; an in-process test would have passed against the broken code. Found by running the pipeline twice, which no test had done. |
| **Source scope expands beyond EDGAR.** Likely. | Adopt web sources only as a distinct, visibly lower tier — a filing has an accession number and an immutable version; a web page has neither. Never blend silently. |
| **Provenance rots.** | Every value carries accession, form, period, URL, in-document locator and a verbatim excerpt. All resolve today. |

---

**Whose decisions these are.** Confirmed by the client: blank-over-guess; the
six-month staleness line; the reporting-quarter anchor; institutional share class
for the interval funds; basis at the cell; the amendment-based fee clock;
semi-annual NAV; two leverage rows; the KREF perimeter. **Consultant defaults,
unratified:** confidence weightings, the 0.40 floor, the N-PORT depth cap, and
the inclusion of KREF's $632m secured term loan as recourse debt.
