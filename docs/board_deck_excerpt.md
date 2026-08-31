# Board deck excerpt — quarterly competitor benchmarking (current format)

> Redacted excerpt from a prior quarterly board presentation, provided as a
> FORMAT reference only: this is the comparison layout the PMs are accustomed
> to seeing. All values are redacted — including Apex Ridge's own. Today this
> table is assembled by hand in Excel each quarter from analyst transcriptions
> of competitor filings.

## Slide 14 — Peer benchmarking, private credit comparables

| Metric | Apex Ridge | CCLFX | TAKIX | GBDC | KREF |
| --- | --- | --- | --- | --- | --- |
| Net return, trailing 1Y (ann.) | ▮▮▮ | ▮▮▮ | ▮▮▮ | ▮▮▮ | ▮▮▮ |
| Net return, trailing 3Y (ann.) | ▮▮▮ | ▮▮▮ | ▮▮▮ | ▮▮▮ | ▮▮▮ |
| Net return, trailing 5Y (ann.) | ▮▮▮ | ▮▮▮ | ▮▮▮ | ▮▮▮ | ▮▮▮ |
| Management fee | ▮▮▮ | ▮▮▮ | ▮▮▮ | ▮▮▮ | ▮▮▮ |
| Incentive fee (hurdle) | ▮▮▮ | ▮▮▮ | ▮▮▮ | ▮▮▮ | ▮▮▮ |
| NAV per share | ▮▮▮ | ▮▮▮ | ▮▮▮ | ▮▮▮ | ▮▮▮ |
| Leverage (D/E) | ▮▮▮ | ▮▮▮ | ▮▮▮ | ▮▮▮ | ▮▮▮ |
| Distribution yield (ann.) | ▮▮▮ | ▮▮▮ | ▮▮▮ | ▮▮▮ | ▮▮▮ |

Footnotes (as they appear in the deck):

1. Competitor figures transcribed from most recent public filings available at
   time of preparation; filing periods may not align with Apex Ridge quarter end.
2. Leverage shown as reported; regulatory vs. economic basis varies by fund.
3. CCLFX and TAKIX figures as reported for the institutional share class.
4. Prepared manually by the analytics team. Figures as transcribed.

---

# Annotation added by the engagement — how the current output differs

*The excerpt above is the client's own redacted artefact and is left exactly as
provided. This section is ours, added because the generated board table has
deliberately diverged from that layout and the differences are decisions, not
drift.*

## Rows

| Their layout | Current output | Why |
| --- | --- | --- |
| `Leverage (D/E)` — one row | **Two rows**: regulatory and economic | Their CIO's Window 3 ruling. Her words: "a single row with a basis note is exactly the kind of thing a tired reader misses and I will not rebuild that risk into the output." |
| `Incentive fee (hurdle)` — one row | **Two rows**: incentive fee, incentive hurdle | A hurdle is a threshold and a fee is a rate. Combining them forces one of the two into a parenthetical, and CCLFX charges no incentive fee at all — so its hurdle is *inapplicable* rather than blank, which the combined row cannot express. |
| 8 rows fixed | 9 base rows, plus any custom metrics | The metric set is now declarative; the PMs' quarterly additions appear as rows without a code change. |

## Cells

Their cells carry a value. Ours carry a value **and** its evidence:

- **Confidence** (High / Med / Low) on every extracted figure.
- **As-of date**, because the four filers report on four different fiscal
  calendars and "as reported" was footnote 1 of their own deck.
- **Basis**, shown at the cell rather than in a slide footnote — an explicit
  client requirement: "I do not want a PM reading that row and assuming it is on
  the same basis as CCLFX without noticing the footnote."
- **A reason on every blank.** Their layout has no way to express one, which is
  the gap that mattered most: a hand-assembled table cannot distinguish "the
  filer does not publish this" from "we could not find it."

## Footnotes

Their four footnotes are all now either enforced in code or superseded:

1. *"figures transcribed from most recent filings; periods may not align"* —
   enforced. Every figure is eligible only if its period ends on or before the
   reporting quarter, and its as-of date is on the cell.
2. *"leverage shown as reported; regulatory vs economic basis varies"* —
   superseded by the two-row split.
3. *"CCLFX and TAKIX figures as reported for the institutional share class"* —
   enforced. A fund-level figure will not render into a cell this footnote
   claims is institutional; it blanks instead.
4. *"prepared manually by the analytics team; figures as transcribed"* — no
   longer true, which is the point of the engagement.

## What has not changed

One column per fund, metrics as rows, the same metric names and ordering where
the metric is unchanged. A PM who reads the old slide can read the new one.
