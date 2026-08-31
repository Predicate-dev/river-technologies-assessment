"""Anchoring, staleness, and projected filing windows.

The client settled two things that live here:

  * The clock runs from the quarter the deck is reporting, NOT from today.
    Apex's own data ends Q4 2025; anchoring on the run date would blank the
    client's own column under the client's own staleness rule while the peers
    populated from mid-2026 N-PORT filings.
  * Six months is the staleness line. Past it the cell blanks rather than
    showing an old number: "I would rather explain a blank than defend a stale
    number that moved materially in the interim."

A candidate is *eligible* if its period ends on or before the anchor, however
late it was filed. TAKIX's N-CSR for 2025-12-31 was filed 2026-02-27; for a
Q4 2025 deck prepared today that is the correct figure, not a future one.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from ..config import get_fund
from .models import Candidate, Suppression, SuppressionLog, SuppressionReason

# The six-month line is the client's, and it is defined once, in confidence.py,
# alongside the continuous freshness factor it is deliberately separate from.
# Re-declaring it here would be two sources of truth for a client-set rule --
# exactly the divergence that produces a number nobody can defend.
from .confidence import STALE_LIMIT_DAYS as STALENESS_LIMIT_DAYS  # noqa: E402

# The quarter the deck reports. Apex's own data ends here (data/
# apex_ridge_fund_data.csv, last row "Q4 2025").
DEFAULT_ANCHOR = date(2025, 12, 31)


def is_eligible(period_end: date | None, anchor: date = DEFAULT_ANCHOR) -> bool:
    """A figure may be used only if its period closed on or before the anchor."""
    return period_end is not None and period_end <= anchor


def age_days(period_end: date, anchor: date = DEFAULT_ANCHOR) -> int:
    return (anchor - period_end).days


def is_stale(period_end: date, anchor: date = DEFAULT_ANCHOR) -> bool:
    return age_days(period_end, anchor) > STALENESS_LIMIT_DAYS


@dataclass(frozen=True)
class FilingWindow:
    """Projected arrival of a filing that does not exist yet.

    Derived from the filer's own history rather than a hardcoded rule: lag from
    period end to filing date, over that filer's prior filings of the same form.
    Observed lags are tight (CCLFX N-CSRS 66-70d over 7 filings), which is what
    makes the projection worth showing a PM at all.
    """

    period_end: date
    earliest: date
    latest: date
    n_observations: int

    @property
    def label(self) -> str:
        if self.earliest.strftime("%b %Y") == self.latest.strftime("%b %Y"):
            return f"expected {self.earliest.strftime('%b %Y')}"
        return (
            f"expected {self.earliest.strftime('%b')}-{self.latest.strftime('%b %Y')}"
        )


def project_filing_window(
    lags_days: list[int], next_period_end: date
) -> FilingWindow | None:
    """Project when a form covering `next_period_end` should arrive.

    Uses the observed min/max lag rather than a mean: the client's whole
    posture is that an overconfident number is worse than an honest range.
    """
    if not lags_days:
        return None
    return FilingWindow(
        period_end=next_period_end,
        earliest=next_period_end + timedelta(days=min(lags_days)),
        latest=next_period_end + timedelta(days=max(lags_days)),
        n_observations=len(lags_days),
    )


def next_period_end(ticker: str, after: date) -> date:
    """Next class-level reporting period end for a fund, given its fiscal year.

    Interval funds report at class level only semi-annually (N-CSRS) and
    annually (N-CSR), which is the cadence gap behind CCLFX's structural blank.
    """
    fye_month, fye_day = (int(x) for x in get_fund(ticker).fiscal_year_end.split("-"))
    # Semi-annual falls six months off the fiscal year end. Both periods land on
    # a month end, and the fiscal day-of-month does not always exist in the
    #other month (a 03-31 year end pairs with 09-30, not 09-31).
    semi_month = fye_month - 6 if fye_month > 6 else fye_month + 6
    candidates: list[date] = []
    for year in (after.year - 1, after.year, after.year + 1):
        candidates.append(date(year, fye_month, min(fye_day, calendar.monthrange(year, fye_month)[1])))
        semi_year = year if fye_month > 6 else year - 1
        candidates.append(
            date(semi_year, semi_month, calendar.monthrange(semi_year, semi_month)[1])
        )
    return min(c for c in candidates if c > after)


def filter_eligible(
    candidates: list[Candidate],
    anchor: date = DEFAULT_ANCHOR,
    notices: SuppressionLog | None = None,
) -> list[Candidate]:
    """Drop candidates whose reporting period closes after the anchor.

    Without this the deck silently compares peers against a later reality than
    Apex's own column: CCLFX and TAKIX file N-PORT through 2026-06-30 while
    Apex's data ends 2025-12-31, so a Q4 2025 board deck would show peers on
    six months of newer information and read as a like-for-like comparison.
    That is a worse failure than a blank, because nothing on the slide reveals
    it.

    Eligibility is about the period a figure *covers*, not when it was filed.
    A TAKIX N-CSR for 2025-12-31 filed in February 2026 is the correct figure
    for a Q4 2025 deck; a June 2026 N-PORT is not, however early it arrived.

    Where filtering removes every candidate for a metric, a notice is recorded
    so the blank says the figures exist but postdate the anchor -- which is a
    materially different statement from "we found nothing".
    """
    eligible: list[Candidate] = []
    dropped: dict[tuple[str, str], list[Candidate]] = {}
    for cand in candidates:
        period_end = cand.as_of or cand.provenance.period_end
        if is_eligible(period_end, anchor):
            eligible.append(cand)
        else:
            dropped.setdefault((cand.fund_ticker, cand.metric), []).append(cand)

    if notices is not None:
        surviving = {(c.fund_ticker, c.metric) for c in eligible}
        for key, lost in dropped.items():
            if key in surviving:
                continue  # an eligible figure remains; nothing to explain
            ticker, metric = key
            earliest = min(
                (c.as_of or c.provenance.period_end for c in lost if c.as_of or c.provenance.period_end),
                default=None,
            )
            notices.add(
                Suppression(
                    fund_ticker=ticker,
                    metric=metric,
                    reason=SuppressionReason.NO_CANDIDATE,
                    detail=(
                        "no figure covering a period on or before the "
                        f"{anchor.isoformat()} reporting quarter"
                    ),
                    as_of=earliest,
                    internal_note=(
                        f"{len(lost)} candidate(s) found but every reporting period "
                        f"closes after the anchor (earliest {earliest}); excluded to "
                        "keep the peer columns on the same reporting quarter as Apex "
                        "Ridge. Not a source gap -- an alignment exclusion."
                    ),
                )
            )
    return eligible
