"""N-PORT adapter for the two non-traded interval funds (CCLFX, TAKIX).

These filers have essentially no usable XBRL -- five or six `cef:` tags, all of
them senior-securities stress figures -- so N-PORT is the only machine-readable
source for them. It is a good one: the schema is fixed, the fields are typed,
and it carries total assets, total liabilities, borrowings by maturity and
counterparty class, and three months of total return per filing.

Practical note: each `primary_doc.xml` is ~8 MB because it embeds the full
holdings schedule, but every field we need appears in the first ~7 KB, before
`<invstOrSecs>`. We truncate there rather than parsing 8 MB of positions.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Iterator

from ..config import M_LEVERAGE, M_RETURN_1Y, M_RETURN_3Y, M_RETURN_5Y, Fund
from ..core.models import (
    Candidate,
    Provenance,
    SourceTier,
    Suppression,
    SuppressionLog,
    SuppressionReason,
)
from ..edgar import EdgarClient, Filing

log = logging.getLogger(__name__)

NS = {"n": "http://www.sec.gov/edgar/nport"}
_HOLDINGS_MARKER = b"<invstOrSecs"

# Borrowing tags in N-PORT fundInfo. Summed, these are the fund's total
# borrowings -- the numerator of a regulatory-style leverage ratio.
BORROW_TAGS = (
    "amtPayOneYrBanksBorr",
    "amtPayOneYrCtrldComp",
    "amtPayOneYrOthAffil",
    "amtPayOneYrOther",
    "amtPayAftOneYrBanksBorr",
    "amtPayAftOneYrCtrldComp",
    "amtPayAftOneYrOthAffil",
    "amtPayAftOneYrOther",
)


def _f(node: ET.Element | None) -> float | None:
    if node is None or node.text is None:
        return None
    try:
        return float(node.text.strip())
    except ValueError:
        return None


def _d(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _month_ends(period_end: date) -> list[date]:
    """The three month-end dates covered by a filing ending `period_end`.

    N-PORT reports rtn1/rtn2/rtn3 for the three months of the reporting
    quarter, oldest first, with rtn3 ending on the report date.
    """
    ends = [period_end]
    cur = period_end
    for _ in range(2):
        first_of_month = cur.replace(day=1)
        cur = first_of_month - timedelta(days=1)
        ends.append(cur)
    return list(reversed(ends))


@dataclass
class NportReport:
    """The header-and-fundInfo slice of one N-PORT filing."""

    filing: Filing
    reg_name: str
    series_name: str
    period_end: date | None
    fiscal_year_end: date | None
    total_assets: float | None
    total_liabilities: float | None
    net_assets: float | None
    borrowings: float | None
    borrowing_breakdown: dict[str, float] = field(default_factory=dict)
    # month_end -> (return_pct, class_id or None)
    monthly_returns: list[tuple[date, float, str | None]] = field(default_factory=list)

    @property
    def raw_url(self) -> str:
        return self.filing.doc_url("primary_doc.xml")


def _parse(filing: Filing, blob: bytes) -> NportReport | None:
    """Parse the header/fundInfo prefix of an N-PORT document.

    Uses a pull parser fed only the bytes before `<invstOrSecs>`: completed
    subtrees emit end-events without the document ever being closed, so we get
    genInfo and fundInfo without parsing 8 MB of holdings and without having to
    guess which tags to synthesise a closing for.
    """
    cut = blob.find(_HOLDINGS_MARKER)
    prefix = blob[:cut] if cut != -1 else blob

    parser = ET.XMLPullParser(["end"])
    gen: ET.Element | None = None
    fund: ET.Element | None = None
    try:
        parser.feed(prefix)
        for _event, el in parser.read_events():
            tag = el.tag.rsplit("}", 1)[-1]
            if tag == "genInfo":
                gen = el
            elif tag == "fundInfo":
                fund = el
    except ET.ParseError as exc:
        log.warning("N-PORT parse failed for %s: %s", filing.accession, exc)
        return None

    if gen is None or fund is None:
        return None

    def g(parent: ET.Element, tag: str) -> ET.Element | None:
        return parent.find(f"n:{tag}", NS)

    # Distinguish "filer reported zero" from "field absent". TAKIX reports an
    # explicit 0.00 in every borrowing field while carrying $2.2bn of total
    # liabilities -- that is a substantive disclosure, not missing data, and
    # collapsing the two would hide it.
    breakdown: dict[str, float] = {}
    reported_any = False
    for tag in BORROW_TAGS:
        v = _f(g(fund, tag))
        if v is None:
            continue
        reported_any = True
        if v:
            breakdown[tag] = v
    borrow_total = sum(breakdown.values()) if reported_any else None

    period_end = _d(gen.findtext("n:repPdDate", namespaces=NS))
    returns: list[tuple[date, float, str | None]] = []
    ri = fund.find("n:returnInfo", NS)
    if ri is not None and period_end:
        ends = _month_ends(period_end)
        rows = ri.findall(".//n:monthlyTotReturn", NS)
        for pos, mtr in enumerate(rows):
            # Multi-class funds emit one row per share class. TAKIX emits seven
            # rows with no classId attribute at all, so the only handle we have
            # is document position -- which is stable within a filing but is NOT
            # a reliable identifier of *which* class. Recorded as a positional
            # series and never presented as a named class.
            cls = mtr.get("classId") or (f"pos{pos}" if len(rows) > 1 else None)
            for i, key in enumerate(("rtn1", "rtn2", "rtn3")):
                raw = mtr.get(key)
                if raw in (None, "", "N/A"):
                    continue
                try:
                    returns.append((ends[i], float(raw), cls))
                except ValueError:
                    continue

    return NportReport(
        filing=filing,
        reg_name=gen.findtext("n:regName", default="", namespaces=NS).strip(),
        series_name=gen.findtext("n:seriesName", default="", namespaces=NS).strip(),
        period_end=period_end,
        fiscal_year_end=_d(gen.findtext("n:repPdEnd", namespaces=NS)),
        total_assets=_f(g(fund, "totAssets")),
        total_liabilities=_f(g(fund, "totLiabs")),
        net_assets=_f(g(fund, "netAssets")),
        borrowings=borrow_total,
        borrowing_breakdown=breakdown,
        monthly_returns=returns,
    )


def load_reports(fund: Fund, client: EdgarClient, limit: int = 8) -> list[NportReport]:
    """Most recent N-PORT reports, oldest first.

    `limit` is a deliberate cost control: each filing is an 8 MB download and
    eight of them cover two years of monthly returns, which is enough for a
    1-year figure. Longer trailing windows come from the annual report's stated
    performance table instead of from 20 more downloads.
    """
    out: list[NportReport] = []
    for filing in client.filings(fund.cik, forms=["NPORT-P"], limit=limit):
        try:
            blob = client.get(filing.doc_url("primary_doc.xml"))
        except Exception:
            log.warning("could not fetch N-PORT %s", filing.accession)
            continue
        rep = _parse(filing, blob)
        if rep:
            out.append(rep)
    out.sort(key=lambda r: r.period_end or date.min)
    return out


def _prov(rep: NportReport, locator: str, excerpt: str) -> Provenance:
    return Provenance(
        fund_ticker="",  # filled by caller
        form_type=rep.filing.form,
        accession=rep.filing.accession,
        filing_date=rep.filing.filing_date,
        period_end=rep.period_end,
        document_url=rep.filing.filing_index_url,
        locator=locator,
        excerpt=excerpt,
    )


def leverage(fund: Fund, reports: list[NportReport]) -> list[Candidate]:
    """Leverage from the most recent N-PORT, on the same two bases as XBRL."""
    if not reports:
        return []
    rep = reports[-1]
    out: list[Candidate] = []
    na = rep.net_assets
    if not na:
        return out

    if rep.borrowings is not None:
        prov = _prov(
            rep,
            "N-PORT fundInfo/amtPay* (sum of borrowings)",
            ", ".join(f"{k}={v:,.0f}" for k, v in rep.borrowing_breakdown.items())
            or "all borrowing fields reported as 0.00",
        )
        anomaly = []
        if rep.borrowings == 0 and rep.total_liabilities and na:
            # Zero borrowings alongside material liabilities means the fund's
            # leverage, if any, is not in the borrowing fields. Reporting 0.00
            # as the leverage ratio without saying so would be misleading.
            if rep.total_liabilities / na > 0.10:
                anomaly.append("zero_borrowings_but_material_total_liabilities")
        out.append(
            Candidate(
                fund_ticker=fund.ticker,
                metric=M_LEVERAGE,
                value=rep.borrowings / na,
                unit="ratio",
                tier=SourceTier.STRUCTURED_XML,
                provenance=Provenance(**{**prov.__dict__, "fund_ticker": fund.ticker}),
                basis={"leverage_basis": "gross_debt_to_equity"},
                transforms=[f"sum(borrowings) {rep.borrowings:,.0f} / netAssets {na:,.0f}"],
                flags=anomaly,
            )
        )

    if rep.total_liabilities is not None:
        prov = _prov(
            rep,
            "N-PORT fundInfo/totLiabs / fundInfo/netAssets",
            f"totLiabs={rep.total_liabilities:,.0f}, netAssets={na:,.0f}",
        )
        out.append(
            Candidate(
                fund_ticker=fund.ticker,
                metric=M_LEVERAGE,
                value=rep.total_liabilities / na,
                unit="ratio",
                tier=SourceTier.STRUCTURED_XML,
                provenance=Provenance(**{**prov.__dict__, "fund_ticker": fund.ticker}),
                basis={"leverage_basis": "total_liabilities_to_equity"},
                transforms=[f"totLiabs {rep.total_liabilities:,.0f} / netAssets {na:,.0f}"],
                flags=["includes_unsettled_trades_and_payables"],
            )
        )
    return out


def monthly_return_series(reports: list[NportReport]) -> dict[str | None, dict[date, float]]:
    """month_end -> return %, keyed by share class id (None = fund level).

    Overlapping filings restate the same month; later filings win, which is the
    filer's own most recent view of that month.
    """
    out: dict[str | None, dict[date, float]] = {}
    for rep in reports:  # already oldest-first
        for month_end, val, cls in rep.monthly_returns:
            out.setdefault(cls, {})[month_end] = val
    return out


def _annualize(monthly: list[tuple[date, float]], years: int) -> float | None:
    """Chain-link `years * 12` monthly returns, annualized. None if incomplete."""
    need = years * 12
    if len(monthly) < need:
        return None
    window = monthly[-need:]
    latest = window[-1][0]
    span = (latest.year - window[0][0].year) * 12 + (latest.month - window[0][0].month) + 1
    if span != need:  # non-contiguous months make the chain meaningless
        return None
    growth = 1.0
    for _, r in window:
        growth *= 1.0 + r / 100.0
    return (growth ** (1.0 / years) - 1.0) * 100.0


@dataclass
class ClassBand:
    """Spread of a trailing return across a fund's unidentified class series."""

    metric: str
    low: float
    high: float
    n_classes: int

    def contains(self, value: float, slack: float = 0.05) -> bool:
        return self.low - slack <= value <= self.high + slack


def class_return_bands(reports: list[NportReport]) -> dict[str, ClassBand]:
    """Min/max trailing return across share-class series, for corroboration.

    Where a multi-class filer does not label its class rows (TAKIX emits seven
    unlabelled rows), we cannot say which one is the institutional class the
    board deck asks for. What we *can* say is the range every class falls in.
    A narrative-extracted institutional figure that lands outside this band is
    almost certainly a misread, and is downgraded accordingly. This is the main
    cross-check available for a fund with no usable XBRL.
    """
    series = monthly_return_series(reports)
    if len(series) < 2:
        return {}
    bands: dict[str, ClassBand] = {}
    for metric, years in ((M_RETURN_1Y, 1), (M_RETURN_3Y, 3), (M_RETURN_5Y, 5)):
        vals = []
        for months in series.values():
            v = _annualize(sorted(months.items()), years)
            if v is not None:
                vals.append(v)
        if len(vals) >= 2:
            bands[metric] = ClassBand(metric, min(vals), max(vals), len(vals))
    return bands


def trailing_returns(
    fund: Fund, reports: list[NportReport], notices: SuppressionLog | None = None
) -> list[Candidate]:
    """Trailing annualized net return chain-linked from N-PORT monthly returns.

    N-PORT monthly total returns are net of expenses, so this is a genuine net
    return from a structured field rather than a NAV reconstruction.

    Two limits are enforced rather than papered over:
      * History depth. We download a bounded number of filings, so only fully
        covered windows are emitted -- never extrapolated.
      * Class attribution. A single unlabelled row is the fund as a whole and is
        emitted as such. Several unlabelled rows cannot be attributed to a named
        share class, so no point estimate is emitted at all; the spread is
        published as a corroboration band instead (see `class_return_bands`).
    """
    series = monthly_return_series(reports)
    if not series:
        if notices is not None:
            for metric in (M_RETURN_1Y, M_RETURN_3Y, M_RETURN_5Y):
                notices.add(
                    Suppression(
                        fund_ticker=fund.ticker,
                        metric=metric,
                        reason=SuppressionReason.NO_CANDIDATE,
                        detail="no monthly total-return rows in the filer's N-PORT reports",
                        as_of=reports[-1].period_end if reports else None,
                    )
                )
        return []
    if len(series) > 1:
        # Several unlabelled class rows. The spread across them is a real
        # cross-check, but by client ruling it is never rendered: anything that
        # is not a point estimate is a label, not a value. So the band goes to
        # the appendix via `internal_note` and the cell says why it is blank.
        log.info(
            "%s: %d unlabelled share-class return series in N-PORT -- no point "
            "estimate emitted; using them as a corroboration band instead",
            fund.ticker, len(series),
        )
        if notices is not None:
            bands = class_return_bands(reports)
            for metric in (M_RETURN_1Y, M_RETURN_3Y, M_RETURN_5Y):
                band = bands.get(metric)
                notices.add(
                    Suppression(
                        fund_ticker=fund.ticker,
                        metric=metric,
                        reason=SuppressionReason.CLASS_ATTRIBUTION_FAILED,
                        detail=(
                            f"{len(series)} share-class return series are reported "
                            "without class identifiers; could not attribute a figure "
                            "to the institutional class"
                        ),
                        as_of=reports[-1].period_end if reports else None,
                        internal_note=(
                            f"appendix only, not for the deck: class spread "
                            f"{band.low:.2f}%-{band.high:.2f}% across {band.n_classes} "
                            "series, retained as a bound-check on any narrative figure"
                            if band
                            else ""
                        ),
                    )
                )
        return []

    months = sorted(next(iter(series.values())).items())
    if not months:
        return []
    out: list[Candidate] = []
    rep = reports[-1]

    for metric, years in ((M_RETURN_1Y, 1), (M_RETURN_3Y, 3), (M_RETURN_5Y, 5)):
        ann = _annualize(months, years)
        if ann is None:
            log.info(
                "%s %s: %d of %d monthly returns available from N-PORT -- suppressed",
                fund.ticker, metric, len(months), years * 12,
            )
            if notices is not None:
                notices.add(
                    Suppression(
                        fund_ticker=fund.ticker,
                        metric=metric,
                        reason=SuppressionReason.INSUFFICIENT_HISTORY,
                        detail=(
                            f"{len(months)} of the {years * 12} contiguous monthly "
                            "returns needed for this window are available from N-PORT"
                        ),
                        as_of=months[-1][0],
                        coverage_start=months[0][0],
                        coverage_end=months[-1][0],
                    )
                )
            continue
        need = years * 12
        prov = _prov(
            rep,
            "N-PORT fundInfo/returnInfo/monthlyTotReturns (chain-linked)",
            f"{need} monthly returns {months[-need][0]}..{months[-1][0]}",
        )
        out.append(
            Candidate(
                fund_ticker=fund.ticker,
                metric=metric,
                value=ann,
                unit="pct",
                tier=SourceTier.DERIVED,
                provenance=Provenance(**{**prov.__dict__, "fund_ticker": fund.ticker}),
                basis={
                    "return_basis": "nport_monthly_chain_linked",
                    "net_of_fees": True,
                    "share_class": "fund_level",
                },
                transforms=[f"chain-link {need} monthly N-PORT returns, annualized"],
                flags=["fund_level_not_share_class_specific"],
            )
        )
    return out


def extract_all(
    fund: Fund,
    client: EdgarClient,
    limit: int = 8,
    notices: SuppressionLog | None = None,
) -> list[Candidate]:
    reports = load_reports(fund, client, limit=limit)
    if not reports:
        return []
    out = leverage(fund, reports) + trailing_returns(fund, reports, notices)
    return [c for c in out if c.metric in fund.supported_metrics]
