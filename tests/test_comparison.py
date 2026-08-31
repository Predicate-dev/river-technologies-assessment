"""Tests for the peer comparison.

Two things here are load-bearing. Comparability must be decided on what a figure
measures, not on how it was derived — excluding on method would leave most rows
with a single "peer" and quietly defeat the normalization. And the Apex gate must
genuinely be a switch, because the technical document tells the client it is one.
"""

from datetime import date

import apexridge.render.comparison as comparison_module
from apexridge.config import (
    M_DIST_YIELD,
    M_LEVERAGE,
    M_MGMT_FEE,
    M_NAV_PS,
    M_RETURN_1Y,
)
from apexridge.render.comparison import MetricComparison, comparability_key


# ------------------------------------------------------------ comparability


def test_same_measure_by_different_methods_is_comparable():
    """GBDC's NAV total return and TAKIX's chain-linked annual return are both
    net returns on NAV. Different derivations, one distribution."""
    a = comparability_key(M_RETURN_1Y, {"return_basis": "nav_total_return"})
    b = comparability_key(
        M_RETURN_1Y, {"return_basis": "chain_linked_annual_total_return"}
    )
    assert a == b


def test_fee_on_a_different_base_is_not_comparable():
    """KREF's fee is struck on adjusted equity, the credit funds' on assets."""
    reit = comparability_key(M_MGMT_FEE, {"fee_basis": "pct_of_adjusted_equity"})
    fund = comparability_key(M_MGMT_FEE, {"fee_basis": "stated_annual_rate"})
    assert reit != fund


def test_book_value_is_not_a_nav():
    assert comparability_key(M_NAV_PS, {"measure": "book_value_per_share"}) != (
        comparability_key(M_NAV_PS, {"measure": "nav_per_share"})
    )


def test_leverage_bases_are_distinguished():
    assert comparability_key(M_LEVERAGE, {"leverage_basis": "gross_debt_to_equity"}) != (
        comparability_key(M_LEVERAGE, {"leverage_basis": "total_liabilities_to_equity"})
    )


def test_yield_denominator_matters():
    assert comparability_key(M_DIST_YIELD, {"denominator": "nav"}) != (
        comparability_key(M_DIST_YIELD, {"denominator": "price"})
    )


# --------------------------------------------------------------- statistics


def make(metric: str, apex: float | None, peers: dict[str, float]) -> MetricComparison:
    return MetricComparison(metric=metric, apex=apex, peers=dict(peers))


def test_rank_respects_direction_for_returns():
    """Higher is better."""
    c = make(M_RETURN_1Y, 10.31, {"GBDC": 8.72, "TAKIX": 6.27})
    assert c.apex_rank == (1, 3)
    assert [t for t, _ in c.peers_ranked] == ["GBDC", "TAKIX"]


def test_rank_inverts_for_fees():
    """Lower is better, so a higher fee ranks worse."""
    c = make(M_MGMT_FEE, 1.25, {"CCLFX": 1.00, "GBDC": 1.00})
    assert c.apex_rank == (3, 3)


def test_undirected_metrics_are_not_ranked():
    """A NAV per share is a share price, not a quality."""
    c = make(M_NAV_PS, 26.12, {"TAKIX": 8.32, "GBDC": 14.84})
    assert c.direction == 0
    assert c.apex_rank is None


def test_delta_is_against_the_peer_median():
    c = make(M_RETURN_1Y, 10.0, {"A": 6.0, "B": 8.0, "C": 12.0})
    assert c.peer_median == 8.0
    assert c.apex_delta == 2.0


def test_no_peers_means_no_statistics():
    c = make(M_RETURN_1Y, 10.0, {})
    assert c.peer_median is None
    assert c.apex_delta is None
    assert c.apex_rank is None


# ---------------------------------------------------------------- the gate


def test_apex_deltas_are_withheld_until_the_basis_is_confirmed(monkeypatch):
    """The technical document tells the client this is one flag, not a rebuild.
    This asserts that is true."""
    from apexridge.pipeline import BenchmarkRun

    run = BenchmarkRun(anchor=date(2025, 12, 31))

    monkeypatch.setattr(comparison_module, "APEX_BASIS_CONFIRMED", False)
    withheld = comparison_module.comparison_markdown(run)
    assert "deltas are withheld" in withheld

    monkeypatch.setattr(comparison_module, "APEX_BASIS_CONFIRMED", True)
    released = comparison_module.comparison_markdown(run)
    assert "deltas are withheld" not in released
