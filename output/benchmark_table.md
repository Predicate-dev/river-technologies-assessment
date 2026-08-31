# Peer benchmarking — private credit comparables

**Reporting quarter:** 2025-12-31 (Q4 2025). Every figure is as reported by the filer for a period ending on or before that date.

Confidence: High / Med / Low. A blank cell states why it is blank; it is never an extraction that quietly failed.

| Metric | Apex Ridge | CCLFX | TAKIX | GBDC | KREF |
| --- | --- | --- | --- | --- | --- |
| Net return, trailing 1Y (ann.) | **10.31%** (client data) as of 2025-12-31 [basis unconfirmed] | _blank: no figure within staleness window -- most recent reported figure is 275d old, beyond the 183d limit_ | **6.27%** (Med) as of 2025-12-31 [net of fees: True; chain linked annual total return; share class: Class I] | **8.72%** (Low) as of 2025-12-31 | _blank: not reported at this basis -- not reported by a mortgage reit; left blank rather than substituted with a near-metric on an incomparable basis_ |
| Net return, trailing 3Y (ann.) | **9.92%** (client data) as of 2025-12-31 [basis unconfirmed] | _blank: no figure within staleness window -- most recent reported figure is 275d old, beyond the 183d limit_ | **10.36%** (Med) as of 2025-12-31 [net of fees: True; chain linked annual total return; share class: Class I] | **11.88%** (Low) as of 2025-12-31 | _blank: not reported at this basis -- not reported by a mortgage reit; left blank rather than substituted with a near-metric on an incomparable basis_ |
| Net return, trailing 5Y (ann.) | **9.39%** (client data) as of 2025-12-31 [basis unconfirmed] | _blank: no figure within staleness window -- most recent reported figure is 275d old, beyond the 183d limit_ | **8.21%** (Med) as of 2025-12-31 | _blank: insufficient history to compute -- NAV history does not span a full 5Y window (nearest anchor 2020-09-30 is 92d from the 2020-12-31 start date, tolerance 60d); 4.3y available (2021-09-30 to 2025-12-31)_ | _blank: not reported at this basis -- not reported by a mortgage reit; left blank rather than substituted with a near-metric on an incomparable basis_ |
| Management fee | **1.25%** (client data) as of 2025-12-31 [basis unconfirmed] | **1.00%** (Med) as of 2025-08-12 | **1.00%** (Low) as of 2024-12-31 | **1.00%** (Med) as of 2025-09-30 | **1.50%** (Low) as of 2024-12-31 [pct of adjusted equity] |
| Incentive fee | **12.50%** (client data) as of 2025-12-31 [basis unconfirmed] | **none charged** (Low) as of 2025-08-12 [none disclosed] | **15.00%** (Low) as of 2025-04-28 | **15.00%** (Med) as of 2025-09-30 | **20.00%** (Low) as of 2024-12-31 |
| Incentive hurdle | **6.00%** (client data) as of 2025-12-31 [basis unconfirmed] | _blank: not reported at this basis -- the fund charges no incentive fee, so no hurdle applies_ | **6.00%** (Low) as of 2025-04-28 | **8.00%** (Low) as of 2025-09-30 | **7.00%** (Low) as of 2024-12-31 |
| NAV per share | **$26.12** (client data) as of 2025-12-31 [basis unconfirmed] | **$10.77** (Low) as of 2025-09-30 | **$8.32** (Low) as of 2025-12-31 | **$14.84** (High) as of 2025-12-31 [class: common; measure: nav per share] | **$18.22** (Low) as of 2025-12-31 [class: common; measure: book value per share] |
| Leverage (D/E) | **0.96x** (client data) as of 2025-12-31 [as supplied by Apex Ridge] [basis unconfirmed] | **0.32x** (Med) as of 2025-12-31 [gross debt to equity] | _blank: reported basis does not measure this metric -- the filer reports no borrowings while carrying material total liabilities, so the reported basis does not measure leverage; the basis to use is with the client_ | **1.25x** (Med) as of 2025-12-31 [gross debt to equity] | **2.45x** (Med) as of 2025-12-31 [gross debt to equity] |
| Distribution yield (ann.) | **9.22%** (client data) as of 2025-12-31 [basis unconfirmed] | _blank: no figure within staleness window -- most recent reported figure is 275d old, beyond the 183d limit_ | **9.01%** (Med) as of 2025-12-31 [denominator: nav; net of fees: True; share class: Class I; fiscal year distributions on nav] | **10.43%** (Med) as of 2025-12-31 | **5.45%** (Med) as of 2025-12-31 |

## Source conflicts resolved in this run

- **TAKIX — Management fee**: candidates 1, 1.5 (spread 33%). Resolved to **1 (text_pattern)**. kept 1: agreed on by 1 independent extraction(s) vs 1.5 (1); chosen source text_pattern, flags ['rate_not_restated_within_window']
- **GBDC — Incentive fee**: candidates 15, 20 (spread 25%). Resolved to **15 (text_pattern)**. kept 15: agreed on by 2 independent extraction(s) vs 20 (1); chosen source text_pattern, no flags

## Blank cells

- **CCLFX — Net return, trailing 3Y (ann.)** [insufficient_history]: 24 of the 36 contiguous monthly returns needed for this window are available from N-PORT; 1.9y available (2024-01-31 to 2025-12-31).
- **CCLFX — Net return, trailing 5Y (ann.)** [insufficient_history]: 24 of the 60 contiguous monthly returns needed for this window are available from N-PORT; 1.9y available (2024-01-31 to 2025-12-31).
- **GBDC — Net return, trailing 5Y (ann.)** [window_mismatch]: NAV history does not span a full 5Y window (nearest anchor 2020-09-30 is 92d from the 2020-12-31 start date, tolerance 60d); 4.3y available (2021-09-30 to 2025-12-31).
- **TAKIX — Net return, trailing 1Y (ann.)** [class_attribution_failed]: 7 share-class return series are reported without class identifiers; could not attribute a figure to the institutional class; last available 2025-12-31.
- **TAKIX — Net return, trailing 3Y (ann.)** [class_attribution_failed]: 7 share-class return series are reported without class identifiers; could not attribute a figure to the institutional class; last available 2025-12-31.
- **TAKIX — Net return, trailing 5Y (ann.)** [class_attribution_failed]: 7 share-class return series are reported without class identifiers; could not attribute a figure to the institutional class; last available 2025-12-31.

---

Apex Ridge's own column renders with an unconfirmed basis: the share class and fee treatment behind the supplied figures are not yet established, so peer-minus-Apex deltas are withheld. A delta between two numbers of unknown basis is precisely the confidently-wrong figure this system exists to prevent.