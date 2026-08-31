# Competitor benchmarking — solution brief

**For:** CIO and Managing Partner, Apex Ridge Capital Partners

---

## What we built

A system that pulls your four competitors' filings directly from the SEC,
extracts the eight benchmark metrics, and produces the peer table your PMs
already read — with two things the current process cannot give you. Every number
cites the exact filing and location it came from. Every number carries a
confidence grade we can defend. Where the evidence does not support a number,
the cell is **blank with a stated reason** rather than filled with a figure
nobody can stand behind.

The quarterly cycle goes from 6–8 hours of analyst transcription to minutes of
machine time plus a review pass over the exceptions. More importantly, it changes
what the pack *is*: today it is transcribed numbers whose derivation lives in an
analyst's memory; afterwards each one traces back to a filing in one click.

## What changes

**Today** an analyst reads 100–200+ pages per competitor and hand-keys figures
into Excel. The judgment calls — which of several similar-looking numbers is the
right one — happen silently and are never recorded. A misread basis point on a
leverage ratio reached a board deck last year.

**Afterwards** the analyst reviews exceptions: the cells where sources disagreed,
and the cells left blank. Smaller work, and the part where their judgment is
actually worth something. A person still signs off. This replaces the typing, not
the review.

## The judgment calls, in business terms

**We made the system prefer a gap to a guess** — your rule, applied literally. Of
36 competitor cells, 25 populate and 11 are blank. Each blank is attributed: three
are ours to close, three are figures that exist but fall outside your six-month
staleness line, one is withheld pending your leverage definition, four are figures
the competitor genuinely does not publish.

**A caution before you compare this to the old pack.** Do not assume the manual
deck was accurate because it had no blanks. This is not adding gaps to a complete
picture; it is the first honest accounting of which cells were ever actually
sourced from a filing. Some cells filled by hand every quarter appear to have come
from fund websites and IR pages rather than SEC filings — not wrong, but a
different evidentiary standard, and nothing recorded which was which.

**We refused to substitute near-metrics.** KREF is described as a BDC; it is a
mortgage REIT, publishing no fund-style net return and striking its fee on a
different base. We could have filled its return rows with total shareholder return
and the table would have looked complete. Those rows are blank and labelled
instead. *A complete-looking table comparing two different things is the failure
this system exists to prevent.*

**We separated "sources disagree" from "the definition is open."** TAKIX reports
zero borrowings while carrying $2.2bn of liabilities. A leverage figure is
computable, but which one is right depends on a definition now with your CIO. The
system will not answer that question by quietly picking one.

## What it caught

From the live run, not hypotheticals:

- **GBDC's own tagged data reports its management fee as 0.021%** — technically
  correct, from a different offering document, and wrong for this purpose. The
  true rate is 1.0%. A system trusting "official structured data" ships it.
- **GBDC's annual report states both its old and current fee in one sentence** —
  "reduced from 1.375% to 1.0%", "from 20.0% to 15.0%". Reading the first rather
  than the second is precisely the misread that reached your board.
- **TAKIX's prospectus quotes a fee retired in 2020**, paragraphs from the current
  one.
- **KREF's management fee is quoted quarterly** on a different asset base. Read as
  printed it is 0.375% against peers quoting ~1.0%. It is 1.50% a year.
- **A distribution quarter BDCs never report separately** understated GBDC's
  one-year return by 265 basis points.

Each is a number a careful analyst could get wrong, and none announces itself.

## Confidence

We asked to reconcile our output against a prior quarter's manual pack and were
told — correctly — that live fund data cannot leave the firm without compliance
sign-off. So this has never been checked against an external reference, and we
would rather say so plainly than let the grades imply otherwise. There is no
answer key; the manual process was your only source.

The system therefore reports **evidence**, not accuracy: how the number was
obtained, whether independently constructed versions agree, how current the filing
is, and any specific problem seen while extracting. High means several independent
routes converged. Low means one route, unchecked. That survives a board question.
"The model said so" does not, and nothing here asks a model how confident it is.

## Production rollout

1. **Close the definitional questions** (2–3 weeks, mostly your time) — the
   leverage definition, the basis of your own figures, compliance sign-off on
   model-assisted extraction. Most are configuration switches by design, so late
   answers do not trigger rework.
2. **Settle what counts as a source** (1 week, your analysts). Cells that only
   ever came from fund websites cannot be closed by any amount of filing
   extraction. If such sources are adopted, they should carry a distinct and
   visibly lower confidence tier — no accession number, no immutable version, no
   audit trail a reviewer could follow years later.
3. **Extend coverage** (1–2 weeks). Three cells remain within reach.
4. **Operationalise** (1–2 weeks). Quarterly runs timed to your two-weeks-after-
   close cycle, an alert when a metric that populated last quarter stops, and the
   analyst's review interface.

The ongoing risk: **filers change wording, and extraction that depends on wording
quietly stops matching.** We designed for it — a failed match produces a blank
with a reason, never a wrong number — but this needs an owner, not an install.

## Tradeoffs

We chose depth of evidence over breadth of coverage. Filling all 36 cells with
unverified numbers was achievable in the time. We judged it worth less than 25
cells you can defend in a board meeting, plus an explicit account of who owns each
of the 11 that are empty.

We also did not build for scope we were told might come. Adding a fund of a type
already handled is configuration; a general plug-in framework for funds nobody has
named would have consumed the time that went into the confidence model.

One consequence of your own rules is worth seeing before it surprises you. CCLFX's
March fiscal year-end puts its most recent annual report 275 days behind a Q4 2025
reporting date — past your six-month line. Three of its cells blank on your rule
rather than on any failure of ours, and this will recur every year in the same two
quarters. It is the live case for the labelled fund-level fallback now with your
CIO.
