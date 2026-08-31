# Competitor benchmarking — solution brief

**For:** CIO and Managing Partner, Apex Ridge Capital Partners

---

## What we built

A system that pulls your four competitors' filings directly from the SEC,
extracts the benchmark metrics, and produces the peer table your PMs already
read — with two things the current process cannot give you. Every number cites
the filing and location it came from, and carries a confidence grade we can
defend. Where the evidence does not support a number, the cell is **blank with a
stated reason** rather than filled with a figure nobody can stand behind.

The quarterly cycle goes from 6–8 hours of transcription to minutes of machine
time plus a review pass over the exceptions. More importantly it changes what the
pack *is*: today, transcribed numbers whose derivation lives in an analyst's
memory; afterwards, numbers that each trace back to a filing in one click. Your
analyst's job shifts from typing to reviewing the cells where sources disagreed —
the part where judgment is worth something. A person still signs off.

## The judgment calls

**We made the system prefer a gap to a guess** — your rule, applied literally. Of
40 competitor cells, 30 populate and 10 are blank. None of the blanks is ours to
close: four are figures that exist but fall outside your six-month staleness
line, and six are figures the competitor does not publish at all.

**Do not read the old pack's completeness as accuracy.** This is the first
account of which cells were ever actually sourced from a filing. Some filled by
hand each quarter appear to have come from fund websites rather than SEC
filings — not wrong, but a different evidentiary standard, and nothing recorded
which was which.

**We refused to substitute near-metrics.** KREF is described as a BDC; it is a
mortgage REIT and publishes no fund-style net return. Filling its return rows
with total shareholder return would have made the table look complete. Those
rows are blank and labelled instead — a complete-looking table comparing two
different things is the failure this system exists to prevent.

## What it caught

From the live run, not hypotheticals:

- **GBDC's own tagged data reports its management fee as 0.021%** — technically
  correct, from a different offering document, and wrong for this purpose. The
  true rate is 1.0%. A system trusting "official structured data" ships it.
- **GBDC's annual report states both its old and current fee in one sentence** —
  "reduced from 1.375% to 1.0%". Reading the first is precisely the misread that
  reached your board. TAKIX's prospectus quotes a fee retired in 2020.
- **KREF's fee is quoted quarterly** on a different asset base — 0.375% as
  printed, against peers quoting ~1.0%. It is 1.50% a year.
- **A distribution quarter BDCs never report separately** understated GBDC's
  one-year return by 265 basis points.

Each is a number a careful analyst could get wrong, and none announces itself.

## Confidence

We asked to reconcile against a prior quarter's manual pack and were told —
correctly — that live fund data cannot leave the firm without compliance
sign-off. So this has never been checked against an external reference, and we
would rather say so than let the grades imply otherwise.

The system reports **evidence**, not accuracy: how a number was obtained, whether
independently built versions agree, how current the filing is, and any problem
seen while extracting. High means several independent routes converged; Low means
one route, unchecked. That survives a board question. "The model said so" does
not, and nothing here asks a model how confident it is.

## Rollout and tradeoffs

The three additions you asked for are in: custom metrics are now definitions
rather than code, so next quarter's metric does not require us; fund discovery
adds a peer by CIK and refuses any it cannot confidently classify; and the Word
document is produced every run, with blanks carrying their reasons there too.

Four to six weeks: close the remaining definitional questions (mostly your time);
settle whether fund websites count as a source, since cells sourced that way
cannot be closed by any amount of filing extraction; then scheduled quarterly
runs timed to your two-weeks-after-close cycle, with an alert when a metric that
populated last quarter stops. Coverage itself needs no further work.

The ongoing risk: **filers change wording, and extraction that depends on wording
quietly stops matching.** A failed match produces a blank with a reason, never a
wrong number — but this needs an owner, not an install.

We chose depth of evidence over breadth. Filling all 40 cells with unverified
numbers was achievable; we judged it worth less than 30 you can defend plus an
account of who owns each of the 10 that are empty.

One consequence of your own rules is worth seeing before it surprises you.
CCLFX's March fiscal year-end puts its most recent annual report 275 days behind
a Q4 2025 reporting date — past your six-month line. Four of its cells blank on
your rule rather than any failure of ours, and this recurs every year in the same
two quarters.
