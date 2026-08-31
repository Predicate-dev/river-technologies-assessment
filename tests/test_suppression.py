"""Tests for the blank-cell path.

The client's governing rule is asymmetric: a wrong number costs far more than a
gap, so suppression is the pipeline's most-exercised branch. What matters is not
that a cell blanks -- it is that it blanks for the *right stated reason*, since
the reason is what the partner has to defend in the room. These tests cover the
precedence between competing reasons and the coverage arithmetic that the client
explicitly required on the cell.
"""

from datetime import date

from apexridge.config import M_RETURN_1Y, M_RETURN_5Y, Fund
from apexridge.core.confidence import STALE_LIMIT_DAYS
from apexridge.core.models import (
    Candidate,
    Confidence,
    Provenance,
    SourceTier,
    Suppression,
    SuppressionLog,
    SuppressionReason,
)
from apexridge.core.reconcile import reconcile_fund, reconcile_metric

REF = date(2026, 8, 31)

FUND = Fund(
    name="Test Interval Fund",
    ticker="TESTX",
    cik="1234567",
    entity_type="interval_fund",
    fiscal_year_end="03-31",
    primary_forms=("NPORT-P",),
    supported_metrics=(M_RETURN_1Y, M_RETURN_5Y),
)

REIT = Fund(
    name="Test Mortgage REIT",
    ticker="TREIT",
    cik="7654321",
    entity_type="mortgage_reit",
    fiscal_year_end="12-31",
    primary_forms=("10-K",),
    supported_metrics=(),  # publishes no NAV-based return series at all
)


def candidate(value: float, as_of: date, flags: list[str] | None = None) -> Candidate:
    return Candidate(
        fund_ticker=FUND.ticker,
        metric=M_RETURN_1Y,
        value=value,
        unit="pct",
        tier=SourceTier.STRUCTURED_XML,
        provenance=Provenance(
            fund_ticker=FUND.ticker,
            form_type="NPORT-P",
            accession="0001-24-000001",
            filing_date=as_of,
            period_end=as_of,
            document_url="https://example.invalid/primary_doc.xml",
            locator="fundInfo/returnInfo",
        ),
        flags=flags or [],
        as_of=as_of,
    )


# ------------------------------------------------------------- coverage math


def test_coverage_label_states_real_span_not_the_requested_one():
    """GBDC's 5Y case: 4.7 years of history must never be labelled 5Y."""
    s = Suppression(
        fund_ticker="GBDC",
        metric=M_RETURN_5Y,
        reason=SuppressionReason.WINDOW_MISMATCH,
        detail="NAV history does not span a full 5Y window",
        coverage_start=date(2021, 9, 30),
        coverage_end=date(2026, 6, 30),
    )
    assert s.coverage_label == "4.7y available (2021-09-30 to 2026-06-30)"
    assert "5Y" in s.cell_label  # says which window was asked for
    assert s.cell_label.endswith(".")


def test_sub_year_coverage_renders_in_months_not_as_zero_years():
    s = Suppression(
        fund_ticker="TESTX",
        metric=M_RETURN_1Y,
        reason=SuppressionReason.INSUFFICIENT_HISTORY,
        detail="7 of the 12 monthly returns needed are available",
        coverage_start=date(2025, 12, 31),
        coverage_end=date(2026, 6, 30),
    )
    assert s.coverage_label.startswith("6mo available")


def test_cell_label_is_never_empty_even_with_no_dates():
    """A blank cell always carries prose; nothing renders bare."""
    s = Suppression(
        fund_ticker="TESTX",
        metric=M_RETURN_1Y,
        reason=SuppressionReason.NO_CANDIDATE,
        detail="no candidate value found in any source",
    )
    assert s.cell_label.strip()
    assert s.coverage_label == ""


def test_as_of_carried_when_there_is_no_coverage_window():
    """The staleness ruling: a blank still carries the last available date."""
    s = Suppression(
        fund_ticker="CCLFX",
        metric=M_RETURN_1Y,
        reason=SuppressionReason.STALE_BEYOND_LIMIT,
        detail="most recent reported figure is 210d old",
        as_of=date(2026, 3, 31),
    )
    assert "last available 2026-03-31" in s.cell_label


# --------------------------------------------------------------- precedence


def test_extractor_notice_beats_the_generic_absence():
    """The useful sentence is known upstream; reconciliation must not clobber it."""
    notices = SuppressionLog()
    notices.add(
        Suppression(
            fund_ticker=FUND.ticker,
            metric=M_RETURN_5Y,
            reason=SuppressionReason.WINDOW_MISMATCH,
            detail="NAV history does not span a full 5Y window",
            coverage_start=date(2021, 9, 30),
            coverage_end=date(2026, 6, 30),
        )
    )
    r = reconcile_metric(FUND, M_RETURN_5Y, [], REF, notices)
    assert r.value is None
    assert r.suppression is not None
    assert r.suppression.reason is SuppressionReason.WINDOW_MISMATCH
    assert "2021-09-30" in r.notes[0]


def test_missing_notice_falls_back_to_generic_absence():
    r = reconcile_metric(FUND, M_RETURN_5Y, [], REF, SuppressionLog())
    assert r.suppression.reason is SuppressionReason.NO_CANDIDATE
    assert r.confidence is Confidence.SUPPRESSED


def test_staleness_blanks_a_high_confidence_value():
    """The six-month line is a cliff, not a score penalty: good evidence loses."""
    stale = REF.toordinal() - (STALE_LIMIT_DAYS + 1)
    r = reconcile_metric(FUND, M_RETURN_1Y, [candidate(4.2, date.fromordinal(stale))], REF)
    assert r.value is None
    assert r.suppression.reason is SuppressionReason.STALE_BEYOND_LIMIT
    assert r.score > 0.4  # the evidence was fine; the client's rule blanked it
    assert "4.2" in r.suppression.internal_note  # recoverable for the appendix


def test_value_just_inside_the_limit_survives():
    fresh = REF.toordinal() - (STALE_LIMIT_DAYS - 1)
    r = reconcile_metric(FUND, M_RETURN_1Y, [candidate(4.2, date.fromordinal(fresh))], REF)
    assert r.value == 4.2
    assert r.suppression is None


def test_staleness_outranks_the_confidence_floor():
    """Both apply; the reader is told the data stopped, not that a score dipped."""
    stale = date.fromordinal(REF.toordinal() - (STALE_LIMIT_DAYS + 60))
    junk = candidate(4.2, stale, flags=["out_of_sane_range", "single_extraction_pass"])
    r = reconcile_metric(FUND, M_RETURN_1Y, [junk], REF)
    assert r.score < 0.4  # would have been suppressed on confidence too
    assert r.suppression.reason is SuppressionReason.STALE_BEYOND_LIMIT


def _stale_cand(period_end: date, filing_date: date, form: str = "N-CSR") -> Candidate:
    """A candidate whose filing date is deliberately not its period end."""
    return Candidate(
        fund_ticker=FUND.ticker,
        metric=M_RETURN_1Y,
        value=7.4,
        unit="pct",
        tier=SourceTier.HTML_TABLE,
        provenance=Provenance(
            fund_ticker=FUND.ticker,
            form_type=form,
            accession="0001-25-000009",
            filing_date=filing_date,
            period_end=period_end,
            document_url="https://example.invalid/ncsr.htm",
            locator="Financial Highlights, row 3",
        ),
        as_of=period_end,
    )


def test_cadence_blank_names_form_period_filing_date_and_limit():
    """CCLFX's real shape, and the four facts Lara has to answer on in the room."""
    r = reconcile_metric(
        FUND,
        M_RETURN_1Y,
        [_stale_cand(date(2025, 3, 31), date(2025, 6, 5))],
        date(2025, 12, 31),
    )
    detail = r.suppression.detail
    assert r.suppression.reason is SuppressionReason.STALE_BEYOND_LIMIT
    assert "N-CSR" in detail
    assert "period ended 2025-03-31" in detail
    assert "filed 2025-06-05" in detail
    assert f"{STALE_LIMIT_DAYS}d limit" in detail


def test_cadence_age_is_measured_from_period_end_not_filing_date():
    """The correction to the client's own draft wording.

    Her proposed label said "filed 275 days prior to anchor date". It is the
    period end that sits 275 days back; the filing is 209. Decision D makes a
    source eligible on the period it covers, so a label that quotes the filing
    date as the distance describes a rule the system does not implement -- and
    it fails on the first follow-up question in a board meeting.
    """
    r = reconcile_metric(
        FUND,
        M_RETURN_1Y,
        [_stale_cand(date(2025, 3, 31), date(2025, 6, 5))],
        date(2025, 12, 31),
    )
    assert "275d behind the 2025-12-31 anchor" in r.suppression.detail
    assert "209d" not in r.suppression.detail  # the filing-date distance


def test_terms_metric_stale_label_does_not_claim_a_period_end():
    """A fee rate's clock is the last amendment-capable filing, not a period."""
    cand = _stale_cand(date(2024, 12, 31), date(2025, 2, 14), form="10-K")
    cand.terms_clock = date(2025, 1, 31)
    r = reconcile_metric(FUND, M_RETURN_1Y, [cand], date(2026, 8, 31))
    detail = r.suppression.detail
    assert r.suppression.reason is SuppressionReason.STALE_BEYOND_LIMIT
    assert "no amendment to this rate through 2025-01-31" in detail
    assert "period ended" not in detail


def test_cadence_blank_without_a_period_end_falls_back_to_the_as_of():
    cand = _stale_cand(date(2025, 3, 31), date(2025, 6, 5))
    object.__setattr__(cand.provenance, "period_end", None)
    r = reconcile_metric(FUND, M_RETURN_1Y, [cand], date(2025, 12, 31))
    assert "dated 2025-03-31" in r.suppression.detail


def test_not_applicable_outranks_an_extractor_notice():
    """KREF's case: nothing to be stale about if the concept is not published."""
    notices = SuppressionLog()
    notices.add(
        Suppression(
            fund_ticker=REIT.ticker,
            metric=M_RETURN_1Y,
            reason=SuppressionReason.INSUFFICIENT_HISTORY,
            detail="only 1 NAV observation",
        )
    )
    out = reconcile_fund(REIT, [], REF, metrics=[M_RETURN_1Y], notices=notices)
    r = out[M_RETURN_1Y]
    assert r.suppression.reason is SuppressionReason.NOT_APPLICABLE
    assert "near-metric" in r.suppression.detail  # states the refusal to substitute


def test_first_notice_wins_over_a_later_restatement():
    """Extractors run cheapest-first; the earliest diagnosis is the specific one."""
    notices = SuppressionLog()
    first = notices.add(
        Suppression(
            fund_ticker=FUND.ticker,
            metric=M_RETURN_1Y,
            reason=SuppressionReason.CLASS_ATTRIBUTION_FAILED,
            detail="7 unlabelled class series",
        )
    )
    notices.add(
        Suppression(
            fund_ticker=FUND.ticker,
            metric=M_RETURN_1Y,
            reason=SuppressionReason.NO_CANDIDATE,
            detail="nothing extracted",
        )
    )
    assert notices.get(FUND.ticker, M_RETURN_1Y) is first
    assert len(notices) == 1


def test_class_band_stays_out_of_the_rendered_cell():
    """Client ruling: the spread is appendix-only, never a range in the cell."""
    notices = SuppressionLog()
    notices.add(
        Suppression(
            fund_ticker=FUND.ticker,
            metric=M_RETURN_1Y,
            reason=SuppressionReason.CLASS_ATTRIBUTION_FAILED,
            detail="7 share-class return series are reported without class identifiers",
            internal_note="appendix only, not for the deck: class spread 3.19%-4.07%",
        )
    )
    r = reconcile_metric(FUND, M_RETURN_1Y, [], REF, notices)
    assert "3.19" not in r.suppression.cell_label
    assert "3.19" in r.suppression.internal_note


def test_empty_log_is_truthy():
    """`__len__` would otherwise make an empty log falsy, and extractors guarding
    on it would drop notices on precisely the runs that have none yet."""
    assert bool(SuppressionLog()) is True
    assert len(SuppressionLog()) == 0


def test_window_mismatch_coverage_is_the_computable_window():
    """GBDC has NAVs back to 2017 but only annually before 2021. The blank 5Y
    cell must state the window that was actually computable (4.7y from the
    nearest anchor), not the raw 8.7y span -- which would read as a
    contradiction sitting next to a blank."""
    from apexridge.config import FUNDS
    from apexridge.edgar import EdgarClient
    from apexridge.sources.xbrl import XbrlFacts
    from apexridge.sources.xbrl_metrics import nav_total_returns

    import pytest

    gbdc = next(f for f in FUNDS if f.ticker == "GBDC")
    notices = SuppressionLog()
    try:  # the only test touching real filings; skip rather than fail offline
        facts = XbrlFacts(gbdc, EdgarClient())
    except Exception as exc:
        pytest.skip(f"GBDC companyfacts unavailable ({type(exc).__name__}: {exc})")
    nav_total_returns(facts, gbdc, notices=notices)
    s = notices.get("GBDC", M_RETURN_5Y)
    assert s is not None and s.reason is SuppressionReason.WINDOW_MISMATCH
    # Contiguous quarterly history begins 2021-09-30; the annual-only
    # observations before it cannot contribute to a chain-linked return.
    assert s.coverage_start == date(2021, 9, 30)
    # 2021-09-30 to the 2025-12-31 anchor. Was 4.7y when the series ran to
    # mid-2026; anchoring the endpoint shortened it, correctly.
    assert s.coverage_label.startswith("4.3y available")


# ------------------------------------------------- disqualified basis (TAKIX)


def _lev(value: float, basis: str, flags: list[str]) -> Candidate:
    # Inside the staleness limit, so these exercise the basis gate rather than
    # tripping the six-month cliff first.
    c = candidate(value, date(2026, 6, 30), flags)
    c.metric = "leverage_ratio_dte"
    c.unit = "ratio"
    c.basis = {"leverage_basis": basis}
    return c


LEVERAGE_FUND = Fund(
    name="Test Interval Fund",
    ticker="TESTX",
    cik="1234567",
    entity_type="interval_fund",
    fiscal_year_end="03-31",
    primary_forms=("NPORT-P",),
    supported_metrics=("leverage_ratio_dte",),
)


def test_disqualified_primary_basis_blanks_rather_than_falling_through():
    """TAKIX: 0.00 borrowings against material liabilities. Falling through to
    the total-liabilities basis would silently answer the regulatory-vs-economic
    question the client has escalated, by picking the economic reading."""
    cands = [
        _lev(0.0, "gross_debt_to_equity", ["zero_borrowings_but_material_total_liabilities"]),
        _lev(0.4939, "total_liabilities_to_equity", ["includes_unsettled_trades_and_payables"]),
    ]
    r = reconcile_metric(LEVERAGE_FUND, "leverage_ratio_dte", cands, REF)
    assert r.value is None
    assert r.suppression.reason is SuppressionReason.BASIS_DISQUALIFIED
    # The alternative is preserved for the appendix but never substituted.
    assert "0.4939" in r.suppression.internal_note
    assert "0.4939" not in r.suppression.cell_label
    assert "0.49" not in r.suppression.cell_label


def test_a_clean_primary_basis_is_unaffected():
    """The gate must not fire on the three funds that report borrowings properly."""
    cands = [
        _lev(1.231, "gross_debt_to_equity", []),
        _lev(1.9, "total_liabilities_to_equity", ["includes_unsettled_trades_and_payables"]),
    ]
    r = reconcile_metric(LEVERAGE_FUND, "leverage_ratio_dte", cands, REF)
    assert r.value == 1.231
    assert r.suppression is None


def test_disqualifying_flag_on_only_one_of_two_same_basis_candidates_does_not_blank():
    """The gate requires the whole basis to be disqualified. One bad extraction
    alongside a clean one on the same basis is an ordinary conflict, not an
    inapplicable construction."""
    cands = [
        _lev(0.0, "gross_debt_to_equity", ["zero_borrowings_but_material_total_liabilities"]),
        _lev(1.231, "gross_debt_to_equity", []),
    ]
    r = reconcile_metric(LEVERAGE_FUND, "leverage_ratio_dte", cands, REF)
    assert r.value == 1.231  # fewest-flags ordering picks the clean one
    assert r.suppression is None


def test_no_incentive_fee_makes_the_hurdle_not_applicable():
    """A fund charging no carry has no hurdle. Reporting it as an extraction
    gap would imply a figure exists that we failed to find; it does not."""
    from apexridge.config import M_HURDLE, M_INCENTIVE_FEE, Fund
    from apexridge.core.reconcile import reconcile_fund

    fund = Fund(
        name="No-Carry Interval Fund",
        ticker="NOCRY",
        cik="9999999",
        entity_type="interval_fund",
        fiscal_year_end="12-31",
        primary_forms=("N-CSR",),
        supported_metrics=(M_INCENTIVE_FEE, M_HURDLE),
    )
    zero = Candidate(
        fund_ticker=fund.ticker,
        metric=M_INCENTIVE_FEE,
        value=0.0,
        unit="pct",
        tier=SourceTier.HTML_TABLE,
        provenance=Provenance(
            fund_ticker=fund.ticker,
            form_type="486BPOS",
            accession="0001-25-000001",
            # Inside the staleness window: this test is about the cross-metric
            # rule, and a period one day past the limit would suppress the
            # incentive fee first and never exercise it.
            filing_date=date(2025, 9, 30),
            period_end=date(2025, 9, 30),
            document_url="https://example.invalid",
            locator="expense table: no incentive fee row",
        ),
        basis={"fee_basis": "none_disclosed"},
    )
    resolved = reconcile_fund(fund, [zero], date(2025, 12, 31))

    assert resolved[M_INCENTIVE_FEE].value == 0.0
    hurdle = resolved[M_HURDLE]
    assert hurdle.value is None
    assert hurdle.suppression.reason is SuppressionReason.NOT_APPLICABLE
    assert "no incentive fee" in hurdle.suppression.detail
