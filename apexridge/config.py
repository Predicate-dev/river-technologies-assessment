"""Fund registry and pipeline constants.

The fund registry is deliberately hand-curated rather than discovered at
runtime: the four competitors differ in regulatory type, filing forms and
fiscal year-end, and those differences drive which source adapters can run.
Getting them wrong produces confidently-wrong numbers, so they are stated
explicitly and checked against EDGAR in tests.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
OUTPUT_DIR = REPO_ROOT / "output"
CACHE_DIR = REPO_ROOT / ".cache"

# SEC requires a descriptive User-Agent with contact info on every request.
# https://www.sec.gov/os/webmaster-faq#developers
SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "Apex Ridge Capital Benchmarking (engineering@apexridge.example.com)",
)
SEC_MAX_RPS = 8.0  # SEC's published ceiling is 10/s; leave headroom.


@dataclass(frozen=True)
class Fund:
    """A competitor fund and the facts that determine how we can read it."""

    name: str
    ticker: str
    cik: str
    entity_type: str  # "bdc" | "interval_fund" | "mortgage_reit"
    fiscal_year_end: str  # MM-DD
    # Forms this filer actually uses, most useful first.
    primary_forms: tuple[str, ...]
    # Metrics this entity type can support on a like-for-like basis. Anything
    # outside this set is reported with an explicit basis caveat or suppressed.
    supported_metrics: tuple[str, ...]
    notes: str = ""

    @property
    def cik_int(self) -> int:
        return int(self.cik)

    @property
    def cik_padded(self) -> str:
        return f"{self.cik_int:010d}"


# Metric identifiers used throughout the pipeline.
M_RETURN_1Y = "net_return_1y_pct"
M_RETURN_3Y = "net_return_3y_pct"
M_RETURN_5Y = "net_return_5y_pct"
M_MGMT_FEE = "management_fee_pct"
M_INCENTIVE_FEE = "incentive_fee_pct"
M_HURDLE = "incentive_hurdle_pct"
M_NAV_PS = "nav_per_share_usd"
M_LEVERAGE = "leverage_ratio_dte"
M_DIST_YIELD = "distribution_yield_pct"

ALL_METRICS = (
    M_RETURN_1Y,
    M_RETURN_3Y,
    M_RETURN_5Y,
    M_MGMT_FEE,
    M_INCENTIVE_FEE,
    M_HURDLE,
    M_NAV_PS,
    M_LEVERAGE,
    M_DIST_YIELD,
)

METRIC_LABELS = {
    M_RETURN_1Y: "Net return, trailing 1Y (ann.)",
    M_RETURN_3Y: "Net return, trailing 3Y (ann.)",
    M_RETURN_5Y: "Net return, trailing 5Y (ann.)",
    M_MGMT_FEE: "Management fee",
    M_INCENTIVE_FEE: "Incentive fee",
    M_HURDLE: "Incentive hurdle",
    M_NAV_PS: "NAV per share",
    M_LEVERAGE: "Leverage (D/E)",
    M_DIST_YIELD: "Distribution yield (ann.)",
}

# Units, used by the normalizer to catch the classic 100x error.
METRIC_UNITS = {
    M_RETURN_1Y: "pct",
    M_RETURN_3Y: "pct",
    M_RETURN_5Y: "pct",
    M_MGMT_FEE: "pct",
    M_INCENTIVE_FEE: "pct",
    M_HURDLE: "pct",
    M_NAV_PS: "usd",
    M_LEVERAGE: "ratio",
    M_DIST_YIELD: "pct",
}

# Plausible ranges. A value outside these is not silently dropped -- it is
# flagged, which is how unit and scale errors surface instead of shipping.
METRIC_SANE_RANGE = {
    M_RETURN_1Y: (-50.0, 50.0),
    M_RETURN_3Y: (-50.0, 50.0),
    M_RETURN_5Y: (-50.0, 50.0),
    M_MGMT_FEE: (0.0, 5.0),
    M_INCENTIVE_FEE: (0.0, 30.0),
    M_HURDLE: (0.0, 15.0),
    M_NAV_PS: (0.5, 500.0),
    M_LEVERAGE: (0.0, 5.0),
    M_DIST_YIELD: (0.0, 30.0),
}

_FUND_METRICS = ALL_METRICS
# KREF is a mortgage REIT: it has no fund-style net return series and no N-2
# fee table. Pending client confirmation (NOTES/questions.md Q1) we restrict it
# to the metrics that genuinely map across entity types.
# KREF's external-manager agreement does carry an incentive hurdle (7.0% on
# trailing 12-month adjusted equity), and that IS comparable to Apex Ridge's
# 6.00% hurdle, so it stays in scope. Trailing fund-style net returns do not.
_REIT_METRICS = (M_MGMT_FEE, M_INCENTIVE_FEE, M_HURDLE, M_NAV_PS, M_LEVERAGE, M_DIST_YIELD)

FUNDS: tuple[Fund, ...] = (
    Fund(
        name="Cliffwater Corporate Lending Fund",
        ticker="CCLFX",
        cik="0001735964",
        entity_type="interval_fund",
        fiscal_year_end="03-31",
        primary_forms=("NPORT-P", "N-CSR", "N-CSRS", "486BPOS"),
        supported_metrics=_FUND_METRICS,
        notes="Non-traded interval fund. No 10-K. Only 6 cef XBRL tags, all "
        "senior-securities stress figures -- narrative extraction required "
        "for fees and stated returns.",
    ),
    Fund(
        name="Carlyle Tactical Private Credit Fund",
        ticker="TAKIX",
        cik="0001725472",
        entity_type="interval_fund",
        fiscal_year_end="12-31",
        primary_forms=("NPORT-P", "N-CSR", "N-CSRS", "424B3", "486BPOS"),
        supported_metrics=_FUND_METRICS,
        notes="Non-traded interval fund. Multi-share-class. 5 cef XBRL tags "
        "only.",
    ),
    Fund(
        name="Golub Capital BDC",
        ticker="GBDC",
        cik="0001476765",
        entity_type="bdc",
        fiscal_year_end="09-30",
        primary_forms=("10-K", "10-Q", "8-K"),
        supported_metrics=_FUND_METRICS,
        notes="Listed BDC, September fiscal year end. Rich XBRL: 189 us-gaap "
        "tags plus cef:ManagementFeesPercent / cef:IncentiveFeesPercent.",
    ),
    Fund(
        name="KKR Real Estate Finance Trust",
        ticker="KREF",
        cik="0001631596",
        entity_type="mortgage_reit",
        fiscal_year_end="12-31",
        primary_forms=("10-K", "10-Q", "8-K"),
        supported_metrics=_REIT_METRICS,
        notes="Mortgage REIT, NOT a BDC despite the brief's description. "
        "Externally managed by KKR; fee terms live in related-party notes and "
        "the proxy, not a prospectus fee table.",
    ),
)

FUNDS_BY_TICKER = {f.ticker: f for f in FUNDS}


def get_fund(ticker: str) -> Fund:
    return FUNDS_BY_TICKER[ticker.upper()]
