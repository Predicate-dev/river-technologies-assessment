"""Board table and audit trail.

Two outputs, deliberately separate:

  * **The board table** reproduces the layout the PMs already read
    (`docs/board_deck_excerpt.md`), one column per fund. Every filled cell
    carries its confidence and as-of date; every blank carries its reason.
    Nothing on this table requires the reader to look up a footnote to know
    what basis a number is on -- that was an explicit client ruling, and the
    existing deck's bottom-of-slide footnotes are the failure mode it targets.

  * **The audit trail** is one row per *candidate*, not per reported value:
    every figure the pipeline found, whether or not it won, with its
    provenance, its transforms, its flags and the score inputs. This is what a
    compliance reviewer or the board's questioner actually needs, and it is the
    reason a rejected value is never simply discarded.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from ..config import ALL_METRICS, METRIC_LABELS, Fund
from ..core.models import Cell, Confidence, ReasonCode, ShareClass
from ..pipeline import BenchmarkRun
from .cells import build_cell, format_basis

APEX_COLUMN = "Apex Ridge"

# Apex's own metrics, mapped to the CSV columns they come from.
APEX_CSV_COLUMNS = {
    "net_return_1y_pct": "net_return_1y_pct",
    "net_return_3y_pct": "net_return_3y_pct",
    "net_return_5y_pct": "net_return_5y_pct",
    "management_fee_pct": "management_fee_pct",
    "incentive_fee_pct": "incentive_fee_pct",
    "incentive_hurdle_pct": "incentive_hurdle_pct",
    "nav_per_share_usd": "nav_per_share_usd",
    "leverage_ratio_dte": "leverage_ratio_dte",
    "distribution_yield_pct": "distribution_yield_pct",
}

CONFIDENCE_MARK = {
    Confidence.HIGH: "High",
    Confidence.MEDIUM: "Med",
    Confidence.LOW: "Low",
    Confidence.SUPPRESSED: "--",
}


def format_value(value: float | None, unit: str) -> str:
    if value is None:
        return "--"
    if unit == "pct":
        return f"{value:.2f}%"
    if unit == "ratio":
        return f"{value:.2f}x"
    if unit == "usd":
        return f"${value:,.2f}"
    return f"{value:,.4g}"


def _cell_text(cell: Cell) -> str:
    """One table cell: the number with its evidence, or the blank with its reason."""
    if cell.value is None:
        reason = cell.reason.label if cell.reason else "not available"
        detail = f" -- {cell.detail}" if cell.detail else ""
        return f"_blank: {reason}{detail}_"

    # A fee of zero is a different statement from a measured zero, and "0.00%"
    # invites a PM to read it as a computed figure. Say what it means.
    if cell.value == 0.0 and cell.metric in ("incentive_fee_pct", "incentive_hurdle_pct"):
        parts = ["**none charged**"]
    else:
        parts = [f"**{format_value(cell.value, cell.unit)}**"]
    if cell.confidence is None:
        # Client-supplied figures carry no confidence: we did not extract them
        # and have no evidence to score. Defaulting them to a grade would
        # imply an assessment we never made.
        parts.append("(client data)")
    else:
        parts.append(f"({CONFIDENCE_MARK.get(cell.confidence, '?')})")
    if cell.as_of:
        parts.append(f"as of {cell.as_of.isoformat()}")
    # Basis renders at the cell whenever it diverges from the row's reference,
    # and unconditionally for leverage -- the metric behind the board incident.
    if cell.divergent or cell.metric == "leverage_ratio_dte":
        parts.append(f"[{cell.basis}]")
    if cell.share_class is ShareClass.UNCONFIRMED:
        parts.append("[basis unconfirmed]")
    return " ".join(parts)


def apex_cell(run: BenchmarkRun, metric: str) -> Cell:
    """Apex Ridge's own figure for the anchor quarter.

    Rendered through the same Cell type as the peers, with share class
    UNCONFIRMED: the client could not confirm which class the CSV represents or
    whether the net return is net of both fees. The values are theirs and are
    shown, but the unconfirmed basis is what suppresses derived comparisons.
    """
    column = APEX_CSV_COLUMNS.get(metric)
    unit = "usd" if metric.endswith("_usd") else ("ratio" if metric.endswith("_dte") else "pct")
    if run.apex is None or run.apex.empty or column not in run.apex.columns:
        # A blank must always carry a reason, including on the client's own
        # column: without one the Cell type raises and takes the whole render
        # down, turning a missing CSV column into a total failure.
        return Cell(
            fund_ticker=APEX_COLUMN,
            metric=metric,
            value=None,
            unit=unit,
            as_of=None,
            basis="",
            share_class=ShareClass.UNCONFIRMED,
            reason=ReasonCode.NO_VALUE_FOUND,
            detail="not present in the fund data supplied by Apex Ridge",
        )
    row = run.apex.iloc[-1]
    return Cell(
        fund_ticker=APEX_COLUMN,
        metric=metric,
        value=float(row[column]),
        unit=unit,
        as_of=row["period_end"],
        basis="as supplied by Apex Ridge",
        share_class=ShareClass.UNCONFIRMED,
        confidence=None,
    )


def build_cells(run: BenchmarkRun) -> dict[str, dict[str, Cell]]:
    """metric -> column -> Cell, for every row of the board table."""
    grid: dict[str, dict[str, Cell]] = {}
    for metric in ALL_METRICS:
        row: dict[str, Cell] = {APEX_COLUMN: apex_cell(run, metric)}
        # The reference basis for a row is whichever basis the most funds share;
        # a cell differing from it is what gets marked divergent.
        bases = []
        for res in run.results.values():
            rm = res.resolved.get(metric)
            if rm is not None and rm.value is not None and rm.chosen is not None:
                bases.append(format_basis(rm.chosen.basis))
        reference = max(set(bases), key=bases.count) if bases else ""

        for ticker, res in run.results.items():
            row[ticker] = build_cell(res.fund, metric, res.resolved.get(metric), reference)
        grid[metric] = row
    return grid


# A peer with at most this many populated cells is demoted out of the main
# table and reported as a footnote instead. Lara's ruling on TAKIX: "A column
# with one cell is not a comparison, it is noise, and a PM will ask why it is
# there." The threshold is 1 rather than something more aggressive because a
# demotion is a large silent decision, and she has been explicit that she does
# not want those -- CCLFX at 3 of 9 must keep its column and argue for itself.
# Every demotion is announced in the output; none of them happen quietly.
DEMOTION_MAX_POPULATED = 1


def populated_count(grid: dict[str, dict[str, Cell]], ticker: str) -> int:
    return sum(1 for m in grid if not grid[m][ticker].is_blank)


def partition_columns(grid: dict[str, dict[str, Cell]], tickers: list[str]) -> tuple[list[str], list[str]]:
    """Split peers into table columns and footnote-only entries."""
    kept, demoted = [], []
    for t in tickers:
        (demoted if populated_count(grid, t) <= DEMOTION_MAX_POPULATED else kept).append(t)
    return kept, demoted


def demoted_footnote(grid: dict[str, dict[str, Cell]], ticker: str, run: "BenchmarkRun") -> list[str]:
    """What a demoted peer still owes the reader: what is absent, and why.

    Dropping the column must not drop the information. The zero-borrowings
    finding in particular has to stay visible -- it is a statement about the
    filer's disclosure, not about our extraction.
    """
    fund = run.results[ticker].fund
    n = populated_count(grid, ticker)
    out = [
        "",
        f"### {ticker} — {fund.name}",
        "",
        f"Reported as a footnote rather than a column: {n} of {len(grid)} metrics "
        "populate, which is not enough to support a comparison. Removed from the "
        "table so the row reads honestly, not because the peer was dropped.",
        "",
    ]
    for metric in ALL_METRICS:
        cell = grid[metric][ticker]
        label = METRIC_LABELS.get(metric, metric)
        if cell.is_blank:
            detail = f" — {cell.detail}" if cell.detail else ""
            out.append(f"- **{label}**: not reported. {cell.reason.label}{detail}.")
        else:
            out.append(f"- **{label}**: {_cell_text(cell)}")
    return out


def board_markdown(run: BenchmarkRun) -> str:
    """The board table, in the layout the PMs already read."""
    grid = build_cells(run)
    kept, demoted = partition_columns(grid, list(run.results))
    columns = [APEX_COLUMN] + kept
    lines = [
        "# Peer benchmarking — private credit comparables",
        "",
        f"**Reporting quarter:** {run.anchor.isoformat()} (Q4 2025). "
        "Every figure is as reported by the filer for a period ending on or "
        "before that date.",
        "",
        "Confidence: High / Med / Low. A blank cell states why it is blank; it is "
        "never an extraction that quietly failed.",
        "",
        "| Metric | " + " | ".join(columns) + " |",
        "| --- |" + " --- |" * len(columns),
    ]
    for metric in ALL_METRICS:
        cells = [_cell_text(grid[metric][c]) for c in columns]
        lines.append(f"| {METRIC_LABELS[metric]} | " + " | ".join(cells) + " |")

    if demoted:
        names = ", ".join(demoted)
        lines += [
            "",
            f"_{names} {'is' if len(demoted) == 1 else 'are'} reported below "
            "rather than as a column: too few metrics populate to support a "
            "comparison. Nothing is hidden — every metric is listed with its "
            "reason._",
        ]
        lines += ["", "## Peers reported as footnotes", ""]
        for ticker in demoted:
            lines += demoted_footnote(grid, ticker, run)

    lines += ["", "## Source conflicts resolved in this run", ""]
    conflicts = run.conflicts
    if not conflicts:
        lines.append("_No material source conflicts in this run._")
    for ticker, rm in conflicts:
        lines.append(
            f"- **{ticker} — {METRIC_LABELS[rm.metric]}**: "
            f"candidates {', '.join(f'{v:g}' for v in rm.conflict.values)} "
            f"(spread {rm.conflict.spread_pct:.0f}%). Resolved to "
            f"**{rm.conflict.resolution}**. {rm.conflict.rationale}"
        )

    lines += ["", "## Blank cells", ""]
    notices = run.notices.all()
    if not notices:
        lines.append("_No suppressed cells._")
    for n in sorted(notices, key=lambda x: (x.fund_ticker, x.metric)):
        lines.append(
            f"- **{n.fund_ticker} — {METRIC_LABELS.get(n.metric, n.metric)}** "
            f"[{n.reason.value}]: {n.cell_label}"
        )

    lines += [
        "",
        "---",
        "",
        "Apex Ridge's own column renders with an unconfirmed basis: the share "
        "class and fee treatment behind the supplied figures are not yet "
        "established, so peer-minus-Apex deltas are withheld. A delta between "
        "two numbers of unknown basis is precisely the confidently-wrong figure "
        "this system exists to prevent.",
    ]
    return "\n".join(lines)


def audit_frame(run: BenchmarkRun) -> pd.DataFrame:
    """One row per candidate found, winners and losers alike.

    Rejected candidates are the point: the evidence for why the reported value
    won is only legible if what it beat is on the record.
    """
    rows: list[dict[str, object]] = []
    for ticker, res in run.results.items():
        for metric in ALL_METRICS:
            rm = res.resolved.get(metric)
            if rm is None:
                continue
            considered = [c for c in res.candidates if c.metric == metric]
            for cand in considered:
                chosen = rm.chosen is not None and cand is rm.chosen
                rows.append(
                    {
                        "fund": ticker,
                        "metric": metric,
                        "value": cand.value,
                        "unit": cand.unit,
                        "reported": chosen and rm.value is not None,
                        "outcome": (
                            "reported"
                            if (chosen and rm.value is not None)
                            else ("resolved_then_suppressed" if chosen else "rejected")
                        ),
                        "confidence": rm.confidence.value if chosen else "",
                        "score": round(rm.score, 4) if chosen else "",
                        "source_tier": cand.tier.value,
                        "basis": cand.basis_key,
                        "as_of": cand.as_of.isoformat() if cand.as_of else "",
                        "form": cand.provenance.form_type,
                        "accession": cand.provenance.accession,
                        "locator": cand.provenance.locator,
                        "document_url": cand.provenance.document_url,
                        "excerpt": cand.provenance.excerpt,
                        "transforms": "; ".join(cand.transforms),
                        "flags": "; ".join(cand.flags),
                        "score_inputs": (
                            "; ".join(f"{k}={v}" for k, v in rm.score_inputs.items())
                            if chosen
                            else ""
                        ),
                    }
                )
            if not considered:
                rows.append(
                    {
                        "fund": ticker,
                        "metric": metric,
                        "value": None,
                        "unit": rm.unit,
                        "reported": False,
                        "outcome": "no_candidate",
                        "confidence": rm.confidence.value,
                        "score": round(rm.score, 4),
                        "source_tier": "",
                        "basis": "",
                        "as_of": "",
                        "form": "",
                        "accession": "",
                        "locator": "",
                        "document_url": "",
                        "excerpt": "",
                        "transforms": "",
                        "flags": "",
                        "score_inputs": (
                            rm.suppression.internal_note if rm.suppression else ""
                        ),
                    }
                )
    return pd.DataFrame(rows)


def write_outputs(run: BenchmarkRun, outdir, client=None) -> dict[str, str]:
    from pathlib import Path

    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    from .coverage import coverage_frame, coverage_markdown

    board = out / "benchmark_table.md"
    audit = out / "audit_trail.csv"
    coverage = out / "coverage_breakdown.md"
    board.write_text(board_markdown(run))
    audit_frame(run).to_csv(audit, index=False)
    coverage.write_text(coverage_markdown(run))
    coverage_frame(run).to_csv(out / "coverage_breakdown.csv", index=False)

    from .comparison import comparison_markdown

    versus = out / "apex_vs_peers.md"
    versus.write_text(comparison_markdown(run))

    try:
        from .word import build_document

        paths_word = build_document(run, out / "benchmark_report.docx")
    except Exception as exc:  # python-docx optional; Markdown outputs stand alone
        import logging

        logging.getLogger(__name__).warning("Word output skipped: %s", exc)
        paths_word = None

    paths = {
        "board": str(board),
        "audit": str(audit),
        "coverage": str(coverage),
        "comparison": str(versus),
    }
    if paths_word:
        paths["word"] = paths_word
    if client is not None:
        from .trend import build_trend, trend_frame, trend_markdown

        series = build_trend(run, client)
        trend_md = out / "nav_trend.md"
        trend_md.write_text(trend_markdown(run, series))
        trend_frame(series).to_csv(out / "nav_trend.csv", index=False)
        paths["trend"] = str(trend_md)
    return paths
