"""Tests for the client-ruled leverage perimeter.

Leverage is the metric behind the client's board incident, and this is the one
ruling that required per-filer extraction rather than a config switch, so the
arithmetic is pinned here with KREF's real balance-sheet figures. The CIO's
ruling: non-recourse securitisation out, repo in.
"""

from datetime import date

from apexridge.config import M_LEVERAGE_ECON, M_LEVERAGE_REG, Fund
from apexridge.edgar import Filing
from apexridge.sources.narrative import Doc, inline_facts, leverage_perimeter

KREF = Fund(
    name="KKR Real Estate Finance Trust Inc.",
    ticker="KREF",
    cik="0001631596",
    entity_type="mortgage_reit",
    fiscal_year_end="12-31",
    primary_forms=("10-K",),
    supported_metrics=(M_LEVERAGE_REG, M_LEVERAGE_ECON),
)

FILING = Filing(
    accession="0001631596-26-000012",
    form="10-K",
    filing_date=date(2026, 2, 20),
    report_date=date(2025, 12, 31),
    primary_document="kref-20251231.htm",
    cik="0001631596",
)


def _fact(name: str, ctx: str, value: str, scale: str = "3") -> str:
    return (
        f'<ix:nonFraction unitRef="usd" contextRef="{ctx}" decimals="-3" '
        f'name="{name}" scale="{scale}">{value}</ix:nonFraction>'
    )


def _context(cid: str, instant: str, segment: str = "") -> str:
    seg = f"<xbrli:segment>{segment}</xbrli:segment>" if segment else ""
    return (
        f'<xbrli:context id="{cid}"><xbrli:entity>'
        f'<xbrli:identifier scheme="http://www.sec.gov/CIK">0001631596'
        f"</xbrli:identifier>{seg}</xbrli:entity><xbrli:period>"
        f"<xbrli:instant>{instant}</xbrli:instant></xbrli:period></xbrli:context>"
    )


# KREF's actual 2025-12-31 consolidated balance sheet, in thousands.
REPO = "2,862,689"
CLO = "1,198,332"
TERM_LOAN = "632,516"
LIABILITIES = "5,239,439"
EQUITY = "1,172,550"


def kref_html(**overrides: str) -> str:
    """The filing reduced to the facts the perimeter reads."""
    v = {
        "us-gaap:LineOfCredit": REPO,
        "kref:CollateralizedLoanObligationsNet": CLO,
        "us-gaap:SecuredDebt": TERM_LOAN,
        "us-gaap:Liabilities": LIABILITIES,
        "us-gaap:StockholdersEquity": EQUITY,
    }
    v.update(overrides)
    return (
        _context("c-6", "2025-12-31")
        + _context("c-7", "2024-12-31")
        + "".join(_fact(tag, "c-6", val) for tag, val in v.items() if val)
        # Prior year, same tags: must never be picked for a 2025 anchor.
        + _fact("us-gaap:StockholdersEquity", "c-7", "1,100,000")
        + _fact("us-gaap:Liabilities", "c-7", "6,000,000")
    )


def doc(html: str) -> Doc:
    return Doc(KREF, FILING, html)


def _by_metric(cands: list) -> dict:
    return {c.metric: c for c in cands}


# --------------------------------------------------------- inline XBRL read


def test_dimensional_contexts_are_ignored():
    """A member breakdown is a slice of the total, not another reading of it.

    KREF tags its CLO balance twice: once consolidated, once against a
    VariableInterestEntity member. Accepting the dimensional copy would let a
    single vehicle stand in for the whole securitisation balance -- an
    under-exclusion that makes leverage look higher than the ruling intends.
    """
    html = (
        _context("c-6", "2025-12-31")
        + _context(
            "c-310",
            "2025-12-31",
            '<xbrldi:explicitMember dimension="us-gaap:FinancialInstrumentAxis">'
            "us-gaap:CollateralizedLoanObligationsMember</xbrldi:explicitMember>",
        )
        + _fact("kref:CollateralizedLoanObligationsNet", "c-6", CLO)
        + _fact("kref:CollateralizedLoanObligationsNet", "c-310", "400,000")
    )
    found = inline_facts(html, "kref:CollateralizedLoanObligationsNet")
    assert found == [(date(2025, 12, 31), 1_198_332_000)]


def test_scale_is_applied():
    """Filings report in thousands. An unscaled read is wrong by 1000x."""
    html = _context("c-6", "2025-12-31") + _fact("us-gaap:Liabilities", "c-6", "5,239,439")
    assert inline_facts(html, "us-gaap:Liabilities")[0][1] == 5_239_439_000


# ------------------------------------------------------------- the ruling


def test_securitisation_is_excluded_and_repo_is_included():
    """The CIO's ruling, in arithmetic, against KREF's real balance sheet."""
    got = _by_metric(leverage_perimeter(doc(kref_html())))

    # Regulatory: repo + secured term loan over equity.
    assert got[M_LEVERAGE_REG].value == (2_862_689 + 632_516) / 1_172_550
    assert round(got[M_LEVERAGE_REG].value, 2) == 2.98

    # Economic: total liabilities less the non-recourse CLO, over equity.
    assert got[M_LEVERAGE_ECON].value == (5_239_439 - 1_198_332) / 1_172_550
    assert round(got[M_LEVERAGE_ECON].value, 2) == 3.45


def test_the_perimeter_moves_both_rows_not_just_one():
    """Unadjusted, KREF reads 2.45x and 4.47x. Neither survives the ruling.

    A perimeter states which obligations are this filer's leverage. Applying it
    to one row only would leave the excluded $1.2bn visible on the other, so the
    two rows would describe different entities.
    """
    got = _by_metric(leverage_perimeter(doc(kref_html())))
    unadjusted_reg = 2_871_049 / 1_172_550  # DebtInstrumentCarryingAmount / equity
    unadjusted_econ = 5_239_439 / 1_172_550  # total liabilities / equity
    assert abs(got[M_LEVERAGE_REG].value - unadjusted_reg) > 0.4
    assert abs(got[M_LEVERAGE_ECON].value - unadjusted_econ) > 1.0


def test_prior_year_figures_are_never_mixed_in():
    """Same tags, previous balance sheet date. Mixing years reads plausibly."""
    got = _by_metric(leverage_perimeter(doc(kref_html())))
    # Equity 1,100,000 from c-7 would give 3.18x regulatory -- also believable.
    assert round(got[M_LEVERAGE_REG].value, 2) != 3.18


def test_a_missing_recourse_component_blanks_rather_than_part_summing():
    """A partial sum is a smaller, wrong ratio that looks entirely reasonable."""
    got = _by_metric(leverage_perimeter(doc(kref_html(**{"us-gaap:SecuredDebt": ""}))))
    assert M_LEVERAGE_REG not in got
    assert M_LEVERAGE_ECON in got  # the other row is unaffected


def test_a_missing_securitisation_balance_blanks_the_economic_row():
    """Without the excluded balance there is no ruled economic figure.

    Falling back to raw total liabilities would publish the number the CIO
    ruled against, on a row labelled as though the ruling had been applied.
    """
    got = _by_metric(
        leverage_perimeter(doc(kref_html(**{"kref:CollateralizedLoanObligationsNet": ""})))
    )
    assert M_LEVERAGE_ECON not in got
    assert M_LEVERAGE_REG in got


def test_a_filer_without_a_ruled_perimeter_gets_nothing_here():
    """Only a client ruling creates a perimeter; none is ever inferred."""
    other = Fund(
        name="Golub Capital BDC", ticker="GBDC", cik="1476765", entity_type="bdc",
        fiscal_year_end="09-30", primary_forms=("10-K",),
        supported_metrics=(M_LEVERAGE_REG,),
    )
    assert leverage_perimeter(Doc(other, FILING, kref_html())) == []


def test_the_ruling_travels_with_the_number():
    """Provenance has to defend the exclusion, not just the arithmetic."""
    got = _by_metric(leverage_perimeter(doc(kref_html())))
    excerpt = got[M_LEVERAGE_ECON].provenance.excerpt
    assert "securitisation excluded" in excerpt and "repo included" in excerpt
    assert "kref:CollateralizedLoanObligationsNet" in excerpt
