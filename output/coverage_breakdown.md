# Coverage breakdown — cell by cell

Reporting quarter 2025-12-31. **18 of 36 competitor cells populated.**

Each empty cell is classified by who owns the gap. The OURS rows are the ones this system can act on; the rest need either a client decision or a filing that does not exist.

> **Caveat on the OURS rows.** These assume the figure exists somewhere in the filer's EDGAR filings and we have simply not built the extraction. That assumption is now open: the client has confirmed her analysts sometimes source from fund websites, investor-relations pages and press releases as well as EDGAR. Any cell filled that way in the manual pack has no EDGAR source and cannot be closed within the current scope, however much extraction we build. Until the client's cell-by-cell source review comes back, treat OURS as *not yet ruled out* rather than as a committed backlog, and do not read a projected coverage number off this table.

| | CCLFX | TAKIX | GBDC | KREF |
| --- | --- | --- | --- | --- |
| Net return, trailing 1Y (ann.) | **8.912 pct** (Low) | _OURS_ | **8.723 pct** (Low) | _STRUCTURAL_ |
| Net return, trailing 3Y (ann.) | _OURS_ | _OURS_ | **11.88 pct** (Low) | _STRUCTURAL_ |
| Net return, trailing 5Y (ann.) | _OURS_ | _OURS_ | _STRUCTURAL_ | _STRUCTURAL_ |
| Management fee | **1 pct** (Medium) | **1 pct** (Low) | **1 pct** (Medium) | _OURS_ |
| Incentive fee | **0 pct** (Low) | _OURS_ | **15 pct** (Medium) | **20 pct** (Low) |
| Incentive hurdle | _OURS_ | _OURS_ | **8 pct** (Low) | **7 pct** (Low) |
| NAV per share | _OURS_ | _OURS_ | **14.84 usd** (High) | **18.22 usd** (Low) |
| Leverage (D/E) | **0.3186 ratio** (Medium) | _CLIENT_ | **1.254 ratio** (Medium) | **2.449 ratio** (Medium) |
| Distribution yield (ann.) | _OURS_ | _OURS_ | **10.43 pct** (Medium) | **5.449 pct** (Medium) |

## Where the gaps sit

| Owner | Cells | Meaning |
| --- | --- | --- |
| FILLED | 18 | reported with a confidence grade |
| OURS | 13 | extraction we have not built, or evidence too thin |
| CADENCE | 0 | figure exists but falls outside the six-month window |
| CLIENT | 1 | computable, withheld pending a client decision |
| STRUCTURAL | 4 | the filer does not publish it; no work would fix it |

### Ours to close (13)

- **CCLFX — Distribution yield (ann.)** [no_candidate]: no EDGAR source located; either extraction we have not built, or the figure is not in the filings at all -- see the caveat below
- **CCLFX — Incentive hurdle** [no_candidate]: no EDGAR source located; either extraction we have not built, or the figure is not in the filings at all -- see the caveat below
- **CCLFX — NAV per share** [no_candidate]: no EDGAR source located; either extraction we have not built, or the figure is not in the filings at all -- see the caveat below
- **CCLFX — Net return, trailing 3Y (ann.)** [insufficient_history]: history depth limited by our download cap, not by availability
- **CCLFX — Net return, trailing 5Y (ann.)** [insufficient_history]: history depth limited by our download cap, not by availability
- **KREF — Management fee** [no_candidate]: no EDGAR source located; either extraction we have not built, or the figure is not in the filings at all -- see the caveat below
- **TAKIX — Distribution yield (ann.)** [no_candidate]: no EDGAR source located; either extraction we have not built, or the figure is not in the filings at all -- see the caveat below
- **TAKIX — Incentive fee** [no_candidate]: no EDGAR source located; either extraction we have not built, or the figure is not in the filings at all -- see the caveat below
- **TAKIX — Incentive hurdle** [below_confidence_floor]: evidence too thin; needs a second corroborating source
- **TAKIX — NAV per share** [no_candidate]: no EDGAR source located; either extraction we have not built, or the figure is not in the filings at all -- see the caveat below
- **TAKIX — Net return, trailing 1Y (ann.)** [class_attribution_failed]: N-PORT omits class identifiers, but the annual report's financial highlights name each class; that extraction is not built yet
- **TAKIX — Net return, trailing 3Y (ann.)** [class_attribution_failed]: N-PORT omits class identifiers, but the annual report's financial highlights name each class; that extraction is not built yet
- **TAKIX — Net return, trailing 5Y (ann.)** [class_attribution_failed]: N-PORT omits class identifiers, but the annual report's financial highlights name each class; that extraction is not built yet

### Blocked on a client decision (1)

- **TAKIX — Leverage (D/E)** [basis_disqualified]: computable, withheld pending a definition the client is deciding

### Structural — no work would fix these (4)

- **GBDC — Net return, trailing 5Y (ann.)** [window_mismatch]: filer's tagged history does not span the labelled window
- **KREF — Net return, trailing 1Y (ann.)** [not_applicable]: filer does not publish this concept; no extraction would fix it
- **KREF — Net return, trailing 3Y (ann.)** [not_applicable]: filer does not publish this concept; no extraction would fix it
- **KREF — Net return, trailing 5Y (ann.)** [not_applicable]: filer does not publish this concept; no extraction would fix it

## Confidence of what is populated

| Grade | Cells |
| --- | --- |
| High | 1 |
| Medium | 8 |
| Low | 9 |