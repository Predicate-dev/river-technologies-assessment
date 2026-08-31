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
    TEXT_PATTERN = "text_pattern"  # Regex over an anchored prose window.
    NARRATIVE_LLM = "narrative_llm"  # Model-extracted from prose/footnotes.

    @property
    def base_score(self) -> float:
        return _TIER_BASE[self]


_TIER_BASE = {
    SourceTier.XBRL: 0.95,
    SourceTier.STRUCTURED_XML: 0.92,
    SourceTier.DERIVED: 0.75,
    SourceTier.HTML_TABLE: 0.72,
    SourceTier.TEXT_PATTERN: 0.66,
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


class ReasonCode(str, Enum):
    """Why a cell is empty, in the words a PM reads. A bare blank cannot render.

    Distinct from `SuppressionReason`, which is the diagnosis emitted upstream.
    This is the presentation layer, and it is near 1:1 with that enum -- a
    thinner abstraction than it looks. It is kept separate for two reasons: the
    wording here is client-facing and is quoted from Lara ("institutional figure
    not yet filed"), and two of these states never arise from a suppression at
    all. If the mapping ever stops being nearly 1:1, collapse this into a label
    table on SuppressionReason; see NOTES/decisions.md.

    Every label must be true of every case routed to it. The first draft failed
    this: SUPPRESSED read "sources disagree" and was catching GBDC's 5Y, where
    nothing disagreed. Telling a PM something false about a filing is the same
    class of error as a wrong number -- it produces a question Lara cannot
    answer.
    """

    NOT_APPLICABLE = "not_applicable"  # Filer does not publish this concept.
    NOT_YET_FILED = "not_yet_filed"  # Genuine cadence gap; carries a window.
    STALE = "stale"  # Figure exists but predates the six-month line.
    NO_VALUE_FOUND = "no_value_found"  # Applicable, nothing extracted.
    NOT_COMPUTABLE = "not_computable"  # History too short or wrong window.
    CLASS_UNATTRIBUTED = "class_unattributed"  # Series present, class unnamed.
    LOW_EVIDENCE = "low_evidence"  # Below the confidence floor.
    CONFLICTED = "conflicted"  # Independent sources genuinely disagree.
    BASIS_NOT_MEASURED = "basis_not_measured"  # Basis known, and it measures nothing.
    WRONG_SHARE_CLASS = "wrong_share_class"  # Fund-level found; institutional required.
    BASIS_UNCONFIRMED = "basis_unconfirmed"  # Basis unknown; comparison unsafe.

    @property
    def label(self) -> str:
        return _REASON_LABEL[self]


_REASON_LABEL = {
    ReasonCode.NOT_APPLICABLE: "not reported at this basis",
    ReasonCode.NOT_YET_FILED: "institutional figure not yet filed",
    ReasonCode.STALE: "no figure within staleness window",
    ReasonCode.NO_VALUE_FOUND: "no figure located in filings",
    ReasonCode.NOT_COMPUTABLE: "insufficient history to compute",
    ReasonCode.CLASS_UNATTRIBUTED: "share class not identifiable in filing",
    ReasonCode.LOW_EVIDENCE: "evidence too weak to report",
    ReasonCode.CONFLICTED: "sources disagree; not resolved",
    ReasonCode.BASIS_NOT_MEASURED: "reported basis does not measure this metric",
    ReasonCode.WRONG_SHARE_CLASS: "fund-level only; institutional figure not available",
    ReasonCode.BASIS_UNCONFIRMED: "basis unconfirmed",
}


class ShareClass(str, Enum):
    """Institutional is a hard client requirement for the interval funds.

    A blended fund-level number understates fee drag and flatters the
    competitor, and it would contradict deck footnote 3. UNCONFIRMED exists
    for Apex's own column, whose basis the client could not confirm.
    """

    INSTITUTIONAL = "institutional"
    FUND_LEVEL = "fund_level"
    NOT_APPLICABLE = "n/a"  # Single-class filers: GBDC, KREF.
    UNCONFIRMED = "unconfirmed"


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
    # For a contractual terms metric: the date through which no amendment to
    # this rate has been disclosed. Staleness is measured against this rather
    # than `as_of`, because a rate cannot change without a filing. None for
    # measured quantities, which genuinely do go stale with their period.
    terms_clock: date | None = None
    # When a filing states the period a contractual rate applies to. Kept OUT
    # of `basis` deliberately: a basis key partitions candidates into groups
    # that are never reconciled against each other, so putting a temporal
    # qualifier there would stop a superseded rate from ever being compared
    # with the rate that replaced it -- and a silently unreconciled pair is how
    # a wrong number ships.
    effective_from: date | None = None
    effective_until: date | None = None

    def __post_init__(self) -> None:
        if self.as_of is None:
            self.as_of = self.provenance.period_end or self.provenance.filing_date

    def in_force_at(self, when: date) -> bool | None:
        """Whether this rate applied at `when`. None if the filing does not say.

        None is not False: most filings state a rate without dating it, and
        treating undated as not-in-force would discard the common case.
        """
        if self.effective_from is None and self.effective_until is None:
            return None
        if self.effective_from is not None and when < self.effective_from:
            return False
        if self.effective_until is not None and when >= self.effective_until:
            return False
        return True

    @property
    def staleness_date(self) -> date | None:
        """The date staleness is measured from. See `terms_clock`."""
        return self.terms_clock or self.as_of

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
    # Present iff `value is None`. A blank cell is never bare: it states why.
    suppression: "Suppression | None" = None

    @property
    def citation(self) -> str:
        return self.chosen.provenance.citation if self.chosen else ""


@dataclass
class Cell:
    """The render unit. Never bare: a value carries its basis, a blank its reason.

    Constructed only via `filled` or `blank` so neither half can be forgotten.
    """

    fund_ticker: str
    metric: str
    value: float | None
    unit: str
    as_of: date | None
    basis: str  # Human-readable basis statement, shown at the cell.
    share_class: ShareClass
    confidence: Confidence | None = None
    reason: ReasonCode | None = None
    detail: str = ""  # Expected filing window, last-available date, etc.
    citation: str = ""
    divergent: bool = False  # Basis differs from the row's reference basis.

    def __post_init__(self) -> None:
        if self.value is None and self.reason is None:
            raise ValueError(f"blank cell without a reason: {self.fund_ticker}/{self.metric}")
        if self.value is not None and not self.basis:
            raise ValueError(f"value without a basis: {self.fund_ticker}/{self.metric}")

    @classmethod
    def filled(cls, resolved: "ResolvedMetric", *, basis: str, share_class: ShareClass,
               as_of: date | None, divergent: bool = False) -> "Cell":
        return cls(
            fund_ticker=resolved.fund_ticker,
            metric=resolved.metric,
            value=resolved.value,
            unit=resolved.unit,
            as_of=as_of,
            basis=basis,
            share_class=share_class,
            confidence=resolved.confidence,
            citation=resolved.citation,
            divergent=divergent,
        )

    @classmethod
    def blank(cls, fund_ticker: str, metric: str, reason: ReasonCode, *,
              detail: str = "", as_of: date | None = None,
              share_class: ShareClass = ShareClass.NOT_APPLICABLE) -> "Cell":
        return cls(
            fund_ticker=fund_ticker, metric=metric, value=None, unit="",
            as_of=as_of, basis="", share_class=share_class,
            reason=reason, detail=detail,
        )

    @property
    def is_blank(self) -> bool:
        return self.value is None

    def render(self) -> str:
        """Cell text for the board table. A divergent basis is marked inline."""
        if self.is_blank:
            note = f"{self.reason.label}" if self.reason else "no value"
            return f"— ({note}{'; ' + self.detail if self.detail else ''})"
        if self.unit == "pct":
            text = f"{self.value:.2f}%"
        elif self.unit == "usd":
            text = f"${self.value:,.2f}"
        else:
            text = f"{self.value:.2f}x"
        if self.as_of:
            text += f" @ {self.as_of.isoformat()}"
        if self.divergent:
            text += " ‡"
        return text


# --------------------------------------------------------------- SUPPRESSION


class SuppressionReason(str, Enum):
    """Why a cell is blank. Ordered loosely from structural to evidential.

    The reason is part of the deliverable, not diagnostics. The partner's rule:
    "A blank cell generates a question I can answer. A confident wrong number
    generates a question I cannot." That only holds if the blank arrives with
    its explanation attached.
    """

    NOT_APPLICABLE = "not_applicable"  # the filer does not publish this concept
    NO_CANDIDATE = "no_candidate"  # applicable, but nothing extracted
    INSUFFICIENT_HISTORY = "insufficient_history"  # too few observations
    WINDOW_MISMATCH = "window_mismatch"  # history exists, wrong length
    CLASS_ATTRIBUTION_FAILED = "class_attribution_failed"  # cannot name the class
    STALE_BEYOND_LIMIT = "stale_beyond_limit"  # older than the client's hard limit
    BELOW_CONFIDENCE_FLOOR = "below_confidence_floor"  # evidence too weak
    BASIS_DISQUALIFIED = "basis_disqualified"  # the elected construction measures nothing


@dataclass
class Suppression:
    """A blank cell, with its defence.

    `detail` is board-safe prose and renders in the cell. `internal_note` does
    not: it is for the appendix and the technical doc. The split exists because
    of an explicit client ruling -- the TAKIX class-return spread is a valid
    internal cross-check but must not reach a slide, because a range in a cell
    "generates a question I cannot answer cleanly".
    """

    fund_ticker: str
    metric: str
    reason: SuppressionReason
    detail: str
    as_of: date | None = None
    coverage_start: date | None = None
    coverage_end: date | None = None
    internal_note: str = ""

    @property
    def coverage_days(self) -> int | None:
        if not (self.coverage_start and self.coverage_end):
            return None
        return (self.coverage_end - self.coverage_start).days

    @property
    def coverage_label(self) -> str:
        """The period actually covered -- required on the cell by client ruling.

        A 4.75-year series must not be labelled 5Y, so where a partial window
        exists we state its real length and endpoints rather than rounding it
        to the label the row asked for.
        """
        days = self.coverage_days
        if days is None:
            return ""
        years = days / 365.25
        length = f"{years:.1f}y" if years >= 1.0 else f"{round(days / 30.44)}mo"
        return f"{length} available ({self.coverage_start} to {self.coverage_end})"

    @property
    def cell_label(self) -> str:
        """Exactly what renders in the blank cell. Never empty."""
        parts = [self.detail.rstrip(".")]
        if self.coverage_label:
            parts.append(self.coverage_label)
        if self.as_of and not self.coverage_end:
            parts.append(f"last available {self.as_of.isoformat()}")
        return "; ".join(parts) + "."


class SuppressionLog:
    """Collects suppression notices raised inside extractors.

    Extractors previously recorded a skip with `log.info(...)` and moved on, so
    the reason -- the part the client actually asked to see -- died in a log
    line and never reached reconciliation. They now write here instead.
    """

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], Suppression] = {}

    def __bool__(self) -> bool:
        """Always truthy.

        Without this, `__len__` makes an empty log falsy, and every extractor
        guarded by `if notices:` silently drops its notices on exactly the runs
        where the log is still empty -- i.e. the first and most important one.
        The guards say `is not None`, but the trap is one refactor away, so it
        is closed here as well.
        """
        return True

    def add(self, notice: Suppression) -> Suppression:
        """First notice for a (fund, metric) wins.

        Extractors run cheapest-first, so the earliest notice is the most
        specific diagnosis; a later one is usually a downstream restatement of
        the same absence.
        """
        key = (notice.fund_ticker, notice.metric)
        self._by_key.setdefault(key, notice)
        return notice

    def get(self, fund_ticker: str, metric: str) -> Suppression | None:
        return self._by_key.get((fund_ticker, metric))

    def all(self) -> list[Suppression]:
        return list(self._by_key.values())

    def __len__(self) -> int:
        return len(self._by_key)
