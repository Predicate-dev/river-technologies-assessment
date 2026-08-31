"""Tests for run-over-run regression detection.

This exists because the pipeline's failure mode is silent by design: a filer
changes wording, the extractor stops matching, and the cell blanks with a
reason. That is correct behaviour and it is exactly why nobody notices. The
regression report is the only thing that turns a quiet blank into a signal, so
it has to distinguish the causes rather than blame wording for everything.
"""

import pandas as pd

from apexridge.render.regression import (
    CHANGED,
    DEGRADED,
    GAINED,
    LOST,
    compare_runs,
    regression_markdown,
)


def frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "fund": r.get("fund", "GBDC"),
                "metric": r.get("metric", "management_fee_pct"),
                "status": r.get("status", "FILLED"),
                "owner": "-",
                "detail": r.get("detail", "1 pct"),
                "confidence": r.get("confidence", "Medium"),
            }
            for r in rows
        ]
    )


def test_a_cell_that_stops_populating_is_flagged_lost():
    prev = frame([{"detail": "1 pct"}])
    cur = frame([{"status": "no_candidate", "detail": "not found", "confidence": ""}])
    changes = compare_runs(prev, cur)
    assert [c.kind for c in changes] == [LOST]
    assert "wording change" in changes[0].note


def test_lost_cause_reflects_the_recorded_reason_not_a_generic_guess():
    """A figure that aged out is not an extraction failure, and saying so
    wrongly every quarter trains the reader to ignore the report."""
    prev = frame([{"detail": "8.91 pct"}])
    cur = frame([{"status": "stale_beyond_limit", "detail": "", "confidence": ""}])
    note = compare_runs(prev, cur)[0].note
    assert "aged past the staleness line" in note
    assert "wording" not in note


def test_confidence_dropping_a_grade_is_flagged():
    prev = frame([{"confidence": "High"}])
    cur = frame([{"confidence": "Medium"}])
    assert [c.kind for c in compare_runs(prev, cur)] == [DEGRADED]


def test_confidence_improving_is_not_flagged():
    prev = frame([{"confidence": "Low"}])
    cur = frame([{"confidence": "High"}])
    assert compare_runs(prev, cur) == []


def test_a_material_value_move_is_flagged():
    prev = frame([{"detail": "1 pct"}])
    cur = frame([{"detail": "1.5 pct"}])
    kinds = [c.kind for c in compare_runs(prev, cur)]
    assert CHANGED in kinds


def test_a_small_move_is_not_flagged():
    """Quarterly figures move. An alert that cries wolf is one nobody reads."""
    prev = frame([{"detail": "10 pct"}])
    cur = frame([{"detail": "10.5 pct"}])
    assert compare_runs(prev, cur) == []


def test_newly_populated_cells_are_reported_as_gained_not_lost():
    prev = frame([{"status": "no_candidate", "detail": "", "confidence": ""}])
    cur = frame([{"detail": "1 pct"}])
    assert [c.kind for c in compare_runs(prev, cur)] == [GAINED]


def test_a_metric_absent_from_one_run_is_not_a_regression():
    """Adding a fund or a metric must not read as coverage loss."""
    prev = frame([{"fund": "GBDC"}])
    cur = frame([{"fund": "GBDC"}, {"fund": "KREF"}])
    assert compare_runs(prev, cur) == []


def test_no_changes_reads_cleanly():
    prev = cur = frame([{"detail": "1 pct"}])
    report = regression_markdown(compare_runs(prev, cur), "a.csv", "b.csv")
    assert "No changes in coverage" in report
