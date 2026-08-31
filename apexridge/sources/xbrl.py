"""XBRL company-facts adapter.

Covers the two 10-K/10-Q filers (GBDC, KREF), where SEC XBRL gives us typed,
dated, machine-readable facts. This is the highest-trust extraction *mechanism*
we have -- but the tier scores the mechanism, not the filer's judgement. A filer
can tag a number that is valid XBRL and still not mean what we want (see the
`cef:ManagementFeesPercent` handling below), which is precisely why every value
still goes through reconciliation instead of being trusted on tier alone.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterator

from ..config import (
    M_DIST_YIELD,
    M_INCENTIVE_FEE,
    M_LEVERAGE,
    M_MGMT_FEE,
    M_NAV_PS,
    M_RETURN_1Y,
    M_RETURN_3Y,
    M_RETURN_5Y,
    Fund,
)
from ..core.models import Candidate, Provenance, SourceTier
from ..edgar import ARCHIVE_BASE, EdgarClient

log = logging.getLogger(__name__)


def _d(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


@dataclass(frozen=True)
class Fact:
    """One XBRL fact occurrence."""

    tag: str
    taxonomy: str
    unit: str
    val: float
    start: date | None
    end: date | None
    accn: str
    form: str
    filed: date | None
    fy: int | None
    fp: str | None
    frame: str | None

    @property
    def is_instant(self) -> bool:
        return self.start is None

    @property
    def duration_days(self) -> int | None:
        if self.start and self.end:
            return (self.end - self.start).days
        return None

    @property
    def qname(self) -> str:
        return f"{self.taxonomy}:{self.tag}"


class XbrlFacts:
    """Indexed access to one company's XBRL facts."""

    def __init__(self, fund: Fund, client: EdgarClient) -> None:
        self.fund = fund
        self.client = client
        self._raw = client.company_facts(fund.cik)
        self._index: dict[str, list[Fact]] = {}
        self._build()

    def _build(self) -> None:
        for tax, tags in self._raw.get("facts", {}).items():
            for tag, body in tags.items():
                out: list[Fact] = []
                for unit, rows in body.get("units", {}).items():
                    for r in rows:
                        out.append(
                            Fact(
                                tag=tag,
                                taxonomy=tax,
                                unit=unit,
                                val=float(r["val"]),
                                start=_d(r.get("start")),
                                end=_d(r.get("end")),
                                accn=r.get("accn", ""),
                                form=r.get("form", ""),
                                filed=_d(r.get("filed")),
                                fy=r.get("fy"),
                                fp=r.get("fp"),
                                frame=r.get("frame"),
                            )
                        )
                # Newest last; stable ordering keeps runs reproducible.
                out.sort(key=lambda f: (f.end or date.min, f.start or date.min, f.accn))
                self._index[f"{tax}:{tag}"] = out

    def has(self, qname: str) -> bool:
        return bool(self._index.get(qname))

    def series(
        self,
        qname: str,
        *,
        instant: bool | None = None,
        min_days: int | None = None,
        max_days: int | None = None,
        unit: str | None = None,
    ) -> list[Fact]:
        """Facts for a tag, filtered by period shape.

        The period filters matter: `CommonStockDividendsPerShareDeclared` is
        tagged both quarterly and fiscal-year-to-date in the same filing, and
        summing the two would double-count.
        """
        facts = self._index.get(qname, [])
        out = []
        for f in facts:
            if unit and f.unit != unit:
                continue
            if instant is True and not f.is_instant:
                continue
            if instant is False and f.is_instant:
                continue
            dd = f.duration_days
            if min_days is not None and (dd is None or dd < min_days):
                continue
            if max_days is not None and (dd is None or dd > max_days):
                continue
            out.append(f)
        return out

    def latest(self, qname: str, **kw: Any) -> Fact | None:
        s = self.series(qname, **kw)
        return s[-1] if s else None

    def as_of(self, qname: str, anchor: date, **kw: Any) -> Fact | None:
        """The most recent fact whose period closed on or before `anchor`.

        This, not `latest()`, is what every metric extractor wants. `latest()`
        returns the newest observation the filer has published, which for a
        Q4 2025 deck is typically a mid-2026 figure -- newer than anything in
        the client's own column. Selecting on the anchor keeps every peer on
        the same reporting quarter as Apex Ridge; the eligibility filter then
        has nothing left to discard.
        """
        eligible = [f for f in self.series(qname, **kw) if f.end and f.end <= anchor]
        return eligible[-1] if eligible else None

    def at(self, qname: str, period_end: date, tolerance_days: int = 5, **kw: Any) -> Fact | None:
        """The fact whose period end is closest to `period_end`, within tolerance.

        Where a filer reports the same instant in several filings (an original
        10-Q and a later comparative), prefer the earliest-filed original: the
        comparative column is more often restated or rounded.
        """
        best: Fact | None = None
        best_delta = tolerance_days + 1
        for f in self.series(qname, **kw):
            if not f.end:
                continue
            delta = abs((f.end - period_end).days)
            if delta < best_delta or (
                delta == best_delta and best and f.filed and best.filed and f.filed < best.filed
            ):
                best, best_delta = f, delta
        return best

    # ------------------------------------------------------------ provenance

    def provenance(self, fact: Fact, note: str = "") -> Provenance:
        accn_nodash = fact.accn.replace("-", "")
        url = f"{ARCHIVE_BASE}/{self.fund.cik_int}/{accn_nodash}/{fact.accn}-index.htm"
        period = (
            f"{fact.start.isoformat()}..{fact.end.isoformat()}"
            if fact.start and fact.end
            else (fact.end.isoformat() if fact.end else "?")
        )
        locator = f"XBRL {fact.qname} [{fact.unit}] @ {period}"
        if note:
            locator += f" ({note})"
        return Provenance(
            fund_ticker=self.fund.ticker,
            form_type=fact.form,
            accession=fact.accn,
            filing_date=fact.filed,
            period_end=fact.end,
            document_url=url,
            locator=locator,
            excerpt=f"{fact.qname} = {fact.val:,.6g} {fact.unit}",
        )

    def candidate(
        self,
        metric: str,
        fact: Fact,
        *,
        value: float | None = None,
        unit: str = "pct",
        tier: SourceTier = SourceTier.XBRL,
        basis: dict[str, Any] | None = None,
        transforms: list[str] | None = None,
        flags: list[str] | None = None,
        note: str = "",
    ) -> Candidate:
        return Candidate(
            fund_ticker=self.fund.ticker,
            metric=metric,
            value=fact.val if value is None else value,
            unit=unit,
            tier=tier,
            provenance=self.provenance(fact, note),
            basis=basis or {},
            transforms=transforms or [],
            flags=flags or [],
        )
