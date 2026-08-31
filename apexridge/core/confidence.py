"""The confidence model.

There is no answer key for this engagement -- the manual analyst process we are
replacing was the client's only source for these numbers. So confidence cannot
be an accuracy measurement. What it can be is an explicit, auditable statement
of how much *evidence* stands behind a value, built only from things we can
observe about the extraction itself:

    score = tier x agreement x freshness x product(penalties)

  tier        how the number was obtained (a typed XBRL fact vs. a model
              reading a footnote). Scores the mechanism, not the filer.
  agreement   whether independently-constructed values for the same thing on
              the same basis converge. This is the closest thing to ground
              truth available without an answer key, and it is the only factor
              that can raise a score.
  freshness   how stale the underlying filing period is relative to the
              benchmarking date.
  penalties   named, specific problems observed during extraction, each with a
              published multiplier.

Every input is recorded on the ResolvedMetric so a reviewer can audit the score
rather than take it on faith. Deliberately: nothing here asks a model how
confident it is.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..core.models import Candidate, Confidence, SourceTier

# Two candidates are "in agreement" if they fall within the looser of an
# absolute and a relative tolerance. Absolute tolerances matter for small
# percentages (a 10bp gap on a 1.25% fee is material; on a 10% return it is not).
TOLERANCE = {
    #  unit  -> (absolute, relative)
    "pct": (0.10, 0.010),
    "ratio": (0.02, 0.015),
    "usd": (0.02, 0.002),
}

AGREEMENT_CORROBORATED = 1.10  # >=2 independent sources converge
AGREEMENT_SINGLE = 0.90  # only one source; nothing to check it against
AGREEMENT_CONFLICT = 0.70  # independent sources disagree materially

# Named penalties. Each flag a source emits maps to a published multiplier; an
# unrecognised flag gets a mild default so a new flag can never silently pass.
FLAG_PENALTIES: dict[str, float] = {
    "out_of_sane_range": 0.30,
    "implausibly_low_for_entity_type": 0.35,
    "fee_table_from_": 0.60,  # prefix match: wrong document context
    "zero_borrowings_but_material_total_liabilities": 0.55,
    "reit_book_value_not_nav": 0.80,
    "incomplete_distributions_": 0.80,
    "ttm_window_incomplete": 0.85,
    "nav_history_gap_": 0.85,
    "fund_level_not_share_class_specific": 0.85,
    "outside_class_return_band": 0.50,
    "includes_unsettled_trades_and_payables": 0.90,
    "distribution_period_derived": 0.95,
    "_distribution_periods_derived": 0.95,  # suffix-style flag from returns
    "llm_low_agreement": 0.65,
    "single_extraction_pass": 0.90,
    "superseded_rate_present_in_source": 0.85,
    "implausible_incentive_fee_rate": 0.35,
    "fee_denominator_unstated": 0.92,
}
UNKNOWN_FLAG_PENALTY = 0.90

FRESHNESS_BANDS = ((100, 1.00), (200, 0.95), (400, 0.85))
FRESHNESS_STALE = 0.70

SUPPRESS_BELOW = 0.40

# Hard staleness limit, set by the client, not by us: a figure whose period end
# is older than six months is blanked outright regardless of how good the
# evidence behind it is. This is a separate mechanism from the freshness factor
# above -- that one degrades a score continuously, this one is a cliff. Both
# exist because they answer different questions: "how much do we trust this?"
# and "is the client willing to put it in front of a board?".
STALE_LIMIT_DAYS = 183


def tolerance_for(unit: str, value: float) -> float:
    absolute, relative = TOLERANCE.get(unit, TOLERANCE["pct"])
    return max(absolute, abs(value) * relative)


def values_agree(a: float, b: float, unit: str) -> bool:
    return abs(a - b) <= tolerance_for(unit, (abs(a) + abs(b)) / 2 or 1.0)


def flag_penalty(flag: str) -> tuple[str, float]:
    """Multiplier for one flag. Prefix/suffix matching so parameterised flags
    (`incomplete_distributions_2025-03-31..2025-06-30`) still resolve."""
    if flag in FLAG_PENALTIES:
        return flag, FLAG_PENALTIES[flag]
    for known, mult in FLAG_PENALTIES.items():
        if flag.startswith(known) or flag.endswith(known):
            return known, mult
    return flag, UNKNOWN_FLAG_PENALTY


def freshness_factor(as_of: date | None, reference: date) -> tuple[int | None, float]:
    if as_of is None:
        return None, FRESHNESS_STALE
    age = (reference - as_of).days
    for limit, factor in FRESHNESS_BANDS:
        if age <= limit:
            return age, factor
    return age, FRESHNESS_STALE


def independent(a: Candidate, b: Candidate) -> bool:
    """Two candidates corroborate each other only if they are not the same
    observation counted twice: different extraction mechanism, or different
    filing, or a materially different construction."""
    if a.tier != b.tier:
        return True
    if a.provenance.accession != b.provenance.accession:
        return True
    return a.transforms != b.transforms


def score_candidate(
    chosen: Candidate,
    corroborating: list[Candidate],
    reference_date: date,
) -> tuple[float, dict[str, Any]]:
    """Score one resolved value. Returns (score, audit trail of the inputs)."""
    tier = chosen.tier.base_score

    independents = [c for c in corroborating if independent(chosen, c)]
    agreeing = [c for c in independents if values_agree(chosen.value, c.value, chosen.unit)]
    disagreeing = [c for c in independents if c not in agreeing]

    if disagreeing:
        agreement, agreement_reason = AGREEMENT_CONFLICT, (
            f"{len(disagreeing)} independent source(s) disagree beyond tolerance"
        )
    elif agreeing:
        agreement, agreement_reason = AGREEMENT_CORROBORATED, (
            f"corroborated by {len(agreeing)} independent source(s)"
        )
    else:
        agreement, agreement_reason = AGREEMENT_SINGLE, "single source, uncorroborated"

    age_days, fresh = freshness_factor(chosen.as_of, reference_date)

    penalties: list[dict[str, Any]] = []
    penalty_product = 1.0
    for flag in chosen.flags:
        name, mult = flag_penalty(flag)
        penalty_product *= mult
        penalties.append({"flag": flag, "rule": name, "multiplier": mult})

    raw = tier * agreement * fresh * penalty_product
    score = max(0.0, min(1.0, raw))

    return score, {
        "tier": chosen.tier.value,
        "tier_score": tier,
        "agreement_factor": agreement,
        "agreement_reason": agreement_reason,
        "corroborating_sources": len(agreeing),
        "conflicting_sources": len(disagreeing),
        "as_of": chosen.as_of.isoformat() if chosen.as_of else None,
        "age_days": age_days,
        "freshness_factor": fresh,
        "penalties": penalties,
        "penalty_product": round(penalty_product, 4),
        "raw_score": round(raw, 4),
        "final_score": round(score, 4),
        "confidence": Confidence.from_score(score).value,
    }


def grade(score: float) -> Confidence:
    return Confidence.from_score(score)
