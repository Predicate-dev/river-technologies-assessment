"""Tests for financial-highlights parsing.

The two interval funds lay this table out differently and both layouts are
represented here verbatim. Each case below is a way to read the table
successfully and still get a wrong number into a board deck: a sign dropped, a
part-year return chain-linked as if annual, or a figure attributed to a share
class it did not come from.
"""

from datetime import date

from apexridge.edgar import Filing
from apexridge.sources.highlights import (
    HighlightsTable,
    _class_from_preamble,
    _values_from,
    _years_from,
    parse_table,
    pick_class,
)


def filing(form: str, report: date) -> Filing:
    return Filing(
        cik="0001725472",
        form=form,
        accession="0001725472-26-000005",
        filing_date=report,
        report_date=report,
        primary_document="x.htm",
    )


# --------------------------------------------------------------- header rows


def test_bare_year_header_is_read():
    assert _years_from(["CLASS I", "2025", "2024", "2023"]) == [2025, 2024, 2023]


def test_period_phrase_header_takes_the_closing_year():
    """CCLFX writes full period phrases. "January 1, 2022 through March 31,
    2022" names the year twice; the period end is the one that matters."""
    row = [
        "For the Year Ended March 31, 2025",
        "For the Period January 1, 2022 through March 31, 2022*",
        "For the Year Ended December 31, 2021",
    ]
    assert _years_from(row) == [2025, 2022, 2021]


# ------------------------------------------------------------------- values


def test_negative_split_across_cells_keeps_its_sign():
    """CCLFX splits negatives as "(0.90" then ")". Losing the sign turns a
    distribution or a loss into a gain."""
    assert _values_from(["(0.90", ")", "(1.45", ")"]) == [-0.90, -1.45]


def test_currency_and_percent_cells_are_skipped():
    assert _values_from(["$", "10.83", "$", "10.55"]) == [10.83, 10.55]
    assert _values_from(["11.58", "%", "13.34", "%"]) == [11.58, 13.34]


def test_footnote_markers_are_not_read_as_values():
    """"Total return 4" carries a footnote marker; an integer is never a
    per-share value or a return in these tables."""
    assert _values_from(["4", "11.58", "%", "13.34", "%"]) == [11.58, 13.34]


def test_negative_return_is_preserved():
    assert _values_from(["5.86", "%", "(1.42", ")", "%"]) == [5.86, -1.42]


# -------------------------------------------------------------- whole table


TAKIX_ROWS = [
    ["CLASS I", "2025", "2024", "2023"],
    ["Net asset value, beginning of period", "$", "8.55", "$", "8.52"],
    ["Net asset value, end of period", "$", "8.32", "$", "8.55", "$", "8.52"],
    ["Total Return, at Net Asset Value (2)", "6.27", "%", "10.80", "%", "14.15", "%"],
    ["Total Dividends and/or distributions to shareholders:", "(0.75", ")", "(0.86", ")", "(0.88", ")"],
]


def test_parses_a_class_labelled_table():
    t = parse_table(TAKIX_ROWS, filing("N-CSR", date(2025, 12, 31)))
    assert t is not None
    assert t.share_class == "CLASS I"
    assert t.years == [2025, 2024, 2023]
    assert t.nav_end == [8.32, 8.55, 8.52]
    assert t.total_return == [6.27, 10.80, 14.15]
    assert t.dividends == [0.75, 0.86, 0.88]  # sign stripped; magnitudes


def test_class_read_from_the_heading_when_the_header_has_none():
    preamble = "Financial Highlights Class I Shares For a share outstanding"
    assert _class_from_preamble(preamble) == "Class I"


def test_plain_total_return_label_is_matched():
    """CCLFX writes "Total return 4", not "Total Return, at Net Asset Value"."""
    rows = [
        ["For the Year Ended March 31, 2025", "For the Year Ended March 31, 2024"],
        ["Net asset value, end of period", "$", "10.83", "$", "10.55"],
        ["Total return 4", "11.58", "%", "13.34", "%"],
    ]
    t = parse_table(rows, filing("N-CSR", date(2025, 3, 31)))
    assert t is not None and t.total_return == [11.58, 13.34]


# ------------------------------------------------- annual vs semi-annual


def test_semi_annual_table_is_not_treated_as_annual():
    """An N-CSRS leading column is a part-year stub. Chain-linking it as a full
    year would understate a trailing return without any visible symptom."""
    annual = HighlightsTable("Class I", [2025], filing("N-CSR", date(2025, 3, 31)))
    semi = HighlightsTable("Class I", [2025], filing("N-CSRS", date(2025, 9, 30)))
    assert annual.is_annual is True
    assert semi.is_annual is False


# --------------------------------------------------------- class selection


def test_pick_class_returns_none_rather_than_substituting():
    """Institutional is a hard requirement; a different class silently
    substituted is exactly what that requirement exists to prevent."""
    tables = [
        HighlightsTable("CLASS A", [2025], filing("N-CSR", date(2025, 12, 31))),
        HighlightsTable("CLASS Y", [2025], filing("N-CSR", date(2025, 12, 31))),
    ]
    assert pick_class(tables, "Class I") is None


def test_pick_class_matches_case_and_spacing_insensitively():
    tables = [HighlightsTable("CLASS I", [2025], filing("N-CSR", date(2025, 12, 31)))]
    assert pick_class(tables, "Class I") is tables[0]
