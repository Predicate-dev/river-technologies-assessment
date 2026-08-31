# Apex Ridge — competitor benchmarking pipeline

Automates the quarterly peer-benchmarking pack: pulls competitor filings from
SEC EDGAR, extracts and normalizes the benchmark metrics, compares them against
Apex Ridge's own fund data, and produces a board-format table in which **every
value carries its provenance and a confidence grade, and every blank carries its
reason**.

Replaces a 6–8 hour manual transcription cycle in which an analyst read 100–200+
pages per competitor and hand-keyed figures into a locked Excel template.

## Quick start

```bash
git clone <this-repo>
cd river-tech-challenge

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Identify yourself to the SEC. Required: they rate-limit anonymous traffic.
export SEC_USER_AGENT="Your Name (you@yourfirm.com)"

python -m apexridge --print
```

Python 3.11+ (developed on 3.12). First run downloads ~150MB of filings and
takes roughly 3–5 minutes; every subsequent run is served from `.cache/` and
completes in seconds.

Two files land in `output/`:

| File | What it is |
| --- | --- |
| `benchmark_table.md` | The board table, in the layout the PMs already read, plus the conflict log and the reason for every blank cell. |
| `apex_vs_peers.md` | Peer median, range and ordering per metric, plus Apex's delta and rank. Apex-versus-peer deltas are withheld until the basis of the client's own column is confirmed; peer-to-peer statistics do not depend on it and render today. |
| `nav_trend.md` | NAV per share over the trailing window, on a common semi-annual footing with each fund's actual reporting dates labelled. |
| `coverage_breakdown.md` | Every cell classified by who owns the gap: reported, ours to close, cadence-limited, blocked on a client decision, or structurally unavailable. |
| `audit_trail.csv` | One row per candidate value the pipeline found — winners *and* rejects — with source tier, filing accession, in-document locator, verbatim excerpt, transforms applied, flags raised, and the confidence score inputs. |

### Options

```bash
python -m apexridge --funds GBDC KREF      # subset of the peer set
python -m apexridge --anchor 2025-09-30    # a different reporting quarter
python -m apexridge --offline              # cache only; fails rather than degrading silently
python -m apexridge --nport-limit 16       # deeper N-PORT history (slower)
python -m apexridge --compare-to prior/coverage_breakdown.csv   # regression vs a previous run
python -m apexridge -v                     # log extraction and suppression decisions
python -m apexridge --help
```

### Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q          # 89 tests
```

Tests cover the data-correctness path and the failure modes drawn from real
filing text — distribution-period arithmetic, month attribution, anchoring and
eligibility, superseded and historical fee rates, hurdle annualization, and the
blank-cell precedence rules. Glue and I/O are deliberately untested.

## What it does

```
EDGAR (live)  ──►  source adapters  ──►  candidates  ──►  eligibility filter
                                                              │
                        reconciliation ◄─────────────────────┘
                              │
              ┌───────────────┴───────────────┐
        resolved value                  suppression
        + confidence + provenance       + typed reason
                              │
                          render ──► board table + audit trail
```

An extracted number is never stored bare. It is a **candidate** — a value plus
its evidence — and several candidates for the same metric are reconciled in a
separate, logged step, so disagreement between sources survives rather than
being silently collapsed.

The four competitors do not file the same forms, and the pipeline does not
pretend otherwise:

| Fund | Type | Fiscal year end | Primary sources |
| --- | --- | --- | --- |
| CCLFX | Non-traded interval fund | 31 Mar | N-PORT XML, 486BPOS prospectus |
| TAKIX | Non-traded interval fund | 31 Dec | N-PORT XML, 486BPOS, N-CSR |
| GBDC | Listed BDC | 30 Sep | XBRL company facts, 10-K |
| KREF | Mortgage REIT — *not* a BDC | 31 Dec | XBRL company facts, 10-K |

## Confidence

There is no answer key. The manual process being replaced was the client's only
source for these numbers, so confidence cannot be an accuracy measurement — it
is an auditable statement of the evidence behind a value:

```
score = tier × agreement × freshness × ∏(named penalties)
```

`tier` scores the extraction *mechanism* (typed XBRL fact → parsed table → prose
pattern → model reading a footnote). `agreement` is the only factor that can
raise a score and the closest thing to ground truth available: independently
constructed values for the same thing on the same basis either converge or they
do not. `freshness` ages the underlying period against the reporting quarter.
Penalties are named and published, one per observed problem.

Below 0.40 the value is withheld and the blank states why. **Nothing anywhere
asks a model how confident it is.**

See [`docs/technical-approach.md`](docs/technical-approach.md) for the full model
and the reconciliations it runs, and
[`docs/solution-brief.md`](docs/solution-brief.md) for the business summary.

## Layout

```
apexridge/
  config.py          fund registry — entity type, fiscal year end, metric scope
  edgar.py           rate-limited, disk-cached EDGAR client
  pipeline.py        orchestration: extract → filter → reconcile
  __main__.py        CLI
  core/
    models.py        Candidate, Provenance, Conflict, Suppression, Cell
    periods.py       distribution ledger (cumulative differencing)
    temporal.py      reporting anchor, eligibility, staleness, filing windows
    confidence.py    the scoring model
    reconcile.py     basis selection, conflict resolution, suppression
  sources/
    xbrl.py          XBRL company-facts index
    xbrl_metrics.py  metric extractors for the 10-K/10-Q filers
    nport.py         N-PORT adapter for the interval funds
    highlights.py    N-CSR financial highlights — class-level data
    narrative.py     fee tables, prose patterns, optional LLM tier
  render/
    cells.py         typed cells; suppression → presentation mapping
    table.py         board table and audit trail
    coverage.py      cell-by-cell gap ownership
    trend.py         NAV trend on a semi-annual footing
NOTES/               decisions, open client questions, descoped items
docs/                technical approach, solution brief, board format reference
```

## Watching for silent failure

The pipeline's failure mode is quiet by design: if a filer changes wording and a
pattern stops matching, the cell blanks with a reason rather than reporting a
wrong number. That is correct, and it is exactly why nobody notices.

`--compare-to` diffs the current run against a previous quarter's
`coverage_breakdown.csv` and reports what populated then and blanks now,
distinguishing an extraction that stopped matching from a figure that merely
aged out or is held on an open question. It exits non-zero when coverage is
lost, so a scheduled run can gate on it.

## Notes on the LLM tier

Built, and currently **off**: the deterministic tiers cover every fee the system
extracts, and third-party model use is an open compliance item with the client.
When enabled (`--use-llm`, needs `ANTHROPIC_API_KEY`), the model must return a
value **and** a verbatim supporting quote, and the quote is checked to be
literally present in the source document. An answer whose quote cannot be found
is discarded, not downgraded.

## SEC access

Requests are self-throttled to 8/second against the SEC's published 10/second
ceiling, with backoff on 403 and 429, and a descriptive `User-Agent` as they
require. All filings are cached to `.cache/` by URL, which makes runs
deterministic and means a demo cannot be broken by a network hiccup.

## Current status

Prototype. 89 tests passing, running against live EDGAR at the Q4 2025 anchor.
26 of 36 competitor cells populate; the rest blank with a stated reason, broken
down cell by cell in `output/coverage_breakdown.md`. Known gaps and their causes
— some ours, some structural to the filers, and some possibly outside EDGAR
entirely — are in
[`docs/technical-approach.md`](docs/technical-approach.md) §6 and
[`NOTES/questions.md`](NOTES/questions.md).
