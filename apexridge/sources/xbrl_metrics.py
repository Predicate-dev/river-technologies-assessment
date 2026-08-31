"""Metric extractors built on XBRL facts.

Deliberately emits *multiple* candidates per metric where more than one
defensible construction exists (e.g. leverage on a gross-debt basis vs. a
total-liabilities basis). That redundancy is the input to the confidence model:
agreement between independently-constructed values is the only evidence we have
that a number is right, given there is no answer key.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from ..config import (
    M_DIST_YIELD,
    M_INCENTIVE_FEE,
    M_LEVERAGE,
    M_MGMT_FEE,
    M_NAV_PS,
    M_RETURN_1Y,
    M_RETURN_3Y,
    M_RETURN_5Y,
    Fund,
)
from ..core.models import Candidate, SourceTier
from ..core.periods import Period, build_ledger, sum_between
from .xbrl import Fact, XbrlFacts

log = logging.getLogger(__name__)

EQUITY_TAGS = (
    "us-gaap:StockholdersEquity",
    "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
)
DEBT_TAGS = (
    "us-gaap:DebtInstrumentCarryingAmount",
    "us-gaap:SecuredDebt",
)
DPS_TAGS = (
    "us-gaap:CommonStockDividendsPerShareDeclared",
    "us-gaap:InvestmentCompanyDistributionToShareholdersPerShare",
)


def _first_available(facts: XbrlFacts, tags: tuple[str, ...], **kw: Any) -> tuple[str, Fact] | None:
    for t in tags:
        f = facts.latest(t, **kw)
        if f is not None:
            return t, f
    return None


# --------------------------------------------------------------------- NAV


def nav_per_share(facts: XbrlFacts, fund: Fund) -> list[Candidate]:
    out: list[Candidate] = []
    direct = facts.latest("us-gaap:NetAssetValuePerShare", instant=True)
    if direct:
        out.append(
            facts.candidate(
                M_NAV_PS,
                direct,
                unit="usd",
                basis={"measure": "nav_per_share", "class": "common"},
            )
        )

    # Independent construction: equity / shares outstanding. For a BDC this
    # should reproduce reported NAV/share almost exactly, which makes it a
    # genuine cross-check. For a REIT there is no "NAV" -- this is book value
    # per share and is labelled as such.
    eq = _first_available(facts, EQUITY_TAGS, instant=True)
    sh = facts.latest("us-gaap:CommonStockSharesOutstanding", instant=True)
    if eq and sh and sh.val:
        eq_tag, eq_fact = eq
        if eq_fact.end == sh.end:
            measure = "book_value_per_share" if fund.entity_type == "mortgage_reit" else "nav_per_share"
            out.append(
                facts.candidate(
                    M_NAV_PS,
                    eq_fact,
                    value=eq_fact.val / sh.val,
                    unit="usd",
                    tier=SourceTier.DERIVED,
                    basis={"measure": measure, "class": "common"},
                    transforms=[f"{eq_tag} / us-gaap:CommonStockSharesOutstanding"],
                    flags=(
                        ["reit_book_value_not_nav"]
                        if fund.entity_type == "mortgage_reit"
                        else []
                    ),
                    note="derived from equity / shares outstanding",
                )
            )
    return out


# ---------------------------------------------------------------- LEVERAGE


def leverage(facts: XbrlFacts, fund: Fund) -> list[Candidate]:
    """Debt-to-equity on every basis the filer's XBRL supports.

    These bases genuinely differ -- gross borrowings vs. total liabilities can
    be 20%+ apart -- so they are tagged with distinct `basis` values rather than
    being averaged together. The board deck's own footnote 2 concedes that
    regulatory vs. economic leverage varies by fund.
    """
    out: list[Candidate] = []
    eq = _first_available(facts, EQUITY_TAGS, instant=True)
    if not eq:
        return out
    eq_tag, eq_fact = eq
    if not eq_fact.val:
        return out

    # Basis 1: gross debt outstanding / equity. Closest to the BDC regulatory
    # asset-coverage concept the PMs mean by "leverage ratio".
    debt = _first_available(facts, DEBT_TAGS, instant=True)
    if debt:
        debt_tag, debt_fact = debt
        if debt_fact.end == eq_fact.end:
            out.append(
                facts.candidate(
                    M_LEVERAGE,
                    debt_fact,
                    value=debt_fact.val / eq_fact.val,
                    unit="ratio",
                    tier=SourceTier.DERIVED,
                    basis={"leverage_basis": "gross_debt_to_equity"},
                    transforms=[f"{debt_tag} / {eq_tag}"],
                    note="regulatory-style: borrowings / net assets",
                )
            )

    # Basis 2: total liabilities / equity. Economic leverage; includes payables
    # and derivative liabilities, so it reads higher.
    liab = facts.latest("us-gaap:Liabilities", instant=True)
    if liab and liab.end == eq_fact.end and eq_fact.val:
        out.append(
            facts.candidate(
                M_LEVERAGE,
                liab,
                value=liab.val / eq_fact.val,
                unit="ratio",
                tier=SourceTier.DERIVED,
                basis={"leverage_basis": "total_liabilities_to_equity"},
                transforms=[f"us-gaap:Liabilities / {eq_tag}"],
                note="economic: total liabilities / net assets",
            )
        )

    # Basis 2b: (assets - equity) / equity. Same concept as basis 2 from an
    # independent pair of tags -- a pure internal-consistency probe. If this
    # disagrees with basis 2, the filer's balance sheet tagging is inconsistent
    # and every derived number for this fund should be downgraded.
    assets = facts.latest("us-gaap:Assets", instant=True)
    if assets and assets.end == eq_fact.end and eq_fact.val:
        out.append(
            facts.candidate(
                M_LEVERAGE,
                assets,
                value=(assets.val - eq_fact.val) / eq_fact.val,
                unit="ratio",
                tier=SourceTier.DERIVED,
                basis={"leverage_basis": "total_liabilities_to_equity"},
                transforms=[f"(us-gaap:Assets - {eq_tag}) / {eq_tag}"],
                note="economic, via assets minus equity (consistency probe)",
            )
        )
    return out


# --------------------------------------------------------- DISTRIBUTIONS


def dps_ledger(facts: XbrlFacts) -> list[Period]:
    """Non-overlapping per-share distribution periods.

    Built from every duration-tagged distribution fact across both relevant
    tags. The ledger differences fiscal-year-to-date cumulatives to recover
    quarters the filer never tagged standalone -- notably a BDC's fiscal Q4,
    which appears only inside the 10-K annual total. Missing it understates a
    year of total return by roughly a full quarterly distribution.
    """
    rows: list[tuple[date, date, float, str]] = []
    for tag in DPS_TAGS:
        for f in facts.series(tag, instant=False):
            if f.start and f.end:
                rows.append((f.start, f.end, f.val, f"{f.qname}@{f.accn}"))
    return build_ledger(rows)


def _latest_quarter(ledger: list[Period]) -> Period | None:
    quarters = [p for p in ledger if 80 <= p.days <= 100]
    return quarters[-1] if quarters else None


def distribution_yield(facts: XbrlFacts, fund: Fund) -> list[Candidate]:
    """Annualized distribution yield on NAV, on two standard bases.

    Both are reported because they answer different questions and can diverge
    sharply: when a fund cuts its distribution, the run-rate basis reflects it
    immediately and the trailing basis lags by up to a year. Collapsing them to
    one number would hide exactly the signal a PM is benchmarking for.
    """
    out: list[Candidate] = []
    ledger = dps_ledger(facts)
    latest = _latest_quarter(ledger)
    if not latest:
        return out
    navs = nav_per_share(facts, fund)
    nav = next((c for c in navs if c.tier == SourceTier.XBRL), None) or (navs[0] if navs else None)
    if nav is None or not nav.value:
        return out

    anchor = facts.at(
        "us-gaap:CommonStockDividendsPerShareDeclared", latest.end, tolerance_days=10
    ) or facts.latest("us-gaap:CommonStockDividendsPerShareDeclared")
    if anchor is None:
        return out

    # Basis 1: most recent quarter, annualized by day count.
    ann_factor = 365.25 / latest.days
    out.append(
        facts.candidate(
            M_DIST_YIELD,
            anchor,
            value=100.0 * (latest.value * ann_factor) / nav.value,
            unit="pct",
            tier=SourceTier.DERIVED,
            basis={"yield_basis": "current_quarter_annualized", "denominator": "nav"},
            transforms=[
                f"DPS {latest.value:.4f} ({latest.start}..{latest.end}, {latest.source}) "
                f"x {ann_factor:.3f} / NAV {nav.value:.4f}"
            ],
            flags=(["distribution_period_derived"] if latest.source != "tagged" else []),
            note="run-rate annualized",
        )
    )

    # Basis 2: trailing twelve months.
    ttm_start = latest.end - timedelta(days=364)
    total, used, complete = sum_between(ledger, ttm_start, latest.end)
    if used:
        flags = [] if complete else ["ttm_window_incomplete"]
        out.append(
            facts.candidate(
                M_DIST_YIELD,
                anchor,
                value=100.0 * total / nav.value,
                unit="pct",
                tier=SourceTier.DERIVED,
                basis={"yield_basis": "trailing_12m", "denominator": "nav"},
                transforms=[
                    f"sum of {len(used)} distribution periods "
                    f"({used[0].start}..{used[-1].end}) = {total:.4f} / NAV {nav.value:.4f}"
                ],
                flags=flags,
                note="trailing twelve months",
            )
        )
    return out


# -------------------------------------------------------------- RETURNS


def _nav_series(facts: XbrlFacts) -> list[Fact]:
    """One NAV observation per period end, preferring the original filing."""
    rows = facts.series("us-gaap:NetAssetValuePerShare", instant=True)
    best: dict[date, Fact] = {}
    for f in rows:
        if not f.end:
            continue
        cur = best.get(f.end)
        if cur is None or (f.filed and cur.filed and f.filed < cur.filed):
            best[f.end] = f
    return sorted(best.values(), key=lambda f: f.end)  # type: ignore[arg-type]


# How far the available NAV history may miss the exact trailing window before
# the figure stops being what it claims to be. A "5-year return" measured over
# 4.75 years is not a 5-year return, so we suppress rather than mislabel.
_WINDOW_TOLERANCE_DAYS = {1: 20, 3: 45, 5: 60}
_MAX_INTERNAL_GAP_DAYS = 200


def nav_total_returns(facts: XbrlFacts, fund: Fund) -> list[Candidate]:
    """Trailing 1/3/5-year annualized NAV total return.

    Neither BDC publishes an annualized trailing net return in its filings --
    the manual analyst process read it off a factsheet or computed it. We
    compute it explicitly so the method is auditable:

        period TR  = (NAV_end - NAV_start + distributions_in_period) / NAV_start
        annualized = prod(1 + TR) ** (365.25 / elapsed_days) - 1

    Assumes distributions reinvested at period-end NAV. NAV is already net of
    fees, so this is a net return. It is *not* a market-price total return: a
    listed BDC trading at a discount will show a materially different number,
    and the two must never be compared side by side without labelling.
    """
    out: list[Candidate] = []
    navs = _nav_series(facts)
    if len(navs) < 3:
        return out
    ledger = dps_ledger(facts)
    end_fact = navs[-1]
    end_date: date = end_fact.end  # type: ignore[assignment]

    for metric, years in ((M_RETURN_1Y, 1), (M_RETURN_3Y, 3), (M_RETURN_5Y, 5)):
        target = end_date - timedelta(days=round(365.25 * years))
        tol = _WINDOW_TOLERANCE_DAYS[years]
        anchor = min(
            (n for n in navs[:-1] if n.end),
            key=lambda n: abs((n.end - target).days),  # type: ignore[operator]
            default=None,
        )
        if anchor is None:
            continue
        drift = abs((anchor.end - target).days)  # type: ignore[operator]
        if drift > tol:
            log.info(
                "%s %s: no NAV anchor within %dd of %s (closest %s, off by %dd) -- suppressed",
                fund.ticker, metric, tol, target, anchor.end, drift,
            )
            continue

        window = [n for n in navs if n.end and anchor.end <= n.end <= end_date]
        if len(window) < 2 or window[0].val <= 0:
            continue

        growth = 1.0
        flags: list[str] = []
        derived_periods = 0
        max_gap = 0
        ok = True
        for prev, cur in zip(window, window[1:]):
            gap = (cur.end - prev.end).days  # type: ignore[operator]
            max_gap = max(max_gap, gap)
            dist, used, complete = sum_between(
                ledger, prev.end + timedelta(days=1), cur.end  # type: ignore[operator]
            )
            if not complete:
                flags.append(f"incomplete_distributions_{prev.end}..{cur.end}")
            derived_periods += sum(1 for p in used if p.source != "tagged")
            if prev.val <= 0:
                ok = False
                break
            growth *= (cur.val - prev.val + dist) / prev.val + 1.0
        if not ok:
            continue
        if max_gap > _MAX_INTERNAL_GAP_DAYS:
            # An annual-only stretch inside the window makes the distribution
            # attribution unreliable; say so rather than quietly averaging.
            flags.append(f"nav_history_gap_{max_gap}d")

        elapsed = (end_date - window[0].end).days  # type: ignore[operator]
        if elapsed <= 0:
            continue
        ann = (growth ** (365.25 / elapsed) - 1.0) * 100.0
        if derived_periods:
            flags.append(f"{derived_periods}_distribution_periods_derived")
        out.append(
            facts.candidate(
                metric,
                end_fact,
                value=ann,
                unit="pct",
                tier=SourceTier.DERIVED,
                basis={
                    "return_basis": "nav_total_return",
                    "net_of_fees": True,
                    "reinvested": True,
                },
                transforms=[
                    f"chain-linked {len(window) - 1} NAV periods "
                    f"({window[0].end}..{end_date}, {elapsed}d), annualized to {years}Y"
                ],
                flags=flags,
                note=f"derived trailing {years}Y",
            )
        )
    return out


# ------------------------------------------------------------------- FEES


def fee_percents(facts: XbrlFacts, fund: Fund) -> list[Candidate]:
    """Fee percentages from `cef:` fee-table tags.

    Treated with suspicion by design. These tags carry a `pure` unit (a decimal
    fraction), and in practice the filer's agent sometimes tags the fee table of
    an unrelated offering document -- a notes prospectus rather than the fund's
    own N-2. We emit the candidate so the disagreement is visible in the audit
    trail, but flag the document context so reconciliation can weigh it against
    the narrative source rather than deferring to it on tier alone.
    """
    out: list[Candidate] = []
    spec = (
        (M_MGMT_FEE, "cef:ManagementFeesPercent"),
        (M_INCENTIVE_FEE, "cef:IncentiveFeesPercent"),
    )
    # Fee tables belong to registration/prospectus forms. Anything else is a
    # context we do not trust for a headline fee rate.
    trusted_forms = {"N-2", "N-2/A", "486BPOS", "497", "424B3"}
    for metric, qname in spec:
        f = facts.latest(qname)
        if not f:
            continue
        pct = f.val * 100.0  # `pure` is a decimal fraction
        flags = []
        if f.form.upper() not in trusted_forms:
            flags.append(f"fee_table_from_{f.form}_not_fund_prospectus")
        if pct < 0.25:
            # No externally-managed credit fund charges under 25bps of assets.
            flags.append("implausibly_low_for_entity_type")
        out.append(
            facts.candidate(
                metric,
                f,
                value=pct,
                unit="pct",
                tier=SourceTier.XBRL,
                basis={"fee_basis": "as_tagged"},
                transforms=["pure fraction x 100"],
                flags=flags,
                note="cef fee-table tag",
            )
        )
    return out


def extract_all(facts: XbrlFacts, fund: Fund) -> list[Candidate]:
    out: list[Candidate] = []
    for fn in (nav_per_share, leverage, distribution_yield, nav_total_returns, fee_percents):
        try:
            out.extend(fn(facts, fund))
        except Exception:  # one bad metric must not sink the run
            log.exception("%s failed for %s", fn.__name__, fund.ticker)
    return [c for c in out if c.metric in fund.supported_metrics]
