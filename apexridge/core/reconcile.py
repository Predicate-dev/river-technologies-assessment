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
    M_INCENTIVE_FEE,
    M_MGMT_FEE,
    METRIC_SANE_RANGE,
    METRIC_UNITS,
    M_DIST_YIELD,
    M_LEVERAGE,
    M_NAV_PS,
    Fund,
)
from .confidence import (
    STALE_LIMIT_DAYS,
    SUPPRESS_BELOW,
    grade,
    is_measurement,
    score_candidate,
    values_agree,
)
from .models import (
    Candidate,
    Conflict,
    Confidence,
    ResolvedMetric,
    Suppression,
    SuppressionLog,
    SuppressionReason,
)

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
    # A rate stated in the fund's own governing document beats a `cef:` fee
    # tag. Without this the tag wins basis selection on tier alone, and GBDC's
    # mis-contexted 0.0213% -- correctly tagged, from a notes prospectus rather
    # than the fund's fee table -- displaces the true 1.0% before the
    # confidence model ever gets to weigh them.
    M_MGMT_FEE: [
        ("fee_basis", "stated_annual_rate"),
        ("fee_basis", "pct_of_net_assets"),
        ("fee_basis", "stated_rate"),
        ("fee_basis", "as_tagged"),
    ],
    M_INCENTIVE_FEE: [
        ("fee_basis", "stated_rate"),
        ("fee_basis", "pct_of_net_assets"),
        ("fee_basis", "as_tagged"),
    ],
}


# Flags that do not merely weaken a value -- they mean the construction did not
# measure the metric at all. TAKIX reports 0.00 in every N-PORT borrowing field
# while carrying $2.2bn of total liabilities on $4.47bn of net assets, so its
# gross-debt leverage ratio is 0.00: arithmetically correct and informationally
# empty. A confidence penalty is the wrong instrument for this, because the
# number is not uncertain, it is inapplicable.
DISQUALIFYING_FLAGS = frozenset({"zero_borrowings_but_material_total_liabilities"})


def _disqualified(cand: Candidate) -> bool:
    return any(f in DISQUALIFYING_FLAGS for f in cand.flags)


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


def _cluster(group: list[Candidate]) -> list[list[Candidate]]:
    """Group same-basis candidates into clusters of mutually-agreeing values."""
    clusters: list[list[Candidate]] = []
    for cand in sorted(group, key=lambda c: c.value):
        for cl in clusters:
            if values_agree(cl[0].value, cand.value, cand.unit):
                cl.append(cand)
                break
        else:
            clusters.append([cand])
    return clusters


def _independent_count(cluster: list[Candidate]) -> int:
    """How many genuinely distinct observations a cluster represents.

    The same table matched twice through two anchor phrases is one observation,
    not two. Counting distinct (tier, accession, locator-shape) triples keeps a
    repeated match from voting itself into the deck.
    """
    return len({(c.tier, c.provenance.accession, tuple(c.transforms)) for c in cluster})


def _in_force(group: list[Candidate], when: date) -> list[Candidate]:
    """Drop candidates the filing explicitly dates outside the reporting quarter.

    The client resolves a fee to the rate in force *during the reporting
    quarter*, not to whichever rate is current now. Where a filing supplies an
    effective date this answers it outright; where it does not, `in_force_at`
    returns None and the candidate is kept for the evidence-weight rules below.
    Undated candidates are never discarded -- most filings state a rate without
    dating it.
    """
    dated_out = [c for c in group if c.in_force_at(when) is False]
    if not dated_out or len(dated_out) == len(group):
        return group  # nothing to exclude, or excluding all would leave nothing
    return [c for c in group if c.in_force_at(when) is not False]


def _resolve_within_basis(
    metric: str, group: list[Candidate], reference_date: date | None = None
) -> tuple[Candidate, list[Candidate], Conflict | None]:
    """Pick one candidate from a same-basis group and log any conflict.

    Resolution is a weight of evidence, in this order:
      1. **Corroboration.** The value the most independent extractions agree on.
         Two filings and a table agreeing on 1.00% beats one regex finding
         1.50% deep in an appendix.
      2. **Fewest extraction flags.** A clean derived value beats a flagged
         high-tier one -- this is the GBDC management-fee case, where a
         correctly-tagged XBRL fact came from the wrong document.
      3. **Highest source tier**, then **most recent period**.
    """
    if reference_date is not None:
        group = _in_force(group, reference_date)
    clusters = _cluster(group)
    clusters.sort(
        key=lambda cl: (
            # A rate the filing itself describes as superseded can never beat a
            # current one, whatever else it has going for it. Flag *count* is
            # too crude a tiebreak here: it let TAKIX's 1.50% rate, retired in
            # 2020, outrank the current 1.00% on recency alone because both
            # carried exactly one flag.
            not any(is_measurement(c) for c in cl),
            -_independent_count(cl),
            min(len(c.flags) for c in cl),
            -max(c.tier.base_score for c in cl),
            -max((c.as_of.toordinal() if c.as_of else 0) for c in cl),
        )
    )
    winner = clusters[0]
    chosen = sorted(
        winner,
        key=lambda c: (
            len(c.flags),
            -c.tier.base_score,
            -(c.as_of.toordinal() if c.as_of else 0),
        ),
    )[0]
    others = [c for c in group if c is not chosen]

    losing = [c for cl in clusters[1:] for c in cl]
    conflict = None
    if losing:
        values = [chosen.value] + [c.value for c in losing]
        mid = sorted(values)[len(values) // 2] or 1.0
        spread = (max(values) - min(values)) / abs(mid) * 100.0
        rationale = (
            f"kept {chosen.value:.4g}: agreed on by {_independent_count(winner)} "
            f"independent extraction(s) vs "
            + ", ".join(
                f"{cl[0].value:.4g} ({_independent_count(cl)})" for cl in clusters[1:]
            )
            + f"; chosen source {chosen.tier.value}"
            + (f", flags {chosen.flags}" if chosen.flags else ", no flags")
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


def _suppress(metric_obj: ResolvedMetric, notice: Suppression) -> ResolvedMetric:
    """Blank a cell and attach its defence. The only path that nulls a value.

    Keeping this the single entry point is what lets `ResolvedMetric.value is
    None` guarantee `suppression is not None`, which the render layer relies on
    to make a bare blank unrepresentable.
    """
    metric_obj.value = None
    metric_obj.confidence = Confidence.SUPPRESSED
    metric_obj.suppression = notice
    metric_obj.notes.append(notice.cell_label)
    return metric_obj


def reconcile_metric(
    fund: Fund,
    metric: str,
    candidates: list[Candidate],
    reference_date: date,
    notices: SuppressionLog | None = None,
) -> ResolvedMetric:
    unit = METRIC_UNITS.get(metric, "pct")
    if not candidates:
        # Prefer the extractor's specific diagnosis ("4.7y of NAV history, 5Y
        # window not covered") over the generic absence. This is the whole
        # reason SuppressionLog exists: the useful sentence is known upstream,
        # where the data ran out, not here.
        notice = notices.get(fund.ticker, metric) if notices else None
        return _suppress(
            ResolvedMetric(
                fund_ticker=fund.ticker,
                metric=metric,
                unit=unit,
                value=None,
                confidence=Confidence.SUPPRESSED,
                score=0.0,
                chosen=None,
            ),
            notice
            or Suppression(
                fund_ticker=fund.ticker,
                metric=metric,
                reason=SuppressionReason.NO_CANDIDATE,
                detail="no candidate value found in any source",
            ),
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

    # A disqualified primary basis is NOT silently replaced by the next basis
    # down. Falling through would quietly answer the question the client has
    # escalated -- whether leverage is measured on a regulatory (borrowings) or
    # economic (total liabilities) basis -- by picking the economic one and not
    # saying so. The cell blanks and names both readings instead.
    if all(_disqualified(c) for c in primary_group):
        alt = [
            min(g, key=lambda c: (len(c.flags), -c.tier.base_score))
            for _, g in ordered_bases[1:]
        ]
        disq = min(primary_group, key=lambda c: (len(c.flags), -c.tier.base_score))
        alt_text = "; ".join(
            f"{c.basis.get('leverage_basis') or c.basis_key or 'alternative basis'} "
            f"= {c.value:.4g}"
            for c in alt
        )
        return _suppress(
            ResolvedMetric(
                fund_ticker=fund.ticker,
                metric=metric,
                value=None,
                unit=unit,
                confidence=Confidence.SUPPRESSED,
                score=0.0,
                chosen=None,
                alternatives=alt,
            ),
            Suppression(
                fund_ticker=fund.ticker,
                metric=metric,
                reason=SuppressionReason.BASIS_DISQUALIFIED,
                detail=(
                    "the filer reports no borrowings while carrying material "
                    "total liabilities, so the reported basis does not measure "
                    "leverage; the basis to use is with the client"
                ),
                as_of=disq.as_of,
                internal_note=(
                    f"appendix only: disqualified {primary_key or 'primary basis'} "
                    f"= {disq.value:.4g}"
                    + (f"; {alt_text}" if alt_text else "")
                    + "; not substituted, that choice is the open CIO question"
                ),
            ),
        )

    chosen, same_basis_others, conflict = _resolve_within_basis(
        metric, primary_group, reference_date
    )

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

    resolved = ResolvedMetric(
        fund_ticker=fund.ticker,
        metric=metric,
        value=chosen.value,
        unit=unit,
        confidence=grade(score),
        score=score,
        chosen=chosen,
        alternatives=alternatives,
        conflict=conflict,
        score_inputs=audit,
        notes=notes,
    )

    # Staleness is checked before the confidence floor, and independently of it:
    # a six-month-old figure is blanked however strong its evidence is. Checking
    # it first also means the cell carries the more useful of the two reasons --
    # "the data stops here" tells the reader what to do next, "confidence 0.31"
    # does not.
    # Terms metrics measure staleness from the last filing that could have
    # amended the rate, not from the document we read: a contractual rate
    # cannot change without a filing (Lara, Window 2).
    clock = chosen.staleness_date
    age_days = (reference_date - clock).days if clock else None
    if age_days is not None and age_days > STALE_LIMIT_DAYS:
        return _suppress(
            resolved,
            Suppression(
                fund_ticker=fund.ticker,
                metric=metric,
                reason=SuppressionReason.STALE_BEYOND_LIMIT,
                detail=(
                    f"most recent reported figure is {age_days}d old, beyond the "
                    f"{STALE_LIMIT_DAYS}d limit"
                ),
                as_of=chosen.as_of,
                internal_note=(
                    f"suppressed value was {chosen.value:.4g} {unit} "
                    f"({chosen.tier.value}, score {score:.2f})"
                ),
            ),
        )

    if score < SUPPRESS_BELOW:
        # Below the floor we publish the absence, not the number. A blank cell
        # with a reason is defensible to a board; a bad number is not.
        reasons = "; ".join(f["flag"] for f in audit["penalties"]) or "insufficient evidence"
        return _suppress(
            resolved,
            Suppression(
                fund_ticker=fund.ticker,
                metric=metric,
                reason=SuppressionReason.BELOW_CONFIDENCE_FLOOR,
                detail=(
                    f"evidence below the reporting floor "
                    f"({score:.2f} < {SUPPRESS_BELOW:.2f}): {reasons}"
                ),
                as_of=chosen.as_of,
                internal_note=f"suppressed value was {chosen.value:.4g} {unit}",
            ),
        )

    return resolved


def reconcile_fund(
    fund: Fund,
    candidates: Iterable[Candidate],
    reference_date: date,
    metrics: Iterable[str] = ALL_METRICS,
    notices: SuppressionLog | None = None,
) -> dict[str, ResolvedMetric]:
    grouped: dict[str, list[Candidate]] = defaultdict(list)
    for c in candidates:
        grouped[c.metric].append(c)

    out: dict[str, ResolvedMetric] = {}
    for metric in metrics:
        if metric not in fund.supported_metrics:
            # Structural absence outranks every evidential one: the filer does
            # not publish this concept, so there is nothing to be stale or
            # low-confidence about. This is the KREF net-return case.
            out[metric] = _suppress(
                ResolvedMetric(
                    fund_ticker=fund.ticker,
                    metric=metric,
                    value=None,
                    unit=METRIC_UNITS.get(metric, "pct"),
                    confidence=Confidence.SUPPRESSED,
                    score=0.0,
                    chosen=None,
                ),
                Suppression(
                    fund_ticker=fund.ticker,
                    metric=metric,
                    reason=SuppressionReason.NOT_APPLICABLE,
                    detail=(
                        f"not reported by a {fund.entity_type.replace('_', ' ')}; "
                        "left blank rather than substituted with a near-metric on "
                        "an incomparable basis"
                    ),
                ),
            )
            continue
        out[metric] = reconcile_metric(
            fund, metric, grouped.get(metric, []), reference_date, notices
        )
    return out
