"""End-to-end orchestration: EDGAR to resolved metrics.

One function, `run`, so that the CLI, the tests and any future scheduler all
exercise the same path. The stage order is deliberate and each stage is
observable:

    extract -> filter to the anchor -> reconcile -> resolved metrics + notices

Extraction is already anchored (adapters select as of the reporting quarter),
so the eligibility filter should normally drop nothing. It stays in the pipeline
as a guard: if a future adapter forgets to anchor, the filter catches it and the
run reports an alignment exclusion instead of silently comparing a peer's
mid-year figure against the client's quarter.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from .config import ALL_METRICS, DATA_DIR, FUNDS, Fund
from .core.models import Candidate, ResolvedMetric, SuppressionLog
from .core.reconcile import reconcile_fund
from .core.temporal import DEFAULT_ANCHOR, filter_eligible
from .edgar import EdgarClient
from .sources import highlights, narrative, nport
from .sources.xbrl import XbrlFacts
from .sources.xbrl_metrics import extract_all as xbrl_extract

log = logging.getLogger(__name__)


@dataclass
class FundResult:
    fund: Fund
    resolved: dict[str, ResolvedMetric]
    candidates: list[Candidate]
    dropped_by_anchor: int = 0


@dataclass
class BenchmarkRun:
    anchor: date
    results: dict[str, FundResult] = field(default_factory=dict)
    notices: SuppressionLog = field(default_factory=SuppressionLog)
    apex: pd.DataFrame | None = None

    @property
    def conflicts(self) -> list[tuple[str, ResolvedMetric]]:
        out = []
        for ticker, res in self.results.items():
            for metric in ALL_METRICS:
                rm = res.resolved.get(metric)
                if rm is not None and rm.conflict is not None:
                    out.append((ticker, rm))
        return out


def load_apex(anchor: date, path=None) -> pd.DataFrame:
    """Apex Ridge's own quarters, up to and including the anchor.

    Loaded through the same anchor rule as the peers. The client's column is
    the reference point of every comparison, so letting it run past the
    reporting quarter would be the same misalignment in the other direction.
    """
    df = pd.read_csv(path or DATA_DIR / "apex_ridge_fund_data.csv")
    # "Q4 2025" -> the quarter's period end, so it can be compared to a date.
    def period_end(label: str) -> date:
        q, year = label.split()
        month, day = {"Q1": (3, 31), "Q2": (6, 30), "Q3": (9, 30), "Q4": (12, 31)}[q]
        return date(int(year), month, day)

    df["period_end"] = df["quarter"].map(period_end)
    return df[df["period_end"] <= anchor].reset_index(drop=True)


def extract_fund(
    fund: Fund,
    client: EdgarClient,
    anchor: date,
    notices: SuppressionLog,
    *,
    nport_limit: int = 8,
    use_llm: bool = False,
) -> list[Candidate]:
    """Every candidate this filer's sources can produce, as of the anchor."""
    candidates: list[Candidate] = []

    if fund.entity_type == "interval_fund":
        try:
            candidates += nport.extract_all(
                fund, client, limit=nport_limit, notices=notices, anchor=anchor
            )
        except Exception:
            log.exception("N-PORT extraction failed for %s", fund.ticker)
        # The only class-level source for these filers, and therefore the only
        # way to meet the institutional-class requirement.
        try:
            from .config import _REGISTRY

            specs = tuple(
                s for s in _REGISTRY
                if s.highlights_rows and s.applies_to(fund.entity_type)
            )
            class_level, _tables = highlights.extract_all(
                fund, client, anchor, specs=specs
            )
            candidates += class_level
        except Exception:
            log.exception("financial-highlights extraction failed for %s", fund.ticker)
    else:
        try:
            facts = XbrlFacts(fund, client)
            candidates += xbrl_extract(facts, fund, anchor, notices)
        except Exception:
            log.exception("XBRL extraction failed for %s", fund.ticker)

    try:
        from .config import _REGISTRY

        prose_specs = tuple(
            s for s in _REGISTRY
            if s.prose_patterns and s.applies_to(fund.entity_type)
        )
        candidates += narrative.extract_all(
            fund, client, use_llm=use_llm, anchor=anchor, specs=prose_specs
        )
    except Exception:
        log.exception("narrative extraction failed for %s", fund.ticker)

    return candidates


def run(
    anchor: date = DEFAULT_ANCHOR,
    funds: tuple[Fund, ...] = FUNDS,
    client: EdgarClient | None = None,
    *,
    nport_limit: int = 8,
    use_llm: bool = False,
) -> BenchmarkRun:
    client = client or EdgarClient()
    run_result = BenchmarkRun(anchor=anchor)
    run_result.apex = load_apex(anchor)

    for fund in funds:
        log.info("extracting %s (%s)", fund.ticker, fund.entity_type)
        candidates = extract_fund(
            fund,
            client,
            anchor,
            run_result.notices,
            nport_limit=nport_limit,
            use_llm=use_llm,
        )
        eligible = filter_eligible(candidates, anchor, run_result.notices)
        dropped = len(candidates) - len(eligible)
        if dropped:
            log.warning(
                "%s: %d candidate(s) excluded as post-anchor -- an adapter is "
                "not selecting as of %s",
                fund.ticker, dropped, anchor,
            )
        resolved = reconcile_fund(fund, eligible, anchor, notices=run_result.notices)
        run_result.results[fund.ticker] = FundResult(
            fund=fund,
            resolved=resolved,
            candidates=eligible,
            dropped_by_anchor=dropped,
        )
    return run_result
