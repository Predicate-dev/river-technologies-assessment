"""Tests for fund discovery and classification.

Adding a fund is the one feature here that can produce confidently wrong numbers
rather than blanks: every adapter keys off entity type and fiscal year end, and
a filer classified wrong runs the wrong extractors against the wrong forms. So
classification refuses when the evidence is thin, and these tests are mostly
about the refusals.
"""

from datetime import date

import pytest

from apexridge.discovery import Classification, _annual_period_end, to_fund


def submissions(forms_and_reports: list[tuple[str, str]]) -> dict:
    return {
        "form": [f for f, _ in forms_and_reports],
        "reportDate": [r for _, r in forms_and_reports],
    }


# --------------------------------------------------------- fiscal year end


def test_fiscal_year_end_comes_from_the_latest_annual_filing():
    recent = submissions(
        [("10-Q", "2025-06-30"), ("N-CSR", "2025-03-31"), ("N-CSR", "2024-03-31")]
    )
    assert _annual_period_end(recent) == date(2025, 3, 31)


def test_quarterly_filings_do_not_set_the_fiscal_year_end():
    recent = submissions([("10-Q", "2025-06-30"), ("NPORT-P", "2025-09-30")])
    assert _annual_period_end(recent) is None


def test_malformed_report_dates_are_skipped():
    recent = submissions([("10-K", "not-a-date"), ("10-K", "2025-09-30")])
    assert _annual_period_end(recent) == date(2025, 9, 30)


# ------------------------------------------------------------- the refusals


def usable(**kw) -> Classification:
    base = dict(
        cik="1",
        name="Test Fund",
        entity_type="bdc",
        fiscal_year_end="12-31",
        confident=True,
    )
    base.update(kw)
    return Classification(**base)


def test_a_confident_classification_becomes_a_fund():
    fund = to_fund(usable(entity_type="interval_fund"))
    assert fund.entity_type == "interval_fund"
    assert fund.institutional_class == "Class I"
    assert "NPORT-P" in fund.primary_forms


def test_an_unconfident_classification_is_refused():
    """Apple files 10-K/10-Q and would otherwise be classified a BDC."""
    with pytest.raises(ValueError, match="cannot add"):
        to_fund(usable(confident=False, reasons=["SIC 3571 is not investment company"]))


def test_a_filer_with_no_fiscal_year_end_is_refused():
    """Every anchoring and staleness decision keys off it."""
    with pytest.raises(ValueError):
        to_fund(usable(fiscal_year_end=""))


def test_an_unclassified_filer_is_refused():
    with pytest.raises(ValueError):
        to_fund(usable(entity_type=""))


def test_the_refusal_names_the_reason():
    """A refusal a user cannot act on is just a failure."""
    with pytest.raises(ValueError, match="files neither"):
        to_fund(usable(confident=False, reasons=["files neither 10-K nor N-CSR"]))


# ------------------------------------------------------- metric scoping


def test_a_reit_added_by_discovery_excludes_fund_style_returns():
    """The same rule the configured peer set applies to KREF."""
    fund = to_fund(usable(entity_type="mortgage_reit"))
    assert not any(m.startswith("net_return") for m in fund.supported_metrics)
    assert "leverage_ratio_dte" in fund.supported_metrics


def test_an_interval_fund_added_by_discovery_keeps_returns():
    fund = to_fund(usable(entity_type="interval_fund"))
    assert "net_return_1y_pct" in fund.supported_metrics
