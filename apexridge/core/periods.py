"""Reconstructing a clean, non-overlapping distribution ledger.

Filers tag per-share distributions inconsistently: some periods appear as
standalone quarters, some only inside a fiscal-year-to-date cumulative, and a
10-K reports the full year without ever tagging its fourth quarter separately.
Naively summing every tagged fact double-counts; naively taking only the
90-day facts silently drops a quarter and understates a year of return.

This module reconstructs one non-overlapping interval per period by:
  1. accepting the shortest, most specific intervals first, then
  2. differencing longer cumulative intervals against what is already covered
     to recover the single uncovered gap.

Pure date/number logic with no I/O, so it is directly testable -- and it is the
main place a silent arithmetic error could reach the board deck.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable

DAY = timedelta(days=1)


@dataclass(frozen=True)
class Period:
    """An amount attributed to a half-open-ish inclusive date range."""

    start: date
    end: date
    value: float
    source: str = "tagged"  # "tagged" | "derived_by_difference"
    origin: str = ""  # accession or tag that produced it

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def overlaps(self, other: "Period") -> bool:
        return self.start <= other.end and other.start <= self.end

    def contains(self, other: "Period") -> bool:
        return self.start <= other.start and other.end <= self.end


def _gaps(outer: Period, covered: list[Period]) -> list[tuple[date, date]]:
    """Uncovered sub-ranges of `outer` given sorted, non-overlapping `covered`."""
    out: list[tuple[date, date]] = []
    cursor = outer.start
    for c in sorted(covered, key=lambda p: p.start):
        if c.start > cursor:
            out.append((cursor, c.start - DAY))
        cursor = max(cursor, c.end + DAY)
    if cursor <= outer.end:
        out.append((cursor, outer.end))
    return out


def build_ledger(
    facts: Iterable[tuple[date, date, float, str]],
    *,
    max_passes: int = 6,
    tolerance: float = 1e-9,
) -> list[Period]:
    """Non-overlapping periods covering as much of the timeline as possible.

    `facts` are (start, end, value, origin) tuples. Returns periods sorted by
    start date. Intervals that cannot be disambiguated are dropped rather than
    guessed at.
    """
    raw: dict[tuple[date, date], Period] = {}
    for start, end, value, origin in facts:
        if start is None or end is None or end < start:
            continue
        key = (start, end)
        # Identical periods reported twice (original vs. comparative) -- keep one.
        if key not in raw:
            raw[key] = Period(start, end, value, "tagged", origin)

    candidates = sorted(raw.values(), key=lambda p: (p.days, p.start))
    accepted: list[Period] = []
    for p in candidates:
        if not any(p.overlaps(a) for a in accepted):
            accepted.append(p)

    # Difference the longer cumulative facts against what is already covered.
    for _ in range(max_passes):
        changed = False
        for p in candidates:
            if any(p.overlaps(a) and not a.days < p.days for a in accepted):
                pass
            inside = [a for a in accepted if p.contains(a)]
            if not inside:
                continue
            covered_days = sum(a.days for a in inside)
            if covered_days >= p.days:
                continue  # fully covered, nothing to learn
            holes = _gaps(p, inside)
            if len(holes) != 1:
                continue  # ambiguous: cannot attribute a residual to one period
            hole = holes[0]
            # The hole must not overlap anything already accepted elsewhere.
            probe = Period(hole[0], hole[1], 0.0)
            if any(probe.overlaps(a) for a in accepted):
                continue
            residual = p.value - sum(a.value for a in inside)
            if abs(residual) < tolerance:
                residual = 0.0
            accepted.append(
                Period(
                    hole[0],
                    hole[1],
                    residual,
                    "derived_by_difference",
                    f"{p.origin} minus {len(inside)} tagged sub-periods",
                )
            )
            changed = True
        if not changed:
            break

    return sorted(accepted, key=lambda p: p.start)


def sum_between(ledger: list[Period], start: date, end: date) -> tuple[float, list[Period], bool]:
    """Total value of periods fully inside [start, end].

    Returns (total, periods_used, complete) where `complete` is False if the
    used periods leave a gap of more than a few days -- the caller must then
    flag the derived figure rather than presenting it as exact.
    """
    used = [p for p in ledger if p.start >= start and p.end <= end]
    total = sum(p.value for p in used)
    if not used:
        return 0.0, [], False
    span_days = (end - start).days + 1
    covered = sum(p.days for p in used)
    complete = covered >= span_days - 7  # allow week-scale boundary slack
    return total, used, complete
