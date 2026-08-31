"""Reconciling candidates into the single number that reaches the board deck.

Two different things get conflated as "disagreement", and the distinction is the
whole point of this module:

  * **Basis differences** are not errors. Gross-debt leverage and
    total-liabilities leverage measure different things and *should* differ.
    Averaging them produces a number that describes nothing. We pick a basis by
    published policy, report the alternative alongside, and never blend them.

  * **Conflicts** are two independent attempts to measure the *same thing on the
    same basis* that disagree beyond tolerance. Those are real, they get logged
    with a resolution and a rationale, and they cost confidence.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date
from typing import Any, Iterable

from ..config import (
    ALL_METRICS,
    METRIC_SANE_RANGE,
    METRIC_UNITS,
    M_DIST_YIELD,
    M_LEVERAGE,
    M_NAV_PS,
    Fund,
)
from .confidence import SUPPRESS_BELOW, grade, score_candidate, values_agree
from .models import Candidate, Conflict, Confidence, ResolvedMetric

log = logging.getLogger(__name__)

# Which basis wins when a metric can be constructed several defensible ways.
# These are policy choices, not facts -- they are stated here so a reviewer can
# disagree with them in one place rather than reverse-engineering them from
# output. Each is logged in NOTES/decisions.md with its reasoning.
BASIS_PREFERENCE: dict[str, list[tuple[str, str]]] = {
    # Apex Ridge reports its own leverage as a debt-to-equity ratio around
    # 1.0x, which is a borrowings-based measure. Matching that basis is what
    # makes the comparison meaningful; total liabilities would flatter Apex.
    M_LEVERAGE: [
        ("leverage_basis", "gross_debt_to_equity"),
        ("leverage_basis", "total_liabilities_to_equity"),
    ],
    # "Annualized distribution rate" in the brief. Run-rate is the standard
    # reading and reflects a distribution change immediately; the trailing
    # figure is carried as the alternative because it is what LP reporting
    # usually shows. Confirmed as an open question with the client.
    M_DIST_YIELD: [
        ("yield_basis", "current_quarter_annualized"),
        ("yield_basis", "trailing_12m"),
    ],
    # A REIT's book value per share is not a fund NAV. Prefer a real NAV where
    # one exists; fall back to book value only with its flag attached.
    M_NAV_PS: [
        ("measure", "nav_per_share"),
        ("measure", "book_value_per_share"),
    ],
}


def _basis_rank(metric: str, cand: Candidate) -> int:
    prefs = BASIS_PREFERENCE.get(metric)
    if not prefs:
        return 0
    for i, (key, val) in enumerate(prefs):
        if cand.basis.get(key) == val:
            return i
    return len(prefs)  # unknown basis sorts last


def _sanity_check(cand: Candidate) -> None:
    """Attach a flag if a value is outside the plausible range for its metric.

    Deliberately a flag, not a drop: a value outside range is usually a unit or
    scale error, and the audit trail is more useful than a silent omission.
    """
    lo, hi = METRIC_SANE_RANGE.get(cand.metric, (float("-inf"), float("inf")))
    if not (lo <= cand.value <= hi):
        flag = "out_of_sane_range"
        if flag not in cand.flags:
            cand.flags.append(flag)


def _resolve_within_basis(
    metric: str, group: list[Candidate]
) -> tuple[Candidate, list[Candidate], Conflict | None]:
    """Pick one candidate from a same-basis group and log any conflict.

    Resolution order: fewest flags, then highest source tier, then most recent
    period. "Fewest flags" leads deliberately -- a clean derived value beats a
    flagged XBRL fact, which is the GBDC management-fee case (a correctly-tagged
    number from the wrong document).
    """
    ranked = sorted(
        group,
        key=lambda c: (
            len(c.flags),
            -c.tier.base_score,
            -(c.as_of.toordinal() if c.as_of else 0),
        ),
    )
    chosen, others = ranked[0], ranked[1:]

    disagreeing = [c for c in others if not values_agree(chosen.value, c.value, chosen.unit)]
    conflict = None
    if disagreeing:
        values = [chosen.value] + [c.value for c in disagreeing]
        mid = sorted(values)[len(values) // 2] or 1.0
        spread = (max(values) - min(values)) / abs(mid) * 100.0
        rationale = (
            f"kept the value with fewest extraction flags ({len(chosen.flags)}) "
            f"and highest source tier ({chosen.tier.value}); "
            f"rejected {len(disagreeing)} value(s) at "
            + ", ".join(f"{c.value:.4g} [{c.tier.value}, flags={c.flags or 'none'}]"
                        for c in disagreeing)
        )
        conflict = Conflict(
            fund_ticker=chosen.fund_ticker,
            metric=metric,
            values=values,
            spread_pct=spread,
            resolution=f"{chosen.value:.4g} ({chosen.tier.value})",
            rationale=rationale,
            candidates=group,
        )
        log.info(
            "conflict %s/%s: %s -> kept %.4g (spread %.1f%%)",
            chosen.fund_ticker, metric, [round(v, 4) for v in values], chosen.value, spread,
        )
    return chosen, others, conflict


def reconcile_metric(
    fund: Fund,
    metric: str,
    candidates: list[Candidate],
    reference_date: date,
) -> ResolvedMetric:
    unit = METRIC_UNITS.get(metric, "pct")
    if not candidates:
        return ResolvedMetric(
            fund_ticker=fund.ticker,
            metric=metric,
            value=None,
            unit=unit,
            confidence=Confidence.SUPPRESSED,
            score=0.0,
            chosen=None,
            notes=["no candidate value found in any source"],
        )

    for c in candidates:
        _sanity_check(c)

    by_basis: dict[str, list[Candidate]] = defaultdict(list)
    for c in candidates:
        by_basis[c.basis_key].append(c)

    # Rank bases by policy; the winner supplies the headline value.
    ordered_bases = sorted(
        by_basis.items(),
        key=lambda kv: (_basis_rank(metric, kv[1][0]), -max(c.tier.base_score for c in kv[1])),
    )
    primary_key, primary_group = ordered_bases[0]
    chosen, same_basis_others, conflict = _resolve_within_basis(metric, primary_group)

    score, audit = score_candidate(chosen, same_basis_others, reference_date)

    notes: list[str] = []
    alternatives = list(same_basis_others)
    for key, group in ordered_bases[1:]:
        best = min(group, key=lambda c: (len(c.flags), -c.tier.base_score))
        alternatives.append(best)
        notes.append(
            f"alternative basis [{key or 'default'}]: {best.value:.4g} "
            f"({best.tier.value}) -- reported separately, not blended"
        )

    if conflict:
        audit["conflict_spread_pct"] = round(conflict.spread_pct, 2)

    confidence = grade(score)
    value: float | None = chosen.value
    if score < SUPPRESS_BELOW:
        # Below the floor we publish the absence, not the number. A blank cell
        # with a reason is defensible to a board; a bad number is not.
        value = None
        confidence = Confidence.SUPPRESSED
        notes.append(
            f"suppressed: confidence {score:.2f} below floor {SUPPRESS_BELOW:.2f} "
            f"({'; '.join(f['flag'] for f in audit['penalties']) or 'insufficient evidence'})"
        )

    return ResolvedMetric(
        fund_ticker=fund.ticker,
        metric=metric,
        value=value,
        unit=unit,
        confidence=confidence,
        score=score,
        chosen=chosen,
        alternatives=alternatives,
        conflict=conflict,
        score_inputs=audit,
        notes=notes,
    )


def reconcile_fund(
    fund: Fund,
    candidates: Iterable[Candidate],
    reference_date: date,
    metrics: Iterable[str] = ALL_METRICS,
) -> dict[str, ResolvedMetric]:
    grouped: dict[str, list[Candidate]] = defaultdict(list)
    for c in candidates:
        grouped[c.metric].append(c)

    out: dict[str, ResolvedMetric] = {}
    for metric in metrics:
        if metric not in fund.supported_metrics:
            out[metric] = ResolvedMetric(
                fund_ticker=fund.ticker,
                metric=metric,
                value=None,
                unit=METRIC_UNITS.get(metric, "pct"),
                confidence=Confidence.SUPPRESSED,
                score=0.0,
                chosen=None,
                notes=[
                    f"not applicable to a {fund.entity_type.replace('_', ' ')}; "
                    "excluded rather than reported on an incomparable basis"
                ],
            )
            continue
        out[metric] = reconcile_metric(fund, metric, grouped.get(metric, []), reference_date)
    return out
