"""Turning resolved metrics into board-table cells.

This is the boundary between diagnosis and presentation. Upstream, a blank
carries a `SuppressionReason` -- granular, engineering-facing, and emitted by
whichever extractor gave up. Here it becomes a `ReasonCode`, which is what a PM
actually reads on the slide.

The mapping is deliberately total and deliberately loud. An unmapped reason
raises rather than falling back to a generic blank, because a generic blank is
indistinguishable from a broken pipeline -- and the whole premise of the
deliverable is that a blank explains itself well enough to answer the question
it provokes.
"""

from __future__ import annotations

from datetime import date

from ..config import Fund, METRIC_UNITS, M_RETURN_1Y, M_RETURN_3Y, M_RETURN_5Y
from ..core import temporal
from ..core.models import (
    Cell,
    Candidate,
    ReasonCode,
    ResolvedMetric,
    ShareClass,
    Suppression,
    SuppressionReason,
)

# Diagnosis -> presentation. Every label on the right must be true of every
# case that lands there; see ReasonCode's docstring for the bug that rule fixes.
REASON_MAP: dict[SuppressionReason, ReasonCode] = {
    SuppressionReason.NOT_APPLICABLE: ReasonCode.NOT_APPLICABLE,
    SuppressionReason.NO_CANDIDATE: ReasonCode.NO_VALUE_FOUND,
    # Both mean "the series is too short to answer the question asked". Neither
    # is a filing that is coming: GBDC's 5Y needs the passage of time, and
    # CCLFX's needs us to lift our own N-PORT depth cap. Rendering either as
    # NOT_YET_FILED would tell a PM to wait for something that never arrives.
    SuppressionReason.INSUFFICIENT_HISTORY: ReasonCode.NOT_COMPUTABLE,
    SuppressionReason.WINDOW_MISMATCH: ReasonCode.NOT_COMPUTABLE,
    SuppressionReason.CLASS_ATTRIBUTION_FAILED: ReasonCode.CLASS_UNATTRIBUTED,
    SuppressionReason.STALE_BEYOND_LIMIT: ReasonCode.STALE,
    SuppressionReason.BELOW_CONFIDENCE_FLOOR: ReasonCode.LOW_EVIDENCE,
}

# Added upstream after the first map was written; kept out of the literal above
# so its absence upstream does not break this module at import time.
if hasattr(SuppressionReason, "BASIS_DISQUALIFIED"):
    # Distinct from BASIS_UNCONFIRMED: here the basis is known exactly and
    # fails to measure the metric (TAKIX reporting 0.00 borrowings against
    # $2.2bn of liabilities). "Unconfirmed" would understate that.
    REASON_MAP[SuppressionReason.BASIS_DISQUALIFIED] = ReasonCode.BASIS_NOT_MEASURED


class UnmappedReason(RuntimeError):
    """A new SuppressionReason reached render without a presentation decision."""


def to_reason_code(reason: SuppressionReason) -> ReasonCode:
    try:
        return REASON_MAP[reason]
    except KeyError:
        raise UnmappedReason(
            f"{reason!r} has no ReasonCode. Add it to REASON_MAP with a label "
            f"that is true of every case routed to it -- do not default it."
        ) from None


def format_basis(basis: dict[str, object]) -> str:
    """Human-readable basis statement for the cell.

    Rendered at the cell rather than in a slide footnote, by explicit client
    instruction: "I do not want a PM reading that row and assuming it is on the
    same basis as CCLFX without noticing the footnote."
    """
    if not basis:
        return ""
    parts = []
    for key in sorted(basis):
        value = str(basis[key]).replace("_", " ")
        parts.append(value if key.endswith("_basis") else f"{key.replace('_', ' ')}: {value}")
    return "; ".join(parts)


def pending_class_window(fund: Fund, pending_period: date | None) -> str | None:
    """Projected arrival of a class-level filing that genuinely has not landed.

    `pending_period` must be supplied by the caller, which is the only layer
    that knows whether a class-level filing covering the anchor actually
    exists. Defaulting to None means no promotion, and that default is the
    point: an earlier version promoted every missing interval-fund value to
    NOT_YET_FILED, which would have told a PM to wait for a figure that was
    already filed, or was never coming at all. Safe-by-default beats inferring.

    For the Q4 2025 deck this should essentially never fire: CCLFX's N-CSRS for
    2025-09-30 sits three months inside the anchor. The cadence gap is real but
    bites future quarters.
    """
    if pending_period is None or fund.entity_type != "interval_fund":
        return None
    window = temporal.project_filing_window(_OBSERVED_LAGS.get(fund.ticker, []), pending_period)
    return window.label if window else None


# Lag from period end to filing date, over each filer's own prior N-CSRS
# filings. Taken from the EDGAR *submissions index*, which has one row per
# actual filing.
#
# Do not recompute these from companyfacts. A period first appears there in
# whichever filing mentions it earliest, which for older periods is a
# comparative restatement inside a much later report: GBDC's 2020-09-30 shows
# a 782-day "lag" that way, against a true 10-K lag near 50 days. Projections
# built on that are wrong in the direction that makes us look worse than we
# are.
_OBSERVED_LAGS: dict[str, list[int]] = {
    "CCLFX": [66, 70, 70, 68, 70, 66, 70],
    "TAKIX": [52, 59, 68, 60, 58, 66, 55, 62, 59],
}


# Metrics where deck footnote 3 asserts an institutional-class figure. Lara made
# this a hard requirement: a blended fund-level number understates fee drag and
# flatters the competitor, and a cell contradicting the footnote is the exact
# discrepancy she said a PM would catch. Whether a labelled fund-level figure is
# acceptable as a named fallback is with the CIO; until he rules, it blanks.
CLASS_REQUIRED_METRICS = frozenset({M_RETURN_1Y, M_RETURN_3Y, M_RETURN_5Y})


def violates_class_requirement(fund: Fund, metric: str, basis: str) -> bool:
    return (
        fund.entity_type == "interval_fund"
        and metric in CLASS_REQUIRED_METRICS
        and "fund level" in basis.lower()
    )


def blank_cell(
    fund: Fund,
    metric: str,
    suppression: Suppression,
    pending_period: date | None = None,
) -> Cell:
    """Build the blank, with the reason and whatever detail makes it answerable."""
    code = to_reason_code(suppression.reason)

    # A missing class-level figure is only NOT_YET_FILED when a filing really is
    # pending. Promotion is narrow on purpose: everything else keeps the reason
    # its extractor diagnosed.
    detail = suppression.detail
    if code is ReasonCode.NO_VALUE_FOUND:
        window = pending_class_window(fund, pending_period)
        if window:
            code = ReasonCode.NOT_YET_FILED
            detail = window

    if not detail and suppression.coverage_label:
        detail = suppression.coverage_label
    elif suppression.coverage_label and suppression.coverage_label not in detail:
        detail = f"{detail}; {suppression.coverage_label}" if detail else suppression.coverage_label

    return Cell.blank(
        fund.ticker,
        metric,
        code,
        detail=detail,
        as_of=suppression.as_of,
        share_class=_share_class(fund),
    )


def _share_class(fund: Fund) -> ShareClass:
    if fund.entity_type == "interval_fund":
        return ShareClass.INSTITUTIONAL
    return ShareClass.NOT_APPLICABLE


def build_cell(
    fund: Fund,
    metric: str,
    resolved: ResolvedMetric | None,
    reference_basis: str = "",
    pending_period: date | None = None,
) -> Cell:
    """One board-table cell, filled or blank, never bare."""
    if resolved is None:
        return Cell.blank(fund.ticker, metric, ReasonCode.NO_VALUE_FOUND,
                          share_class=_share_class(fund))
    if resolved.value is None:
        suppression = resolved.suppression or Suppression(
            fund_ticker=fund.ticker,
            metric=metric,
            reason=SuppressionReason.NO_CANDIDATE,
            detail="",
        )
        return blank_cell(fund, metric, suppression, pending_period)

    chosen: Candidate | None = resolved.chosen
    basis = format_basis(chosen.basis if chosen else {})
    if violates_class_requirement(fund, metric, basis):
        # Enforced here rather than upstream: this is a question about whether
        # the cell matches what the deck claims about itself, which is a
        # presentation question. The value is not lost -- it stays in the audit
        # trail, and flipping this to a marked fallback is one branch if the
        # CIO allows it.
        return Cell.blank(
            fund.ticker, metric, ReasonCode.WRONG_SHARE_CLASS,
            detail=f"{basis}; institutional class required by deck footnote 3",
            as_of=chosen.as_of if chosen else None,
            share_class=ShareClass.FUND_LEVEL,
        )
    return Cell.filled(
        resolved,
        basis=basis or "as reported",
        share_class=_share_class(fund),
        as_of=chosen.as_of if chosen else None,
        divergent=bool(reference_basis) and basis != reference_basis,
    )
