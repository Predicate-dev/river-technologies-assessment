"""Tests for the distribution ledger.

Covers the real failure modes seen in EDGAR data, not happy paths: a 10-K that
reports a fiscal year without tagging its fourth quarter, fiscal-year-to-date
cumulatives that overlap each other, and duplicate comparative tagging.
"""

from datetime import date

from apexridge.core.periods import Period, build_ledger, sum_between


def d(s: str) -> date:
    return date.fromisoformat(s)


def test_recovers_untagged_fiscal_q4_from_annual_total():
    """GBDC's real shape: Q1-Q3 tagged, only the FY total covers Q4."""
    facts = [
        (d("2024-10-01"), d("2024-12-31"), 0.48, "10-Q:Q1"),
        (d("2024-10-01"), d("2025-03-31"), 0.87, "10-Q:H1-cumulative"),
        (d("2025-04-01"), d("2025-06-30"), 0.39, "10-Q:Q3"),
        (d("2024-10-01"), d("2025-09-30"), 1.65, "10-K:FY-total"),
    ]
    ledger = build_ledger(facts)
    by_start = {p.start: p for p in ledger}

    # Q2 recovered by differencing the H1 cumulative against Q1.
    q2 = by_start[d("2025-01-01")]
    assert abs(q2.value - 0.39) < 1e-9
    assert q2.source == "derived_by_difference"

    # Q4 recovered by differencing the FY total against Q1-Q3.
    q4 = by_start[d("2025-07-01")]
    assert abs(q4.value - 0.39) < 1e-9
    assert q4.source == "derived_by_difference"

    # The whole fiscal year is covered exactly once -- no double counting.
    total, used, complete = sum_between(ledger, d("2024-10-01"), d("2025-09-30"))
    assert abs(total - 1.65) < 1e-9
    assert len(used) == 4
    assert complete


def test_duplicate_comparative_tagging_is_not_double_counted():
    """The same quarter re-tagged in a later filing must count once."""
    facts = [
        (d("2025-04-01"), d("2025-06-30"), 0.39, "10-Q:2025"),
        (d("2025-04-01"), d("2025-06-30"), 0.39, "10-Q:2026-comparative"),
    ]
    ledger = build_ledger(facts)
    assert len(ledger) == 1
    assert abs(sum(p.value for p in ledger) - 0.39) < 1e-9


def test_ambiguous_residual_is_dropped_not_guessed():
    """A cumulative with two uncovered holes cannot be attributed -- leave it."""
    facts = [
        (d("2025-04-01"), d("2025-06-30"), 0.39, "Q2"),
        (d("2025-01-01"), d("2025-12-31"), 1.60, "FY"),
    ]
    ledger = build_ledger(facts)
    # Q1 and H2 are both uncovered; we must not invent a split between them.
    assert [p.source for p in ledger] == ["tagged"]
    assert len(ledger) == 1


def test_dividend_cut_is_preserved_not_smoothed():
    """KREF's real Q2 2026 cut: 0.25 -> 0.10. The ledger must not average it."""
    facts = [
        (d("2026-01-01"), d("2026-03-31"), 0.25, "10-Q"),
        (d("2026-01-01"), d("2026-06-30"), 0.35, "10-Q:H1"),
        (d("2026-04-01"), d("2026-06-30"), 0.10, "10-Q"),
    ]
    ledger = build_ledger(facts)
    vals = [p.value for p in ledger]
    assert 0.25 in vals and 0.10 in vals
    total, _, _ = sum_between(ledger, d("2026-01-01"), d("2026-06-30"))
    assert abs(total - 0.35) < 1e-9


def test_incomplete_window_is_reported_incomplete():
    facts = [(d("2025-01-01"), d("2025-03-31"), 0.25, "Q1")]
    ledger = build_ledger(facts)
    _, _, complete = sum_between(ledger, d("2025-01-01"), d("2025-12-31"))
    assert complete is False
