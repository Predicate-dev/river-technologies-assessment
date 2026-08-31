"""Core data model.

The central idea: an extracted number is never stored bare. It is a `Candidate`
-- a value plus the evidence for it. Multiple candidates for the same
(fund, metric, period) are reconciled into a `ResolvedMetric` in a separate,
logged step, so disagreement between sources is preserved rather than silently
collapsed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class SourceTier(str, Enum):
    """How the number was obtained, ordered by how much we trust the mechanism.

    This is about the *extraction mechanism*, not the filing's authority. A
    number typed into an XBRL tag by the filer's agent is machine-readable and
    unambiguous; the same number read out of a footnote by a model is not.
    """

    XBRL = "xbrl"  # Tagged financial data, exact, typed, dated.
    STRUCTURED_XML = "structured_xml"  # N-PORT XML fields. Exact, schema-defined.
    DERIVED = "derived"  # Computed from other candidates by an explicit formula.
    HTML_TABLE = "html_table"  # Deterministically parsed table cell.
    NARRATIVE_LLM = "narrative_llm"  # Model-extracted from prose/footnotes.

    @property
    def base_score(self) -> float:
        return _TIER_BASE[self]


_TIER_BASE = {
    SourceTier.XBRL: 0.95,
    SourceTier.STRUCTURED_XML: 0.92,
    SourceTier.DERIVED: 0.75,
    SourceTier.HTML_TABLE: 0.70,
    SourceTier.NARRATIVE_LLM: 0.55,
}


class Confidence(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    SUPPRESSED = "Suppressed"

    @classmethod
    def from_score(cls, score: float) -> "Confidence":
        if score >= 0.85:
            return cls.HIGH
        if score >= 0.65:
            return cls.MEDIUM
        if score >= 0.40:
            return cls.LOW
        return cls.SUPPRESSED


@dataclass(frozen=True)
class Provenance:
    """Where a number came from, precisely enough for a compliance reviewer.

    `locator` is the machine-addressable position within the document: an XBRL
    tag name, an XML XPath, a table caption plus cell coordinates, or a text
    offset. `excerpt` is the human-readable proof.
    """

    fund_ticker: str
    form_type: str
    accession: str
    filing_date: date | None
    period_end: date | None
    document_url: str
    locator: str
    excerpt: str = ""

    @property
    def citation(self) -> str:
        """One-line citation for a board deck footnote."""
        parts = [self.fund_ticker, self.form_type]
        if self.period_end:
            parts.append(f"period ended {self.period_end.isoformat()}")
        parts.append(f"acc. {self.accession}")
        parts.append(self.locator)
        return " | ".join(parts)


@dataclass
class Candidate:
    """One source's answer for one metric, with its evidence."""

    fund_ticker: str
    metric: str
    value: float
    unit: str
    tier: SourceTier
    provenance: Provenance
    # Basis qualifiers -- the reason two honest sources disagree.
    basis: dict[str, Any] = field(default_factory=dict)
    # Normalization steps applied, in order. Each one is a small risk.
    transforms: list[str] = field(default_factory=list)
    # Non-fatal problems found during extraction/normalization.
    flags: list[str] = field(default_factory=list)
    as_of: date | None = None

    def __post_init__(self) -> None:
        if self.as_of is None:
            self.as_of = self.provenance.period_end or self.provenance.filing_date

    @property
    def basis_key(self) -> str:
        """Candidates only meaningfully disagree if their basis matches."""
        return "|".join(f"{k}={self.basis[k]}" for k in sorted(self.basis))


@dataclass
class Conflict:
    """A material disagreement between candidates for the same value."""

    fund_ticker: str
    metric: str
    values: list[float]
    spread_pct: float
    resolution: str  # what we picked
    rationale: str  # why
    candidates: list[Candidate] = field(default_factory=list)


@dataclass
class ResolvedMetric:
    """The single number that reaches the board deck, plus its defence."""

    fund_ticker: str
    metric: str
    value: float | None
    unit: str
    confidence: Confidence
    score: float
    chosen: Candidate | None
    alternatives: list[Candidate] = field(default_factory=list)
    conflict: Conflict | None = None
    score_inputs: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def n_sources(self) -> int:
        return (1 if self.chosen else 0) + len(self.alternatives)

    @property
    def citation(self) -> str:
        return self.chosen.provenance.citation if self.chosen else ""
