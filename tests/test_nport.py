"""Tests for N-PORT return arithmetic and month attribution.

The month-attribution logic is the risky part: N-PORT gives three unlabelled
return values per filing and we have to decide which month each belongs to.
Getting it wrong shifts an entire return series by a month without any error.
"""

from datetime import date

from apexridge.sources.nport import _annualize, _month_ends


def test_month_ends_maps_rtn1_to_the_oldest_month():
    assert _month_ends(date(2026, 6, 30)) == [
        date(2026, 4, 30),
        date(2026, 5, 31),
        date(2026, 6, 30),
    ]


def test_month_ends_handles_february_and_year_boundary():
    assert _month_ends(date(2026, 3, 31)) == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
    ]
    assert _month_ends(date(2026, 1, 31)) == [
        date(2025, 11, 30),
        date(2025, 12, 31),
        date(2026, 1, 31),
    ]


def test_annualize_chain_links_and_compounds():
    months = [(date(2025, m, 28), 1.0) for m in range(1, 13)]
    ann = _annualize(months, 1)
    assert abs(ann - ((1.01**12 - 1) * 100)) < 1e-9


def test_annualize_returns_none_when_history_is_short():
    months = [(date(2025, m, 28), 0.5) for m in range(1, 12)]
    assert _annualize(months, 1) is None


def test_annualize_rejects_non_contiguous_months():
    """A gap must suppress the figure, not silently compress the window."""
    months = [(date(2025, m, 28), 0.5) for m in (1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12)]
    months.append((date(2026, 1, 28), 0.5))
    assert _annualize(months, 1) is None


def test_annualize_multi_year_uses_geometric_annualization():
    months = [
        (date(y, m, 28), 1.0) for y in (2024, 2025, 2026) for m in range(1, 13)
    ]
    ann = _annualize(months, 3)
    assert abs(ann - ((1.01**12 - 1) * 100)) < 1e-9
