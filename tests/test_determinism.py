"""The board table must be byte-identical across runs on unchanged inputs.

This is a client-facing guarantee, not a nicety: the README promises reproducible
runs off the filing cache, and the whole engagement exists because a misread
basis reached a board. A basis label that moves between runs with no data change
is indistinguishable, in a diff, from a number that moved.

The bug this pins was real. `max(set(values), key=values.count)` chose the row's
reference basis; set iteration order over strings varies between processes, so a
two-way tie resolved differently each run and the annotation jumped between
TAKIX and GBDC on the trailing-return rows.
"""

import subprocess
import sys

from apexridge.render.cells import modal


def test_modal_breaks_ties_by_first_appearance():
    """A tie must resolve the same way every time, and predictably."""
    assert modal(["nav total return", "chain linked"]) == "nav total return"
    assert modal(["chain linked", "nav total return"]) == "chain linked"


def test_modal_prefers_the_most_common_over_the_first():
    assert modal(["a", "b", "b"]) == "b"


def test_modal_of_nothing_is_empty():
    assert modal([]) == ""


def test_modal_is_stable_under_hash_randomisation():
    """The actual defect: same input, different process, same answer.

    Run in subprocesses with different PYTHONHASHSEED values, because the bug is
    invisible within a single process -- one interpreter has one hash seed, so a
    set iterates consistently for the life of the run and only differs between
    runs. An in-process assertion would have passed against the broken code.
    """
    script = (
        "from apexridge.render.cells import modal;"
        # Eight distinct bases, all tied at one occurrence: the widest tie a
        # row can present, and the case a set is most likely to reorder.
        "print(modal([chr(97 + i) * 12 for i in range(8)]))"
    )
    answers = set()
    for seed in ("0", "1", "42", "12345", "99999"):
        out = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, check=True,
            env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"},
        )
        answers.add(out.stdout.strip())
    assert answers == {"a" * 12}, f"tie resolved differently across seeds: {answers}"
