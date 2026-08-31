"""Cell-by-cell coverage report.

The client asked for the shape of the coverage, not the count: "the shape
matters more than the count." A fill rate is not actionable. What is actionable
is knowing, for each empty cell, whether it is empty because the filer does not
publish the figure, because a client decision is outstanding, or because we have
not built the extraction yet -- because only the third kind is work we can do.

So every cell is classified by *who owns the gap*:

    FILLED       the figure is reported, with a confidence grade
    STRUCTURAL   the filer does not publish it, or not on a comparable basis
    CLIENT       blocked on an open decision (a definition, a basis)
    CADENCE      exists, but not for a period inside the staleness window
    OURS         we have not built the extraction, or the evidence was too thin
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..config import ALL_METRICS, METRIC_LABELS
from ..core.models import Confidence, SuppressionReason
from ..pipeline import BenchmarkRun

FILLED = "FILLED"
STRUCTURAL = "STRUCTURAL"
CLIENT = "CLIENT"
CADENCE = "CADENCE"
OURS = "OURS"

# Which bucket each suppression reason falls into, and why it is that bucket.
_OWNER = {
    SuppressionReason.NOT_APPLICABLE: (
        STRUCTURAL,
        "filer does not publish this concept; no extraction would fix it",
    ),
    SuppressionReason.BASIS_DISQUALIFIED: (
        CLIENT,
        "computable, withheld pending a definition the client is deciding",
    ),
    SuppressionReason.CLASS_ATTRIBUTION_FAILED: (
        OURS,
        "N-PORT omits class identifiers, but the annual report's financial "
        "highlights name each class; that extraction is not built yet",
    ),
    SuppressionReason.STALE_BEYOND_LIMIT: (
        CADENCE,
        "figure exists but predates the six-month line",
    ),
    SuppressionReason.INSUFFICIENT_HISTORY: (
        OURS,
        "history depth limited by our download cap, not by availability",
    ),
    SuppressionReason.WINDOW_MISMATCH: (
        STRUCTURAL,
        "filer's tagged history does not span the labelled window",
    ),
    SuppressionReason.NO_CANDIDATE: (
        OURS,
        "extraction not built for this metric on this filer type",
    ),
    SuppressionReason.BELOW_CONFIDENCE_FLOOR: (
        OURS,
        "evidence too thin; needs a second corroborating source",
    ),
}


@dataclass
class CoverageRow:
    fund: str
    metric: str
    status: str
    owner: str
    detail: str
    confidence: str = ""


def coverage_rows(run: BenchmarkRun) -> list[CoverageRow]:
    rows: list[CoverageRow] = []
    for ticker, res in run.results.items():
        for metric in ALL_METRICS:
            rm = res.resolved.get(metric)
            if rm is None:
                continue
            if rm.value is not None:
                rows.append(
                    CoverageRow(
                        fund=ticker,
                        metric=metric,
                        status=FILLED,
                        owner="-",
                        detail=f"{rm.value:,.4g} {rm.unit}",
                        confidence=rm.confidence.value,
                    )
                )
                continue
            reason = rm.suppression.reason if rm.suppression else SuppressionReason.NO_CANDIDATE
            owner, why = _OWNER.get(reason, (OURS, "unclassified"))
            rows.append(
                CoverageRow(
                    fund=ticker,
                    metric=metric,
                    status=reason.value,
                    owner=owner,
                    detail=why,
                )
            )
    return rows


def coverage_frame(run: BenchmarkRun) -> pd.DataFrame:
    return pd.DataFrame([r.__dict__ for r in coverage_rows(run)])


def coverage_markdown(run: BenchmarkRun) -> str:
    rows = coverage_rows(run)
    tickers = list(run.results)
    by_key = {(r.fund, r.metric): r for r in rows}

    filled = [r for r in rows if r.status == FILLED]
    buckets = {b: [r for r in rows if r.owner == b] for b in (OURS, CADENCE, CLIENT, STRUCTURAL)}

    lines = [
        "# Coverage breakdown — cell by cell",
        "",
        f"Reporting quarter {run.anchor.isoformat()}. "
        f"**{len(filled)} of {len(rows)} competitor cells populated.**",
        "",
        "Each empty cell is classified by who owns the gap. Only the OURS rows "
        "are work this system can close; the rest need either a client decision "
        "or a filing that does not exist.",
        "",
        "| | " + " | ".join(tickers) + " |",
        "| --- |" + " --- |" * len(tickers),
    ]
    for metric in ALL_METRICS:
        cells = []
        for t in tickers:
            r = by_key.get((t, metric))
            if r is None:
                cells.append("-")
            elif r.status == FILLED:
                cells.append(f"**{r.detail}** ({r.confidence})")
            else:
                cells.append(f"_{r.owner}_")
        lines.append(f"| {METRIC_LABELS[metric]} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "## Where the gaps sit",
        "",
        "| Owner | Cells | Meaning |",
        "| --- | --- | --- |",
        f"| FILLED | {len(filled)} | reported with a confidence grade |",
        f"| OURS | {len(buckets[OURS])} | extraction we have not built, or evidence too thin |",
        f"| CADENCE | {len(buckets[CADENCE])} | figure exists but falls outside the six-month window |",
        f"| CLIENT | {len(buckets[CLIENT])} | computable, withheld pending a client decision |",
        f"| STRUCTURAL | {len(buckets[STRUCTURAL])} | the filer does not publish it; no work would fix it |",
        "",
    ]

    for bucket, heading in (
        (OURS, "Ours to close"),
        (CADENCE, "Cadence-limited"),
        (CLIENT, "Blocked on a client decision"),
        (STRUCTURAL, "Structural — no work would fix these"),
    ):
        entries = buckets[bucket]
        if not entries:
            continue
        lines += [f"### {heading} ({len(entries)})", ""]
        for r in sorted(entries, key=lambda x: (x.fund, x.metric)):
            lines.append(
                f"- **{r.fund} — {METRIC_LABELS[r.metric]}** [{r.status}]: {r.detail}"
            )
        lines.append("")

    by_conf: dict[str, int] = {}
    for r in filled:
        by_conf[r.confidence] = by_conf.get(r.confidence, 0) + 1
    lines += [
        "## Confidence of what is populated",
        "",
        "| Grade | Cells |",
        "| --- | --- |",
    ]
    for grade in (Confidence.HIGH, Confidence.MEDIUM, Confidence.LOW):
        lines.append(f"| {grade.value} | {by_conf.get(grade.value, 0)} |")
    return "\n".join(lines)
