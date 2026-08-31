"""Financial-highlights extraction from N-CSR / N-CSRS.

This is the only source of *class-level* data for the two interval funds, and
therefore the only way to satisfy the client's hard requirement that CCLFX and
TAKIX figures be institutional-class. N-PORT carries no per-share and no
per-class field at all; the annual and semi-annual reports carry both, in a
table whose shape is fixed by Reg S-X.

What the table gives us, per share class, per fiscal year:

    Net asset value, end of period        -> NAV per share
    Total Return, at Net Asset Value      -> that year's total return, net
    Dividends to shareholders             -> distributions per share

Trailing 3Y and 5Y figures are chain-linked from the annual returns rather than
read off anywhere, because the filings do not state them. The method is
recorded on every candidate.

Cadence note: these reports are annual (N-CSR) and semi-annual (N-CSRS), so the
NAV series they support is semi-annual at best. That is the constraint behind
the client's ruling to put the whole peer set on a common semi-annual footing.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date

from bs4 import BeautifulSoup

from ..config import (
    M_DIST_YIELD,
    M_NAV_PS,
    M_RETURN_1Y,
    M_RETURN_3Y,
    M_RETURN_5Y,
    Fund,
)
from ..core.models import Candidate, Provenance, SourceTier
from ..edgar import EdgarClient, Filing
from .narrative import anchors

log = logging.getLogger(__name__)

# Row labels we read, matched case-insensitively as a prefix of the first cell.
ROW_NAV_END = r"net asset value,? end of"
# Label wording differs by filer: TAKIX writes "Total Return, at Net Asset
# Value"; CCLFX writes "Total return 4" with a footnote marker. Both are the
# NAV total return -- these tables carry no market-price return.
ROW_TOTAL_RETURN = r"total return"
ROW_DIVIDENDS = (
    r"(total )?(dividends|distributions)( and/or distributions)? to shareholders"
)

_YEAR_IN_TEXT = re.compile(r"\b(19|20)(\d{2})\b")
# Decimal required. Financial-highlights rows carry footnote markers as bare
# integers in the same cells ("Total return 4"), and an integer is never a
# per-share value or a return in these tables.
_DECIMAL = re.compile(r"\(?\d[\d,]*\.\d+\)?")


def _years_from(row: list[str]) -> list[int]:
    """Fiscal years from a header row.

    Two layouts occur across these filers: bare year cells ("2025", "2024")
    and full period phrases ("For the Year Ended March 31, 2025"). Both are
    read, taking the last year mentioned in each cell -- a phrase like
    "For the Period January 1, 2022 through March 31, 2022" names the year
    twice and the closing one is the period end.
    """
    years: list[int] = []
    for cell in row:
        found = _YEAR_IN_TEXT.findall(cell)
        if found:
            years.append(int(f"{found[-1][0]}{found[-1][1]}"))
    return years


def _values_from(cells: list[str]) -> list[float]:
    """Ordered numeric values from a data row.

    Currency and percent symbols sit in their own cells, and a negative can be
    split across cells as "(0.90" then ")". Joining the row first and repairing
    the split parentheses keeps the sign, which matters: a negative return read
    as positive is a silent sign error in a benchmark.
    """
    text = " ".join(cells)
    text = text.replace("$", " ").replace("%", " ")
    # "(0.90 )" and "(0.90" + ")" both become "(0.90)".
    text = re.sub(r"\(\s*([\d,]*\.?\d+)\s*\)", r"(\1)", text)
    out: list[float] = []
    for token in _DECIMAL.findall(text):
        negative = token.startswith("(")
        try:
            v = float(token.strip("()").replace(",", ""))
        except ValueError:
            continue
        out.append(-v if negative else v)
    return out


@dataclass
class HighlightsTable:
    """One share class's financial-highlights block."""

    share_class: str
    years: list[int]
    filing: Filing

    @property
    def is_annual(self) -> bool:
        """N-CSR covers a full fiscal year; N-CSRS's first column is a stub.

        A semi-annual report's leading return column is a part-year figure. It
        looks exactly like an annual one and chain-linking it into a trailing
        return would silently understate several years of performance, so
        returns are only ever taken from annual tables.
        """
        return self.filing.form.upper() == "N-CSR"

    nav_end: list[float | None] = field(default_factory=list)
    total_return: list[float | None] = field(default_factory=list)
    dividends: list[float | None] = field(default_factory=list)

    def by_year(self, series: list[float | None]) -> dict[int, float]:
        return {y: v for y, v in zip(self.years, series) if v is not None}


def _rows(html: str, start: int, end: int) -> list[list[str]]:
    soup = BeautifulSoup(html[start:end], "html.parser")
    out = []
    for tr in soup.find_all("tr"):
        cells = [re.sub(r"\s+", " ", td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        if cells:
            out.append(cells)
    return out


# A class label sitting in prose just above the table, where the header row
# does not carry one.
_CLASS_HEADING = re.compile(
    r"\b(Class\s+[A-Z]{1,2}|Institutional\s+(?:Class|Shares))\b"
)


def _class_from_preamble(text: str) -> str:
    """Share class named in the text immediately preceding a highlights table.

    CCLFX's header row carries period phrases and no class label, but the fund
    does have classes. Reading the heading above the table is how we avoid
    reporting a figure whose class we cannot name -- which the client's
    institutional requirement forbids.
    """
    found = _CLASS_HEADING.findall(text)
    return found[-1] if found else ""


def parse_table(
    rows: list[list[str]], filing: Filing, preamble: str = ""
) -> HighlightsTable | None:
    """One financial-highlights table into a typed record.

    Currency and percent symbols occupy their own cells in these documents, so
    values are read as an ordered run of numeric tokens and aligned positionally
    to the year columns rather than by cell index.
    """
    header_years: list[int] = []
    share_class = ""
    for row in rows[:6]:
        years = _years_from(row)
        if len(years) >= 2:
            header_years = years
            label = row[0].strip()
            if not _YEAR_IN_TEXT.search(label):
                share_class = label
            else:
                # A header of period phrases carries no class label; look for
                # one in the heading above the table.
                share_class = _class_from_preamble(preamble)
            break
    if not header_years:
        return None

    table = HighlightsTable(
        share_class=share_class or "unlabelled", years=header_years, filing=filing
    )
    for row in rows:
        label = row[0].lower()
        values = _values_from(row[1:])
        if re.match(ROW_NAV_END, label):
            table.nav_end = values[: len(header_years)]
        elif re.match(ROW_TOTAL_RETURN, label):
            table.total_return = values[: len(header_years)]
        elif re.match(ROW_DIVIDENDS, label) and not table.dividends:
            table.dividends = [abs(v) for v in values[: len(header_years)]]
    if not (table.nav_end or table.total_return):
        return None
    return table


def load_tables(
    fund: Fund, client: EdgarClient, anchor: date, per_form: int = 1
) -> list[HighlightsTable]:
    """Every share class's highlights block from the reports in force at `anchor`."""
    tables: list[HighlightsTable] = []
    for form in ("N-CSR", "N-CSRS"):
        found = [
            f
            for f in client.filings(fund.cik, forms=[form], limit=8)
            if f.report_date and f.report_date <= anchor
        ]
        for filing in found[:per_form]:
            try:
                html = client.get_text(filing.primary_url)
            except Exception:
                log.warning("could not fetch %s %s", fund.ticker, filing.accession)
                continue
            seen_spans: set[int] = set()
            for pos in anchors(html, ["Net asset value, end of"], limit_per_phrase=30):
                start = html.rfind("<table", 0, pos)
                end = html.find("</table>", pos)
                if start < 0 or end < 0 or start in seen_spans:
                    continue
                seen_spans.add(start)
                preamble = BeautifulSoup(
                    html[max(0, start - 4000) : start], "html.parser"
                ).get_text(" ", strip=True)
                parsed = parse_table(
                    _rows(html, start, end + 8), filing, preamble[-600:]
                )
                if parsed:
                    tables.append(parsed)
    return tables


def pick_class(tables: list[HighlightsTable], preferred: str) -> HighlightsTable | None:
    """The institutional share class, or None if it cannot be identified.

    Deliberately returns None rather than falling back to another class: the
    client made institutional a hard requirement because a blended or retail
    figure understates fee drag and flatters the competitor. Substituting a
    different class silently is the failure that requirement exists to prevent.
    """
    want = preferred.lower().replace(" ", "")
    for t in tables:
        if t.share_class.lower().replace(" ", "") == want:
            return t
    for t in tables:
        if want in t.share_class.lower().replace(" ", ""):
            return t
    return None


def _prov(fund: Fund, t: HighlightsTable, locator: str, excerpt: str) -> Provenance:
    return Provenance(
        fund_ticker=fund.ticker,
        form_type=t.filing.form,
        accession=t.filing.accession,
        filing_date=t.filing.filing_date,
        period_end=t.filing.report_date,
        document_url=t.filing.primary_url,
        locator=locator,
        excerpt=excerpt,
    )


def extract_all(
    fund: Fund, client: EdgarClient, anchor: date
) -> tuple[list[Candidate], list[HighlightsTable]]:
    """Class-level candidates, plus the parsed tables for the NAV trend."""
    if not fund.institutional_class:
        return [], []
    tables = load_tables(fund, client, anchor)
    if not tables:
        return [], []
    # Freshest first, so a point-in-time figure comes from the most recent
    # report available at the anchor.
    tables.sort(key=lambda t: t.filing.report_date or date.min, reverse=True)
    chosen = pick_class(tables, fund.institutional_class)
    # Returns must come from an annual table; see HighlightsTable.is_annual.
    annual = pick_class([t for t in tables if t.is_annual], fund.institutional_class)
    if chosen is None:
        log.info(
            "%s: institutional class %r not found among %s -- no class-level "
            "candidates emitted",
            fund.ticker, fund.institutional_class,
            [t.share_class for t in tables],
        )
        return [], tables

    out: list[Candidate] = []
    navs = chosen.by_year(chosen.nav_end)
    returns = annual.by_year(annual.total_return) if annual else {}
    divs = annual.by_year(annual.dividends) if annual else {}
    basis = {"share_class": fund.institutional_class, "net_of_fees": True}

    # A semi-annual table repeats the fiscal year for its stub column
    # ("2025", "2025"), so keying the point-in-time NAV by year collapses the
    # two and silently returns the older figure. These tables are ordered
    # newest-column-first in both filers, so position is the reliable handle.
    latest_nav = chosen.nav_end[0] if chosen.nav_end else None
    latest_year = max(navs) if navs else None
    if latest_nav is not None:
        out.append(
            Candidate(
                fund_ticker=fund.ticker,
                metric=M_NAV_PS,
                value=latest_nav,
                unit="usd",
                tier=SourceTier.HTML_TABLE,
                provenance=_prov(
                    fund, chosen,
                    f"financial highlights, {chosen.share_class}, "
                    "'net asset value, end of period', most recent column "
                    f"(period ended {chosen.filing.report_date})",
                    f"NAV end of period = {latest_nav}",
                ),
                basis={**basis, "measure": "nav_per_share"},
            )
        )
        if annual is not None and latest_year in divs and navs.get(latest_year):
            out.append(
                Candidate(
                    fund_ticker=fund.ticker,
                    metric=M_DIST_YIELD,
                    value=100.0 * divs[latest_year] / navs[latest_year],
                    unit="pct",
                    tier=SourceTier.DERIVED,
                    provenance=_prov(
                        fund, annual,
                        f"financial highlights, {annual.share_class}, "
                        f"dividends / NAV end, FY{latest_year}",
                        f"dividends {divs[latest_year]} / NAV {navs[latest_year]}",
                    ),
                    basis={**basis, "yield_basis": "fiscal_year_distributions_on_nav",
                           "denominator": "nav"},
                    transforms=[f"FY{latest_year} distributions / NAV at period end"],
                )
            )

    # Trailing returns, chain-linked from the stated annual returns. The filings
    # publish each year's total return but never the annualized trailing figure,
    # so the arithmetic is ours and is recorded as such.
    ordered = sorted(returns.items(), reverse=True)
    for metric, years in ((M_RETURN_1Y, 1), (M_RETURN_3Y, 3), (M_RETURN_5Y, 5)):
        window = ordered[:years]
        if len(window) < years:
            continue
        growth = 1.0
        for _y, r in window:
            growth *= 1.0 + r / 100.0
        ann = (growth ** (1.0 / years) - 1.0) * 100.0
        out.append(
            Candidate(
                fund_ticker=fund.ticker,
                metric=metric,
                value=ann,
                unit="pct",
                tier=SourceTier.DERIVED,
                provenance=_prov(
                    fund, annual,
                    f"financial highlights, {annual.share_class}, "
                    f"'total return at net asset value' FY{window[-1][0]}-FY{window[0][0]}",
                    ", ".join(f"FY{y}: {r}%" for y, r in reversed(window)),
                ),
                basis={**basis, "return_basis": "chain_linked_annual_total_return"},
                transforms=[
                    f"chain-link {years} stated annual total returns "
                    f"(FY{window[-1][0]}..FY{window[0][0]}), annualized"
                ],
            )
        )
    return [c for c in out if c.metric in fund.supported_metrics], tables
