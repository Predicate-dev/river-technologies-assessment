# Competitor benchmarking — solution brief

**For:** CIO and Managing Partner, Apex Ridge Capital Partners
**Subject:** Automating the quarterly peer benchmarking pack

---

## The short version

We built a system that pulls your four competitors' filings directly from the
SEC, extracts the eight benchmark metrics, and produces the peer table your PMs
already read — with two things the current process cannot give you. Every number
carries a citation to the exact filing and location it came from. Every number
carries a confidence grade we can defend. And where the evidence does not
support a number, the cell is **blank with a stated reason** rather than filled
with a figure nobody can stand behind.

The quarterly cycle goes from 6–8 hours of analyst transcription to a few
minutes of machine time plus a review pass over the exceptions. More
importantly, it changes what the pack *is*: today it is a set of transcribed
numbers whose derivation lives in an analyst's memory; afterwards it is a set of
numbers each of which can be traced back to a filing in one click.

## What changes about the quarterly workflow

**Today.** An analyst opens EDGAR, finds each competitor's most recent filings,
reads 100–200+ pages, and hand-keys figures into a locked Excel template. The
judgment calls — which of several similar-looking numbers in a 200-page document
is the right one — happen silently and are not recorded. A misread basis point
on a leverage ratio reached a board deck last year and was caught only
afterwards.

**Afterwards.** The system produces the table, the citations, and an exception
list. The analyst's job shifts from transcription to reviewing the exceptions:
the cells where sources disagreed, and the cells left blank. That is a smaller
job, and it is the part where their judgment is actually worth something.

What does *not* change: a person still signs off. This replaces the typing, not
the review.

## The judgment calls, in business terms

**We made the system prefer a gap to a guess.** This follows your stated rule
directly — a blank cell generates a question you can answer; a confident wrong
number generates one you cannot. Of 36 competitor cells in the current run, 25
populate and 11 are blank. Each blank is classified by who owns it: three are
ours to close, three are figures that exist but fall outside your six-month
staleness line, one is withheld pending your leverage definition, and four are
figures the competitor genuinely does not publish. No process — automated or
manual — could have filled that last group without inventing a comparison.

**A caution on comparing this to the old pack.** Do not assume the manual deck
was accurate because it had no blanks. This system is not adding gaps to a
previously complete picture; it is producing the first honest accounting of
which cells were ever actually sourced from a filing. Some cells that have been
filled by hand every quarter appear to have come from fund websites and
investor-relations pages rather than SEC filings — which is not wrong, but it is
a different evidentiary standard, and until now nothing recorded which was
which.

**We refused to substitute near-metrics.** KREF is described in the brief as a
BDC. It is a mortgage REIT: it publishes no fund-style net return, and its
management fee is struck on a different base than the credit funds'. We could
have filled its return rows with total shareholder return, and the table would
have looked complete. Those rows are blank instead, labelled as not reported on
a comparable basis. **A complete-looking table that compares two different things
is the failure this system exists to prevent.**

**We separated "the sources disagree" from "the definition is open."** Two of the
funds' filings contradict themselves in ways the system resolves and logs — see
below. But where the *question* is open rather than the data, the system holds
the number back. TAKIX reports zero borrowings while carrying $2.2bn of
liabilities; a leverage figure is computable, but which figure is right depends
on the regulatory-versus-economic definition currently with your CIO. The system
will not answer that question by quietly picking one.

## What it caught that the manual process would not have

These are from the live run, not hypotheticals:

- **GBDC's own tagged data reports its management fee as 0.021%.** The tag is
  technically correct — it comes from a different offering document — but the
  number is wrong for this purpose. The true rate is 1.0%. An automated system
  trusting "official structured data" would have shipped it.
- **GBDC's annual report states both its old and its current fee in one
  sentence** — "reduced from 1.375% to 1.0%", and "from 20.0% to 15.0%". Reading
  the first number rather than the second is precisely the misread that reached
  your board last year. The system now resolves to the current rate and records
  why, as a tested case rather than a matter of analyst attention.
- **TAKIX's prospectus states a management fee of 1.50% that was retired in
  2020,** a few paragraphs from the current 1.00%. Same hazard, different wording.
- **A distribution quarter that BDCs never report separately** was understating
  GBDC's one-year return by 265 basis points until we reconstructed it.
- **KREF's management fee is quoted quarterly**, on a different asset base than
  the credit funds use. Read as printed it is 0.375%, against peers quoting
  around 1.0% annually. It is 1.50% a year, and it is now labelled with the base
  it is struck on so nobody reads it as like-for-like.
- **TAKIX's prospectus quotes a management fee that was retired in 2020,** a few
  paragraphs from the current one.

Each of these is a number a careful analyst could have got wrong, and none of
them announces itself.

## Confidence, and why you can defend it

We asked to reconcile our output against a prior quarter's manual pack and were
told, correctly, that live fund data cannot leave the firm without a compliance
sign-off. So this has never been checked against an external reference, and we
would rather say that plainly than let the confidence grades imply otherwise.
The manual process was your only source, and there is no independent answer key.
The system therefore does not claim accuracy. It reports **evidence**: how the number was obtained, whether
independently constructed versions of it agree, how current the underlying
filing is, and any specific problem observed while extracting it. A grade of
High means several independent routes to the number converged. Low means one
route and no corroboration.

This is the part that survives a board question. "The model said so" does not.
Nothing in the system asks a model how confident it is.

## Production rollout

The prototype runs today against live SEC data. To make it operational we would
expect roughly:

1. **Close the open definitional questions** (2–3 weeks, mostly your time).
   Chiefly the leverage definition, the basis of your own reported figures, and
   compliance sign-off on model-assisted extraction. Most are configuration
   switches by design — deliberately, so that answers arriving late do not
   trigger rework.
2. **Settle what is in scope as a source** (1 week, your analysts). If some
   cells have only ever come from fund websites or IR pages, they cannot be
   closed by any amount of filing extraction. Our recommendation is that such
   sources, if adopted, carry a distinct and visibly lower confidence tier —
   they have no accession number, no immutable version and no audit trail a
   compliance reviewer could follow years later.
3. **Extend coverage** (1–2 weeks). Three cells remain within reach on the
   existing approach.
4. **Operationalise** (1–2 weeks). Scheduled quarterly runs timed to your
   two-weeks-after-close cycle, an alert when a metric that populated last
   quarter stops populating, and the review interface your analyst works
   through.

The ongoing risk worth naming: **filers change their wording, and extraction
that depends on wording will quietly stop matching.** We designed for this — a
failed match produces a blank with a reason, never a wrong number — but it means
this is a system that needs an owner, not one you install and forget. The
quarterly review pass is what keeps it honest.

## Tradeoffs we made

Given the timeline, we chose depth of evidence over breadth of coverage. A
system that filled all 36 cells with unverified numbers was achievable in the
time available. We judged it worth less to you than 25 cells you can take into a
board meeting and defend, plus an explicit account of who owns each of the 11
that are empty.

We also deliberately did not build for scope we were told might come. The fund
and metric list is configuration, so adding a fund of a type we already handle
is cheap. Building a general plug-in framework for funds nobody has named yet
would have consumed the time that went into the confidence model.

One consequence of your own rules is worth seeing before it surprises you.
CCLFX has a March fiscal year-end, which puts its most recent annual report 275
days behind a Q4 2025 reporting date — past your six-month staleness line. Three
of its cells therefore blank on your rule rather than on any failure of ours.
That is the live case for the labelled fund-level fallback now with your CIO,
and it will recur every year in the same two quarters.
