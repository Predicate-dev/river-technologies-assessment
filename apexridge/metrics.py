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
    _spec(key="leverage_ratio_dte", label="Leverage (D/E)",
          unit="ratio", direction=0, sane_range=(0.0, 5.0)),
    _spec(key="distribution_yield_pct", label="Distribution yield (ann.)",
          unit="pct", direction=1, sane_range=(0.0, 30.0)),
)


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
    if not any(
        raw.get(k) for k in ("highlights_rows", "xbrl_tags", "prose_patterns")
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
        prose_patterns=tuple(raw.get("prose_patterns", ())),
        prose_anchors=tuple(raw.get("prose_anchors", ())),
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
