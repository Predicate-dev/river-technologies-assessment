"""Tests for fund discovery and classification.

Adding a fund is the one feature here that can produce confidently wrong numbers
rather than blanks: every adapter keys off entity type and fiscal year end, and
a filer classified wrong runs the wrong extractors against the wrong forms. So
classification refuses when the evidence is thin, and these tests are mostly
about the refusals.
"""

from datetime import date

import pytest

from apexridge.config import Fund
from apexridge.discovery import (
    Classification,
    _DISPLAY,
    _annual_period_end,
    load_peers,
    save_peers,
    to_fund,
)


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


# ------------------------------------------------------- full-text search


def test_display_name_parses_name_ticker_and_cik():
    """EDGAR full-text search is the only SEC index that sees non-traded
    interval funds -- the ticker files omit them entirely -- and it is the only
    place CCLFX's ticker appears alongside its CIK."""
    m = _DISPLAY.match("Cliffwater Corporate Lending Fund  (CCLFX)  (CIK 0001735964)")
    assert m is not None
    assert m.group("name").strip() == "Cliffwater Corporate Lending Fund"
    assert m.group("ticker") == "CCLFX"
    assert m.group("cik") == "0001735964"


def test_display_name_parses_without_a_ticker():
    m = _DISPLAY.match("Carlyle Tactical Private Credit Fund  (CIK 0001725472)")
    assert m is not None
    assert m.group("ticker") is None
    assert m.group("cik") == "0001725472"


# ------------------------------------------------------------- peer sets


def test_peer_set_round_trips(tmp_path):
    fund = to_fund(usable(entity_type="interval_fund", name="Test Interval"))
    path = tmp_path / "peers.json"
    save_peers((fund,), path)
    back = load_peers(path)
    assert len(back) == 1
    assert back[0].entity_type == "interval_fund"
    assert back[0].fiscal_year_end == fund.fiscal_year_end
    assert back[0].institutional_class == fund.institutional_class


def test_a_saved_peer_set_is_readable_json(tmp_path):
    """The CIO owns the peer list. It should be inspectable without running
    anything."""
    import json

    fund = to_fund(usable())
    path = tmp_path / "peers.json"
    save_peers((fund,), path)
    data = json.loads(path.read_text())
    assert data[0]["cik"] and data[0]["entity_type"]


def test_loading_a_malformed_peer_set_raises(tmp_path):
    path = tmp_path / "peers.json"
    path.write_text('{"not": "a list"}')
    with pytest.raises(ValueError):
        load_peers(path)
