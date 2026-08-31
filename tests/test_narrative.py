"""Tests for narrative extraction's ugly cases.

Every case here is drawn from wording that actually appears in these filers'
documents. All of them are ways to read a real, correctly-printed percentage out
of a filing and still put the wrong number in a board deck -- which is the
failure this engagement exists to remove.
"""

import re

from apexridge.sources.narrative import (
    PROSE_RULES,
    SUPERSEDED_RULES,
    _hurdle_basis,
    _is_historical,
    _normalise,
)
from apexridge.config import M_HURDLE, M_INCENTIVE_FEE, M_MGMT_FEE


def _patterns(metric: str) -> list[str]:
    return next(pats for m, _ph, pats, _b in PROSE_RULES if m == metric)


def _first_match(metric: str, text: str) -> re.Match | None:
    for pat in _patterns(metric):
        m = re.search(pat, text, re.I)
        if m:
            return m
    return None


# --------------------------------------------------------- historical rates

TAKIX_HISTORICAL = (
    "Prior to April 1, 2020, the Management Fee was calculated and payable "
    "monthly in arrears at the annual rate of 1.50% of the month-end value of "
    "the Fund's Net Assets."
)
TAKIX_CURRENT = (
    "The base management fee is calculated at an annual rate of 1.00% of the "
    "Fund's consolidated month-end Managed Assets."
)


def test_prior_to_clause_is_detected_as_superseded():
    m = _first_match(M_MGMT_FEE, TAKIX_HISTORICAL)
    assert m is not None and m.group(1) == "1.50"
    assert _is_historical(TAKIX_HISTORICAL, m.start()) is not None


def test_current_rate_is_not_flagged_historical():
    m = _first_match(M_MGMT_FEE, TAKIX_CURRENT)
    assert m is not None and m.group(1) == "1.00"
    assert _is_historical(TAKIX_CURRENT, m.start()) is None


def test_marker_in_a_neighbouring_sentence_does_not_condemn_a_current_rate():
    """The two clauses sit paragraphs apart in the real filing but can land in
    one extraction window. A marker must govern its own clause only."""
    text = TAKIX_HISTORICAL + " " + TAKIX_CURRENT
    m = re.search(r"annual rate of 1\.00", text)
    assert _is_historical(text, m.start()) is None


# --------------------------------------------------- superseded rate pairs


def test_reduced_from_x_to_y_captures_both_rates_current_second():
    """GBDC: both figures are real; the current one is the second."""
    text = (
        "On August 3, 2023, our board approved the Prior Investment Advisory "
        "Agreement, pursuant to which the base management fee rate was reduced "
        "from 1.375% to 1.0%."
    )
    pattern = next(p for metric, _ph, p, _b in SUPERSEDED_RULES if metric == M_MGMT_FEE)
    m = re.search(pattern, text, re.I)
    assert m is not None
    assert (m.group(1), m.group(2)) == ("1.375", "1.0")


def test_incentive_fee_reduction_captures_both_rates():
    text = "the incentive fee rates were reduced from 20.0% to 15.0% and the cap was reduced"
    pattern = next(
        p for metric, _ph, p, _b in SUPERSEDED_RULES if metric == M_INCENTIVE_FEE
    )
    m = re.search(pattern, text, re.I)
    assert m is not None
    assert (m.group(1), m.group(2)) == ("20.0", "15.0")


# ------------------------------------------------------------ hurdle basis


def test_quarterly_hurdle_is_annualized():
    """GBDC: 2.0% quarterly is an 8.0% annual hurdle."""
    text = 'is compared to a fixed "hurdle rate" of 2.0% quarterly, which is the same'
    m = re.search(r"hurdle rate\"? of\s*([0-9.]+)\s*%", text, re.I)
    mult, _basis, transforms, _note = _hurdle_basis(text, m.start(1), m.end(1))
    assert mult == 4.0
    assert transforms == ["stated quarterly; x4 to annualize"]


def test_already_annual_hurdle_is_not_quadrupled():
    """TAKIX states both rates in one sentence. Measuring context from the match
    start rather than the number picked up "per quarter" and returned 24%."""
    text = (
        "equal to 1.50% per quarter, or an annualized hurdle rate of 6.00%, "
        "subject to a catch-up feature"
    )
    m = re.search(r"annualized hurdle rate of\s*([0-9.]+)\s*%", text, re.I)
    mult, _basis, _transforms, _note = _hurdle_basis(text, m.start(1), m.end(1))
    assert mult == 1.0


def test_quarterly_qualifier_before_the_number_is_still_found():
    """"in respect of the relevant calendar quarter, to a hurdle rate of 1.50%"
    -- the qualifier precedes the figure."""
    text = (
        "as a percentage of the Fund's Net Assets in respect of the relevant "
        "calendar quarter, to a hurdle rate of 1.50%. If the Fund's income"
    )
    m = re.search(r"hurdle rate of\s*([0-9.]+)\s*%", text, re.I)
    mult, _basis, _transforms, _note = _hurdle_basis(text, m.start(1), m.end(1))
    assert mult == 4.0


# ----------------------------------------------------- quote verification


def test_quote_verification_tolerates_typography_but_not_invention():
    """The LLM guard: smart quotes and whitespace must not fail a real quote,
    and a fabricated one must not pass."""
    source = "The Fund pays the Investment Manager a management fee of 1.00%."
    assert _normalise("management fee of 1.00%") in _normalise(source)
    assert _normalise("management  fee  of  1.00%") in _normalise(source)
    assert _normalise("management fee of 1.25%") not in _normalise(source)
