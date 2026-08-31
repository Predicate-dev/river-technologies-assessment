# Competitor benchmarking — solution brief

**For:** CIO and Managing Partner, Apex Ridge Capital Partners

---

## What we built

A system that pulls your four competitors' filings directly from the SEC,
extracts the eight benchmark metrics, and produces the peer table your PMs
already read — with two things the current process cannot give you. Every number
cites the filing and location it came from, and carries a confidence grade we can
defend. Where the evidence does not support a number, the cell is **blank with a
stated reason** rather than filled with a figure nobody can stand behind.

The quarterly cycle goes from 6–8 hours of transcription to minutes of machine
time plus a review pass over the exceptions. More importantly it changes what the
pack *is*: today, transcribed numbers whose derivation lives in an analyst's
memory; afterwards, numbers that each trace back to a filing in one click.

## What changes

**Today** an analyst reads 100–200+ pages per competitor and hand-keys figures
into Excel. The judgment calls — which of several similar-looking numbers is
right — happen silently and are never recorded. A misread basis point on a
leverage ratio reached a board deck last year.

**Afterwards** the analyst reviews exceptions: cells where sources disagreed, and
cells left blank. Smaller work, and the part where judgment is worth something. A
person still signs off; this replaces the typing, not the review.

The three additions from today's call are covered below.

## The judgment calls, in business terms

**We made the system prefer a gap to a guess** — your rule, applied literally. Of
40 competitor cells, 30 populate and 10 are blank, and none of the blanks is now
ours to close: four are figures that exist but fall outside your six-month
staleness line, and six are figures the competitor does not publish at all.
Nothing is any longer waiting on a decision from you.

**Do not read the old pack's completeness as accuracy.** This is the first
account of which cells were ever actually sourced from a filing. Some filled by
hand every quarter appear to have come from fund websites rather than SEC
filings — not wrong, but a different evidentiary standard, and nothing recorded
which was which.

**We refused to substitute near-metrics.** KREF is described as a BDC; it is a
mortgage REIT and publishes no fund-style net return. Filling its return rows
with total shareholder return would have made the table look complete. Those rows
are blank and labelled instead — a complete-looking table comparing two different
things is the failure this system exists to prevent.

**We separated "sources disagree" from "the definition is open."** TAKIX reports
zero borrowings while carrying $2.2bn of liabilities. A figure was computable,
but which one was right depended on a definition — so the system held it rather
than picking. Your CIO has since ruled, leverage now reports as two rows, and
TAKIX reads blank on regulatory and 0.45x on economic. The discipline is the
point: the number waited for the definition rather than the other way round.

That same discipline now applies to one figure of your own. Your confirmation
covered share class and fee treatment, which released every other comparison.
It did not establish which leverage basis your own ratio is on, and the peer
bases differ by more than a factor of two — so your leverage figure appears and
its comparison is withheld until you tell us. It is a single setting to reverse.

## What it caught

From the live run, not hypotheticals:

- **GBDC's own tagged data reports its management fee as 0.021%** — technically
  correct, from a different offering document, and wrong for this purpose. The
  true rate is 1.0%. A system trusting "official structured data" ships it.
- **GBDC's annual report states both its old and current fee in one sentence** —
  "reduced from 1.375% to 1.0%". Reading the first is precisely the misread that
  reached your board. TAKIX's prospectus quotes a fee retired in 2020.
- **KREF's fee is quoted quarterly** on a different base — 0.375% as printed,
  against peers quoting ~1.0%. It is 1.50% a year.
- **A distribution quarter BDCs never report separately** understated GBDC's
  one-year return by 265 basis points.

Each is a number a careful analyst could get wrong, and none announces itself.

## Confidence

We asked to reconcile our output against a prior quarter's manual pack and were
told — correctly — that live fund data cannot leave the firm without compliance
sign-off. So this has never been checked against an external reference, and we
would rather say so than let the grades imply otherwise.

The system therefore reports **evidence**, not accuracy: how a number was
obtained, whether independently built versions agree, how current the filing is,
and any problem seen while extracting. High means several independent routes
converged; Low means one route, unchecked. That survives a board question. "The
model said so" does not, and nothing here asks a model how confident it is.

## The three scope additions

**Custom metrics** are now definitions rather than code — describe a metric and
it flows through with the same provenance and confidence as the original nine.
Portfolio turnover, non-accrual rates and total annual expenses already work
this way. Next quarter's metric does not require us to write software.

**Fund discovery** searches EDGAR and adds a fund by CIK. It never picks a
search result for you, and refuses any fund it cannot confidently classify —
the system runs different extraction against a BDC, an interval fund and a
REIT, and guessing there produces confident wrong numbers rather than blanks.
Tested by adding Ares Capital cold: 8 of 9 metrics correct on the first run.

**Word output** is produced every run, with the table, the coverage account, the
resolved conflicts and a provenance appendix. Blank cells carry their reasons
there too — the document that leaves the building must not look more complete
than the evidence behind it.

## Production rollout

1. **Close the definitional questions** (2–3 weeks, mostly your time) — the
   leverage definition, the basis of your own figures, compliance sign-off on
   model-assisted extraction. Most are configuration switches by design, so late
   answers do not trigger rework.
2. **Settle what counts as a source** (1 week, your analysts). Cells that only
   ever came from fund websites cannot be closed by any amount of filing
   extraction. If adopted, such sources should carry a distinct and visibly lower
   confidence tier — no accession number, no immutable version, no audit trail a
   reviewer could follow years later.
3. **Operationalise** (1–2 weeks). Quarterly runs timed to your
   two-weeks-after-close cycle, an alert when a metric that populated last
   quarter stops, and the analyst's review interface.

Coverage itself needs no further work unless scope changes: every cell reachable
from EDGAR is populated.

The ongoing risk: **filers change wording, and extraction that depends on wording
quietly stops matching.** We designed for it — a failed match produces a blank
with a reason, never a wrong number — but it needs an owner, not an install.

## Tradeoffs

We chose depth of evidence over breadth of coverage. Filling all 40 cells with
unverified numbers was achievable in the time; we judged it worth less than 30
you can defend in a board meeting plus an account of who owns each of the 10
that are empty.

One consequence of your own rules is worth seeing before it surprises you.
CCLFX's March fiscal year-end puts its most recent annual report 275 days behind
a Q4 2025 reporting date — past your six-month line. Four of its cells blank on
your rule rather than any failure of ours — all three trailing returns and the
distribution yield — and this recurs every year in the same two quarters. It is the live case for the labelled fund-level fallback now with
your CIO.
