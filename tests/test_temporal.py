"""Tests for anchoring and eligibility.

The anchor is the client's ruling: the deck reports Q4 2025, so a peer figure
covering mid-2026 is not a fresher version of the same number -- it is a
different reporting period. Silently mixing the two produces a slide that reads
as like-for-like and is not, which is the failure mode with no visible symptom.
"""

from datetime import date

from apexridge.config import M_LEVERAGE, M_NAV_PS
from apexridge.core.models import (
    Candidate,
    Provenance,
    SourceTier,
    SuppressionLog,
)
from apexridge.core.temporal import (
    DEFAULT_ANCHOR,
    filter_eligible,
    is_eligible,
    next_period_end,
)

ANCHOR = date(2025, 12, 31)


def candidate(metric: str, value: float, period_end: date, filed: date | None = None) -> Candidate:
    return Candidate(
        fund_ticker="TESTX",
        metric=metric,
        value=value,
        unit="ratio",
        tier=SourceTier.STRUCTURED_XML,
        provenance=Provenance(
            fund_ticker="TESTX",
            form_type="NPORT-P",
            accession="0001-26-000001",
            filing_date=filed or period_end,
            period_end=period_end,
            document_url="https://example.invalid",
            locator="test",
        ),
    )


def test_period_after_anchor_is_ineligible_however_early_it_was_filed():
    assert is_eligible(date(2026, 6, 30), ANCHOR) is False
    assert is_eligible(date(2025, 12, 31), ANCHOR) is True
    assert is_eligible(date(2025, 9, 30), ANCHOR) is True


def test_late_filed_but_in_period_figure_is_eligible():
    """TAKIX's N-CSR for 2025-12-31 was filed 2026-02-27.

    Eligibility is about the period covered, not the filing date: that figure
    is the correct one for a Q4 2025 deck even though it arrived in 2026.
    """
    late = candidate(M_LEVERAGE, 0.49, date(2025, 12, 31), filed=date(2026, 2, 27))
    assert filter_eligible([late], ANCHOR) == [late]


def test_post_anchor_candidates_are_dropped():
    keep = candidate(M_LEVERAGE, 0.68, date(2025, 12, 31))
    drop = candidate(M_LEVERAGE, 0.29, date(2026, 6, 30))
    assert filter_eligible([keep, drop], ANCHOR) == [keep]


def test_notice_distinguishes_alignment_exclusion_from_a_source_gap():
    """A blank here must not read as "we found nothing" -- we found it and
    excluded it, which is a different sentence to defend to a board."""
    notices = SuppressionLog()
    dropped = candidate(M_NAV_PS, 14.25, date(2026, 6, 30))
    assert filter_eligible([dropped], ANCHOR, notices) == []

    notice = notices.get("TESTX", M_NAV_PS)
    assert notice is not None
    assert "2025-12-31" in notice.cell_label
    assert "alignment exclusion" in notice.internal_note
    assert notice.as_of == date(2026, 6, 30)


def test_no_notice_when_an_eligible_figure_survives():
    """Dropping a newer figure is not worth explaining if a valid one remains."""
    notices = SuppressionLog()
    keep = candidate(M_LEVERAGE, 0.68, date(2025, 12, 31))
    drop = candidate(M_LEVERAGE, 0.29, date(2026, 6, 30))
    filter_eligible([keep, drop], ANCHOR, notices)
    assert notices.get("TESTX", M_LEVERAGE) is None


def test_candidate_without_a_period_is_not_silently_admitted():
    orphan = candidate(M_LEVERAGE, 1.0, date(2025, 6, 30))
    object.__setattr__(orphan.provenance, "period_end", None)
    orphan.as_of = None
    assert filter_eligible([orphan], ANCHOR) == []


def test_next_period_end_handles_a_march_fiscal_year():
    """CCLFX: March FYE, so class-level reporting lands March and September."""
    assert next_period_end("CCLFX", date(2025, 12, 31)) == date(2026, 3, 31)
    assert next_period_end("CCLFX", date(2026, 4, 1)) == date(2026, 9, 30)


def test_default_anchor_matches_the_apex_reporting_quarter():
    """Apex's own data ends Q4 2025; the anchor must not drift to the run date."""
    assert DEFAULT_ANCHOR == date(2025, 12, 31)
