"""Run-over-run coverage regression.

The operationally important signal is not what populated this quarter — it is
what populated last quarter and stopped. Prose patterns depend on filer wording,
and wording changes without notice. When it does, the failure is silent by
design: a missed match produces a blank with a reason, never a wrong number. That
is the right behaviour and it is exactly why nobody notices.

So a blank alone means nothing. A cell that carried a value last quarter and
carries a reason this quarter means something, and this is what watches for it.

Compares two coverage CSVs and classifies each change:

    LOST        had a value, now blank        -- investigate
    GAINED      was blank, now has a value    -- usually new coverage or a filing
    DEGRADED    still populated, confidence dropped a grade
    CHANGED     value moved by more than a tolerance
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ..config import METRIC_LABELS

# Why a cell that used to populate is blank now. The reason the pipeline already
# recorded is far better evidence than a generic guess -- and a hint that blames
# a filer wording change when the real cause was staleness or an open client
# decision trains the reader to ignore the report.
_LOST_CAUSE = {
    "stale_beyond_limit": "the figure aged past the staleness line; a cadence "
    "issue, not an extraction failure",
    "basis_disqualified": "withheld on an open basis question, not a data problem",
    "not_applicable": "reclassified as structurally unavailable for this filer",
    "class_attribution_failed": "the class-level figure could not be attributed",
    "window_mismatch": "available history no longer spans the labelled window",
    "insufficient_history": "history depth fell below what the window needs",
    "below_confidence_floor": "evidence weakened past the reporting floor; a "
    "corroborating source likely dropped out",
    "no_candidate": "nothing extracted at all -- the most likely cause is a "
    "filer wording change the extractor no longer matches",
}

LOST = "LOST"
GAINED = "GAINED"
DEGRADED = "DEGRADED"
CHANGED = "CHANGED"

_GRADE_ORDER = {"High": 3, "Medium": 2, "Low": 1, "": 0}

# A value moving more than this between runs is worth a look. Deliberately
# generous: quarterly figures genuinely move, and an alert that cries wolf is
# an alert nobody reads.
RELATIVE_TOLERANCE = 0.25


@dataclass
class Change:
    kind: str
    fund: str
    metric: str
    before: str
    after: str
    note: str = ""

    @property
    def label(self) -> str:
        return METRIC_LABELS.get(self.metric, self.metric)


def _index(frame: pd.DataFrame) -> dict[tuple[str, str], pd.Series]:
    return {(r["fund"], r["metric"]): r for _, r in frame.iterrows()}


def compare_runs(previous: pd.DataFrame, current: pd.DataFrame) -> list[Change]:
    prev, cur = _index(previous), _index(current)
    out: list[Change] = []

    for key in sorted(set(prev) | set(cur)):
        fund, metric = key
        p, c = prev.get(key), cur.get(key)
        if p is None or c is None:
            continue  # a fund or metric added or removed: not a regression

        p_filled = str(p["status"]) == "FILLED"
        c_filled = str(c["status"]) == "FILLED"

        if p_filled and not c_filled:
            out.append(
                Change(
                    LOST, fund, metric,
                    before=str(p["detail"]), after=str(c["status"]),
                    note=_LOST_CAUSE.get(
                        str(c["status"]),
                        "populated in the previous run and blank now",
                    ),
                )
            )
        elif c_filled and not p_filled:
            out.append(
                Change(
                    GAINED, fund, metric,
                    before=str(p["status"]), after=str(c["detail"]),
                )
            )
        elif p_filled and c_filled:
            pg = _GRADE_ORDER.get(str(p["confidence"]), 0)
            cg = _GRADE_ORDER.get(str(c["confidence"]), 0)
            if cg < pg:
                out.append(
                    Change(
                        DEGRADED, fund, metric,
                        before=str(p["confidence"]), after=str(c["confidence"]),
                        note="evidence weakened; a corroborating source may have dropped out",
                    )
                )
            pv, cv = _number(p["detail"]), _number(c["detail"])
            if pv is not None and cv is not None and pv != 0:
                move = abs(cv - pv) / abs(pv)
                if move > RELATIVE_TOLERANCE:
                    out.append(
                        Change(
                            CHANGED, fund, metric,
                            before=f"{pv:,.4g}", after=f"{cv:,.4g}",
                            note=f"moved {move * 100:.0f}% between runs",
                        )
                    )
    return out


def _number(detail: object) -> float | None:
    try:
        return float(str(detail).split()[0])
    except (ValueError, IndexError):
        return None


def regression_markdown(changes: list[Change], previous: str, current: str) -> str:
    lines = [
        "# Coverage regression report",
        "",
        f"Previous run: `{previous}` · current run: `{current}`",
        "",
    ]
    if not changes:
        lines.append("No changes in coverage, confidence or values between runs.")
        return "\n".join(lines)

    for kind, heading, blurb in (
        (LOST, "Lost coverage", "**Investigate these first.** Each carries the "
         "reason the pipeline recorded, which distinguishes an extraction that "
         "stopped matching from a figure that merely aged out or is held on an "
         "open question."),
        (DEGRADED, "Degraded confidence", "Still populated, but on weaker evidence."),
        (CHANGED, "Values moved materially", "Expected for quarterly figures; worth "
         "an eye on fee terms, which should rarely move."),
        (GAINED, "New coverage", "Usually a new filing or newly built extraction."),
    ):
        group = [c for c in changes if c.kind == kind]
        if not group:
            continue
        lines += [f"## {heading} ({len(group)})", "", blurb, ""]
        for c in group:
            note = f" — {c.note}" if c.note else ""
            lines.append(f"- **{c.fund} — {c.label}**: {c.before} → {c.after}{note}")
        lines.append("")
    return "\n".join(lines)


def run_regression(previous_csv: str | Path, current_csv: str | Path) -> tuple[list[Change], str]:
    prev = pd.read_csv(previous_csv)
    cur = pd.read_csv(current_csv)
    changes = compare_runs(prev, cur)
    return changes, regression_markdown(changes, str(previous_csv), str(current_csv))
