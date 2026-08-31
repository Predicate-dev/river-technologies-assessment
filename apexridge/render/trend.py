"""NAV per share trend, on a common semi-annual footing.

The metric spec asks for a trend over the last eight quarters. Quarterly is not
achievable across this peer set: class-level NAV for the two interval funds
exists only in N-CSR and N-CSRS, i.e. semi-annually, and N-PORT carries no
per-share field at all. The client ruled on the resolution -- put every fund on
a common semi-annual footing rather than plot mixed intervals, because "a
mixed-cadence chart will generate a question from the PMs about why the lines
have different intervals before they get to the numbers."

One honest limit remains and is stated on the output rather than smoothed over:
semi-annual *cadence* is common, but the *dates* are not. Each filer reports on
its own fiscal calendar -- CCLFX at March and September, TAKIX and KREF at June
and December, GBDC at March and September. There is no calendar date on which
all four report. Interpolating onto a shared grid would invent observations no
filer published, so each fund is plotted at its own reporting dates and every
point carries the date it actually represents.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import pandas as pd

from ..config import Fund
from ..core.models import Candidate
from ..edgar import EdgarClient
from ..pipeline import BenchmarkRun
from ..sources import highlights
from ..sources.xbrl import XbrlFacts

log = logging.getLogger(__name__)

TREND_QUARTERS = 8  # the spec's window; two years


@dataclass
class TrendPoint:
    period_end: date
    nav: float
    source: str


def _semi_annual_months(fund: Fund) -> set[int]:
    """The two months a filer reports at, from its fiscal year end."""
    fye_month = int(fund.fiscal_year_end.split("-")[0])
    other = fye_month - 6 if fye_month > 6 else fye_month + 6
    return {fye_month, other}


def _fiscal_year_end(fund: Fund, year: int) -> date:
    month, day = (int(x) for x in fund.fiscal_year_end.split("-"))
    return date(year, month, day)


def interval_fund_navs(
    fund: Fund, client: EdgarClient, anchor: date, reports: int = 3
) -> list[TrendPoint]:
    """NAV history for an interval fund, from its financial highlights.

    Each annual report carries several prior fiscal years' NAV, and each
    semi-annual report adds its own mid-year point, so a few filings assemble a
    usable series without downloading the whole history.
    """
    tables = highlights.load_tables(fund, client, anchor, per_form=reports)
    chosen = [
        t for t in tables
        if t.share_class.lower().replace(" ", "")
        == fund.institutional_class.lower().replace(" ", "")
    ]
    points: dict[date, TrendPoint] = {}
    for t in chosen:
        for i, (year, nav) in enumerate(zip(t.years, t.nav_end)):
            if nav is None:
                continue
            if i == 0 and not t.is_annual:
                # The semi-annual report's leading column ends at the report
                # date, not at the fiscal year end its header repeats.
                period = t.filing.report_date
            else:
                period = _fiscal_year_end(fund, year)
            if period is None or period > anchor:
                continue
            points.setdefault(period, TrendPoint(period, nav, t.filing.form))
    return sorted(points.values(), key=lambda p: p.period_end)


def xbrl_navs(fund: Fund, client: EdgarClient, anchor: date) -> list[TrendPoint]:
    """NAV history for a 10-K/10-Q filer, downsampled to its semi-annual points."""
    facts = XbrlFacts(fund, client)
    series = facts.series("us-gaap:NetAssetValuePerShare", instant=True)
    if not series:
        # A REIT publishes no NAV; book value per share is the closest analogue
        # and is labelled as such wherever it is rendered.
        equity = facts.series("us-gaap:StockholdersEquity", instant=True)
        shares = {
            f.end: f.val
            for f in facts.series("us-gaap:CommonStockSharesOutstanding", instant=True)
        }
        series = [f for f in equity if f.end in shares and shares[f.end]]
        points = {
            f.end: TrendPoint(f.end, f.val / shares[f.end], "10-Q/10-K (book value)")
            for f in series
            if f.end and f.end <= anchor
        }
    else:
        points = {
            f.end: TrendPoint(f.end, f.val, f.form)
            for f in series
            if f.end and f.end <= anchor
        }
    months = _semi_annual_months(fund)
    return sorted(
        (p for p in points.values() if p.period_end.month in months),
        key=lambda p: p.period_end,
    )


def apex_navs(run: BenchmarkRun) -> list[TrendPoint]:
    """Apex's own NAV, downsampled to semi-annual so the comparison matches."""
    if run.apex is None or run.apex.empty:
        return []
    out = []
    for _, row in run.apex.iterrows():
        pe: date = row["period_end"]
        if pe.month in (6, 12):
            out.append(TrendPoint(pe, float(row["nav_per_share_usd"]), "client data"))
    return out


def build_trend(
    run: BenchmarkRun, client: EdgarClient, quarters: int = TREND_QUARTERS
) -> dict[str, list[TrendPoint]]:
    """fund -> semi-annual NAV series over the trailing window."""
    earliest = date(
        run.anchor.year - quarters // 4, run.anchor.month, run.anchor.day
    )
    out: dict[str, list[TrendPoint]] = {"Apex Ridge": apex_navs(run)}
    for ticker, res in run.results.items():
        fund = res.fund
        try:
            if fund.entity_type == "interval_fund":
                points = interval_fund_navs(fund, client, run.anchor)
            else:
                points = xbrl_navs(fund, client, run.anchor)
        except Exception:
            log.exception("NAV trend failed for %s", ticker)
            points = []
        out[ticker] = [p for p in points if p.period_end >= earliest]
    return {k: v for k, v in out.items()}


def trend_frame(trend: dict[str, list[TrendPoint]]) -> pd.DataFrame:
    rows = [
        {
            "fund": fund,
            "period_end": p.period_end.isoformat(),
            "nav_per_share": round(p.nav, 4),
            "source": p.source,
        }
        for fund, points in trend.items()
        for p in points
    ]
    return pd.DataFrame(rows)


def trend_markdown(run: BenchmarkRun, trend: dict[str, list[TrendPoint]]) -> str:
    lines = [
        "# NAV per share — trend",
        "",
        f"Semi-annual cadence, trailing {TREND_QUARTERS} quarters to "
        f"{run.anchor.isoformat()}.",
        "",
        "**Cadence:** semi-annual for every fund. Quarterly is not available "
        "across the peer set — class-level NAV for CCLFX and TAKIX exists only "
        "in their annual and semi-annual reports, and N-PORT carries no "
        "per-share field.",
        "",
        "**Dates differ by fiscal calendar** and are shown per point rather "
        "than forced onto a shared grid: CCLFX reports at March and September, "
        "TAKIX and KREF at June and December, GBDC at March and September. "
        "Interpolating to a common date would invent observations no filer "
        "published.",
        "",
        "**Drill-down:** GBDC and KREF publish NAV *quarterly* in their 10-Qs, "
        "so a finer series is available for those two on request. No fund in "
        "the set publishes a monthly per-share NAV.",
        "",
    ]
    for fund, points in trend.items():
        if not points:
            lines.append(f"- **{fund}**: no NAV series available in the window.")
            continue
        rendered = ", ".join(
            f"{p.period_end.isoformat()} ${p.nav:,.2f}" for p in points
        )
        note = " _(book value per share, not a fund NAV)_" if "book value" in points[0].source else ""
        lines.append(f"- **{fund}**{note}: {rendered}")
    lines += [
        "",
        "KREF is a mortgage REIT: its per-share figure is GAAP book value, not "
        "an administrator-struck NAV, and the two are not directly comparable.",
    ]
    return "\n".join(lines)
