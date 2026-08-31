"""Declarative metric registry.

The client's metric set changes quarter to quarter — weighted average spread one
quarter, default rates the next. Hard-coding each one means an engineering
request every quarter, which is the recurring cost this replaces.

A metric is therefore a *specification*, not code: a label, a unit, a direction,
a plausible range, and the places its value can be found. Adding one is a JSON
entry. The nine original metrics are declared the same way as any custom one, so
there is no second-class path — a custom metric gets the same provenance,
reconciliation and confidence treatment as a built-in.

What a spec deliberately does NOT do is invent an extraction strategy. If a
metric names no source this system can reach, it renders blank with that reason
rather than guessing, exactly like any other unavailable figure.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

log = logging.getLogger(__name__)

VALID_UNITS = {"pct", "usd", "ratio", "count", "years"}


@dataclass(frozen=True)
class MetricSpec:
    """One benchmark metric and where its value can be found."""

    key: str
    label: str
    unit: str = "pct"
    # +1 higher is better for investors, -1 lower is better, 0 no defensible
    # direction (a share price is not a quality; leverage is a posture).
    direction: int = 0
    sane_range: tuple[float, float] = (-1e9, 1e9)

    # A regex-free way to declare a prose metric, for definitions written by
    # someone who should not have to write a regex:
    #   {"near": ["non-accrual"], "take": "first_percent", "within": 400}
    # Compiled to a pattern at load time. `prose_patterns` remains available for
    # cases this cannot express -- two figures in one sentence, for instance.
    match: dict[str, Any] | None = None

    # Extraction hints. Empty means "this source cannot reach this metric".
    highlights_rows: tuple[str, ...] = ()  # regex, matched against a row label
    xbrl_tags: tuple[str, ...] = ()  # qualified tag names, instant facts
    prose_patterns: tuple[str, ...] = ()  # must capture the value in group(1)
    prose_anchors: tuple[str, ...] = ()  # phrases to locate prose windows

    # Restrict to certain filer types. Empty means all.
    entity_types: tuple[str, ...] = ()
    custom: bool = False
    note: str = ""

    def applies_to(self, entity_type: str) -> bool:
        return not self.entity_types or entity_type in self.entity_types


def _spec(**kw: Any) -> MetricSpec:
    return MetricSpec(**kw)


# The original nine, declared through the same mechanism as any custom metric so
# there is no privileged path. Extraction for these lives in the source adapters
# and predates the registry; the hints here describe the ones the generic
# extractors can also reach.
BUILTIN: tuple[MetricSpec, ...] = (
    _spec(key="net_return_1y_pct", label="Net return, trailing 1Y (ann.)",
          unit="pct", direction=1, sane_range=(-50.0, 50.0)),
    _spec(key="net_return_3y_pct", label="Net return, trailing 3Y (ann.)",
          unit="pct", direction=1, sane_range=(-50.0, 50.0)),
    _spec(key="net_return_5y_pct", label="Net return, trailing 5Y (ann.)",
          unit="pct", direction=1, sane_range=(-50.0, 50.0)),
    _spec(key="management_fee_pct", label="Management fee",
          unit="pct", direction=-1, sane_range=(0.0, 5.0)),
    _spec(key="incentive_fee_pct", label="Incentive fee",
          unit="pct", direction=-1, sane_range=(0.0, 30.0)),
    _spec(key="incentive_hurdle_pct", label="Incentive hurdle",
          unit="pct", direction=1, sane_range=(0.0, 15.0)),
    _spec(key="nav_per_share_usd", label="NAV per share",
          unit="usd", direction=0, sane_range=(0.5, 500.0)),
    _spec(key="leverage_regulatory_dte", label="Leverage (D/E), regulatory",
          unit="ratio", direction=0, sane_range=(0.0, 5.0)),
    _spec(key="leverage_economic_dte", label="Leverage (D/E), economic",
          unit="ratio", direction=0, sane_range=(0.0, 5.0)),
    _spec(key="distribution_yield_pct", label="Distribution yield (ann.)",
          unit="pct", direction=1, sane_range=(0.0, 30.0)),
)


# What `match.take` can ask for, and the regex each compiles to. Kept small on
# purpose: a vocabulary a non-engineer can hold in their head beats one that can
# express everything.
_TAKE = {
    "first_percent": r"([0-9]{1,3}(?:\.[0-9]{1,4})?)\s*%",
    "first_number": r"([0-9][0-9,]*(?:\.[0-9]+)?)",
    "first_basis_points": r"([0-9]{2,4})\s*basis points",
}


def compile_match(spec: dict[str, Any], key: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Turn a `match` block into (anchor phrases, regex patterns).

    The generated pattern requires the value to appear *after* the anchor phrase
    and within a bounded distance, so a metric cannot silently pick up a number
    from an unrelated sentence that happens to share a window.
    """
    near = spec.get("near")
    if not near:
        raise MetricDefinitionError(
            f"metric {key!r}: 'match' needs a 'near' list of phrases to look beside"
        )
    if isinstance(near, str):
        near = [near]
    take = spec.get("take", "first_percent")
    if take not in _TAKE:
        raise MetricDefinitionError(
            f"metric {key!r}: 'take' must be one of {sorted(_TAKE)}, got {take!r}"
        )
    within = int(spec.get("within", 300))
    if not 10 <= within <= 2000:
        raise MetricDefinitionError(
            f"metric {key!r}: 'within' must be between 10 and 2000 characters"
        )
    patterns = tuple(
        re.escape(phrase) + r"[^.]{0," + str(within) + r"}?" + _TAKE[take]
        for phrase in near
    )
    return tuple(near), patterns


class MetricDefinitionError(ValueError):
    """A user-supplied metric definition that cannot be trusted to render."""


def parse_spec(raw: dict[str, Any]) -> MetricSpec:
    """Validate one user-supplied definition.

    Strict on purpose. A malformed custom metric that silently half-works would
    put an unlabelled or wrongly-scaled number in a board deck, which is the
    failure this whole system is built to avoid — so a bad definition fails the
    run rather than degrading quietly.
    """
    missing = {"key", "label"} - set(raw)
    if missing:
        raise MetricDefinitionError(f"metric definition missing {sorted(missing)}: {raw}")
    unit = raw.get("unit", "pct")
    if unit not in VALID_UNITS:
        raise MetricDefinitionError(
            f"metric {raw['key']!r}: unit {unit!r} not one of {sorted(VALID_UNITS)}"
        )
    direction = raw.get("direction", 0)
    if direction not in (-1, 0, 1):
        raise MetricDefinitionError(
            f"metric {raw['key']!r}: direction must be -1, 0 or 1, got {direction!r}"
        )
    rng = raw.get("sane_range")
    if rng is not None:
        if not (isinstance(rng, (list, tuple)) and len(rng) == 2 and rng[0] < rng[1]):
            raise MetricDefinitionError(
                f"metric {raw['key']!r}: sane_range must be [low, high] with low < high"
            )
    anchors = tuple(raw.get("prose_anchors", ()))
    patterns = tuple(raw.get("prose_patterns", ()))
    if raw.get("match"):
        if patterns:
            raise MetricDefinitionError(
                f"metric {raw['key']!r}: give either 'match' or 'prose_patterns', "
                "not both -- two ways to find the same value is two ways to "
                "disagree about it"
            )
        anchors, patterns = compile_match(raw["match"], raw["key"])

    if not any(
        (raw.get("highlights_rows"), raw.get("xbrl_tags"), patterns)
    ):
        # Allowed, but say so: it will render blank everywhere.
        log.warning(
            "metric %r declares no extraction source; it will render blank for "
            "every fund with 'no EDGAR source located'",
            raw["key"],
        )
    return MetricSpec(
        key=raw["key"],
        label=raw["label"],
        unit=unit,
        direction=direction,
        sane_range=tuple(rng) if rng else (-1e9, 1e9),
        highlights_rows=tuple(raw.get("highlights_rows", ())),
        xbrl_tags=tuple(raw.get("xbrl_tags", ())),
        prose_patterns=patterns,
        prose_anchors=anchors,
        match=raw.get("match"),
        entity_types=tuple(raw.get("entity_types", ())),
        custom=True,
        note=raw.get("note", ""),
    )


def load_custom(path: str | Path | None) -> tuple[MetricSpec, ...]:
    """Load user-defined metrics from a JSON file. Missing file is not an error."""
    if path is None:
        return ()
    p = Path(path)
    if not p.exists():
        log.info("no custom metric file at %s", p)
        return ()
    raw = json.loads(p.read_text())
    if not isinstance(raw, list):
        raise MetricDefinitionError(f"{p}: expected a JSON list of metric definitions")
    return tuple(parse_spec(r) for r in raw)


class MetricRegistry:
    """The metric set for a run: the built-in nine plus any custom definitions."""

    def __init__(self, specs: Iterable[MetricSpec]) -> None:
        self._specs: dict[str, MetricSpec] = {}
        for s in specs:
            if s.key in self._specs:
                raise MetricDefinitionError(
                    f"duplicate metric key {s.key!r}; a custom metric may not "
                    "silently redefine another"
                )
            self._specs[s.key] = s

    def __iter__(self):
        return iter(self._specs.values())

    def __len__(self) -> int:
        return len(self._specs)

    def __contains__(self, key: object) -> bool:
        return key in self._specs

    def get(self, key: str) -> MetricSpec | None:
        return self._specs.get(key)

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(self._specs)

    @property
    def custom(self) -> tuple[MetricSpec, ...]:
        return tuple(s for s in self._specs.values() if s.custom)

    def labels(self) -> dict[str, str]:
        return {k: s.label for k, s in self._specs.items()}

    def units(self) -> dict[str, str]:
        return {k: s.unit for k, s in self._specs.items()}

    def ranges(self) -> dict[str, tuple[float, float]]:
        return {k: s.sane_range for k, s in self._specs.items()}

    def directions(self) -> dict[str, int]:
        return {k: s.direction for k, s in self._specs.items()}


def build_registry(custom_path: str | Path | None = None) -> MetricRegistry:
    return MetricRegistry(list(BUILTIN) + list(load_custom(custom_path)))


# The default registry, used when no custom file is supplied.
DEFAULT = build_registry()
