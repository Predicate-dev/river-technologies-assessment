"""Invariants across the rendered outputs.

The board table and the coverage report are read by different people for
different reasons, and they are generated from the same run. If they disagree
about which cells are populated, both become untrustworthy — and the disagreement
is silent, because nobody reads them side by side. This caught a real case: a
CCLFX return the pipeline resolved to a fund-level figure, which render then
blanked for being the wrong share class while coverage still counted it.
"""

from datetime import date

from apexridge.config import ALL_METRICS, M_INCENTIVE_FEE, M_HURDLE, Fund
from apexridge.core.models import Candidate, Provenance, SourceTier
from apexridge.pipeline import BenchmarkRun, FundResult
from apexridge.core.reconcile import reconcile_fund
from apexridge.render.coverage import FILLED, coverage_rows
from apexridge.render.table import build_cells

ANCHOR = date(2025, 12, 31)

FUND = Fund(
    name="Test Interval Fund",
    ticker="TESTX",
    cik="1234567",
    entity_type="interval_fund",
    fiscal_year_end="12-31",
    primary_forms=("N-CSR",),
    supported_metrics=ALL_METRICS,
    institutional_class="Class I",
)


def candidate(metric: str, value: float, share_class: str) -> Candidate:
    return Candidate(
        fund_ticker=FUND.ticker,
        metric=metric,
        value=value,
        unit="pct",
        tier=SourceTier.DERIVED,
        provenance=Provenance(
            fund_ticker=FUND.ticker,
            form_type="N-CSR",
            accession="0001-26-000001",
            filing_date=ANCHOR,
            period_end=ANCHOR,
            document_url="https://example.invalid",
            locator="test",
        ),
        basis={"share_class": share_class},
    )


def _run(candidates: list[Candidate]) -> BenchmarkRun:
    run = BenchmarkRun(anchor=ANCHOR)
    run.results[FUND.ticker] = FundResult(
        fund=FUND,
        resolved=reconcile_fund(FUND, candidates, ANCHOR, notices=run.notices),
        candidates=candidates,
    )
    return run


def test_coverage_and_board_agree_on_every_cell():
    """The invariant. Coverage must report what the deck shows, not what the
    pipeline resolved."""
    run = _run(
        [
            candidate("net_return_1y_pct", 8.91, "fund_level"),
            candidate("net_return_3y_pct", 10.4, "Class I"),
        ]
    )
    grid = build_cells(run)
    by_key = {(r.fund, r.metric): r for r in coverage_rows(run)}

    for metric in ALL_METRICS:
        cell = grid[metric][FUND.ticker]
        row = by_key[(FUND.ticker, metric)]
        rendered = cell.value is not None
        counted = row.status == FILLED
        assert rendered == counted, (
            f"{metric}: board renders {'a value' if rendered else 'a blank'} "
            f"but coverage says {row.status}"
        )


def test_institutional_class_outranks_a_fund_level_figure():
    """Both exist for the same metric. The class-level one must win, or render
    blanks a cell whose correct value we already had."""
    run = _run(
        [
            candidate("net_return_1y_pct", 8.91, "fund_level"),
            candidate("net_return_1y_pct", 11.58, "Class I"),
        ]
    )
    resolved = run.results[FUND.ticker].resolved["net_return_1y_pct"]
    assert resolved.chosen is not None
    assert resolved.chosen.basis["share_class"] == "Class I"
    assert resolved.value == 11.58


def test_a_blank_cell_always_carries_a_reason():
    """Enforced by the Cell type, checked here end to end."""
    run = _run([candidate("net_return_1y_pct", 8.91, "Class I")])
    grid = build_cells(run)
    for metric in ALL_METRICS:
        cell = grid[metric][FUND.ticker]
        if cell.value is None:
            assert cell.reason is not None
            assert cell.reason.label


def test_no_incentive_fee_propagates_to_the_hurdle_in_the_rendered_grid():
    run = _run([candidate(M_INCENTIVE_FEE, 0.0, "Class I")])
    grid = build_cells(run)
    assert grid[M_HURDLE][FUND.ticker].value is None
    assert grid[M_HURDLE][FUND.ticker].reason is not None
