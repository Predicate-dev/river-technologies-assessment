"""Narrative extraction from filing HTML.

This is where the metrics live that no structured source carries: fee rates,
hurdles, and the interval funds' stated trailing returns. The client's brief
calls this out -- "structured tables, narrative text, footnotes, and exhibits"
-- and it is genuinely the hard part. CCLFX states its management fee in a
sentence in the middle of a 2.9 MB prospectus; TAKIX states its hurdle as
"1.50% per quarter, or an annualized hurdle rate of 6.00%".

Three extraction mechanisms, in descending trust:

  1. **Fee/performance tables** -- located by anchor phrase, parsed structurally.
     A table row is an unambiguous label/value pair.
  2. **Anchored prose patterns** -- regex over a bounded window around an anchor
     phrase. Deterministic and reviewable, but brittle to wording.
  3. **LLM extraction** (optional) -- for windows the first two miss. Every LLM
     answer must come back with a verbatim supporting quote, and the quote is
     checked to be literally present in the source document. An answer whose
     quote cannot be found is discarded, not downgraded. This is the guard that
     keeps a fluent-sounding hallucination out of a board deck.

Documents are large (one CCLFX N-CSR is 67 MB), so we never parse a whole file:
anchors are found in the raw HTML with a tag-tolerant pattern, and only a
bounded window around each hit is handed to the HTML parser.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Iterable

from bs4 import BeautifulSoup

from ..config import (
    AMENDABLE_FORMS,
    TERMS_METRICS,
    M_DIST_YIELD,
    M_HURDLE,
    M_INCENTIVE_FEE,
    M_MGMT_FEE,
    M_NAV_PS,
    M_RETURN_1Y,
    M_RETURN_3Y,
    M_RETURN_5Y,
    Fund,
)
from ..core.confidence import STALE_LIMIT_DAYS
from ..core.models import Candidate, Provenance, SourceTier
from ..edgar import EdgarClient, Filing

log = logging.getLogger(__name__)

# Filler allowed between words of an anchor phrase: HTML tags, entities, space.
# Filing HTML routinely splits a phrase across <font> and <span> boundaries, so
# a plain substring search misses most real anchors.
_FILLER = r"(?:<[^>]*>|&nbsp;|&#160;|&#8217;|\s)*"
_PCT = r"([0-9]{1,3}(?:\.[0-9]{1,4})?)\s*%"


def tag_tolerant(phrase: str) -> re.Pattern[str]:
    return re.compile(_FILLER.join(re.escape(w) for w in phrase.split()), re.I)


def anchors(html: str, phrases: Iterable[str], limit_per_phrase: int = 12) -> list[int]:
    out: list[int] = []
    for p in phrases:
        for i, m in enumerate(tag_tolerant(p).finditer(html)):
            if i >= limit_per_phrase:
                break
            out.append(m.start())
    return sorted(set(out))


def window_text(html: str, pos: int, before: int = 1200, after: int = 2500) -> str:
    chunk = html[max(0, pos - before) : pos + after]
    text = BeautifulSoup(chunk, "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text)


def table_after(html: str, pos: int, max_scan: int = 40000) -> list[list[str]] | None:
    """Rows of the first <table> starting at or after `pos`."""
    j = html.find("<table", pos)
    if j < 0 or j - pos > max_scan:
        return None
    k = html.find("</table>", j)
    if k < 0:
        return None
    soup = BeautifulSoup(html[j : k + 8], "html.parser")
    rows: list[list[str]] = []
    for tr in soup.find_all("tr"):
        cells = [re.sub(r"\s+", " ", td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        if cells:
            rows.append(cells)
    return rows or None


def _pct_in(cell: str) -> float | None:
    m = re.search(_PCT, cell)
    return float(m.group(1)) if m else None


@dataclass
class Doc:
    """A filing document held as raw HTML, with provenance metadata."""

    fund: Fund
    filing: Filing
    html: str

    def provenance(self, locator: str, excerpt: str) -> Provenance:
        return Provenance(
            fund_ticker=self.fund.ticker,
            form_type=self.filing.form,
            accession=self.filing.accession,
            filing_date=self.filing.filing_date,
            period_end=self.filing.report_date or self.filing.filing_date,
            document_url=self.filing.primary_url,
            locator=locator,
            excerpt=excerpt[:400],
        )

    def candidate(
        self,
        metric: str,
        value: float,
        *,
        unit: str,
        tier: SourceTier,
        locator: str,
        excerpt: str,
        basis: dict[str, Any] | None = None,
        transforms: list[str] | None = None,
        flags: list[str] | None = None,
    ) -> Candidate:
        return Candidate(
            fund_ticker=self.fund.ticker,
            metric=metric,
            value=value,
            unit=unit,
            tier=tier,
            provenance=self.provenance(locator, excerpt),
            basis=basis or {},
            transforms=transforms or [],
            flags=flags or [],
        )


# ------------------------------------------------------------------ tables

FEE_TABLE_ANCHORS = (
    "Annual Expenses",
    "Annual Fund Operating Expenses",
    "Fees and Expenses",
    "Shareholder Fees",
    "Summary of Fund Expenses",
)

# Row label -> (metric, note). Matched case-insensitively as a prefix.
FEE_ROW_LABELS: list[tuple[str, str]] = [
    (r"management fee", M_MGMT_FEE),
    (r"investment management fee", M_MGMT_FEE),
    (r"advisory fee", M_MGMT_FEE),
    (r"incentive fee", M_INCENTIVE_FEE),
]


def fee_tables(doc: Doc) -> list[Candidate]:
    """Fee rates from an expense table.

    Anchors are noisy -- "Annual Expenses" matches the table of contents as
    often as the fee table -- so a table is only accepted if it actually
    contains a recognised fee row with a percentage in it.
    """
    out: list[Candidate] = []
    seen: set[tuple[str, float]] = set()
    for pos in anchors(doc.html, FEE_TABLE_ANCHORS):
        rows = table_after(doc.html, pos)
        if not rows:
            continue
        header = rows[0][0] if rows and rows[0] else ""
        for row in rows:
            if len(row) < 2:
                continue
            label = row[0].lower()
            for pattern, metric in FEE_ROW_LABELS:
                if not re.match(pattern, label):
                    continue
                pct = _pct_in(row[1])
                if pct is None:
                    continue
                key = (metric, pct)
                if key in seen:
                    continue
                seen.add(key)
                # Expense tables are stated as a percentage of net assets;
                # a fee quoted on gross assets is a different number and the
                # header is the only place that distinction appears.
                denom = "net_assets" if "net asset" in header.lower() else "unstated"
                out.append(
                    doc.candidate(
                        metric,
                        pct,
                        unit="pct",
                        tier=SourceTier.HTML_TABLE,
                        locator=f"expense table @ char {pos}, row {row[0]!r}",
                        excerpt=f"{header} | {' | '.join(row[:3])}",
                        basis={"fee_basis": f"pct_of_{denom}"},
                        flags=[] if denom != "unstated" else ["fee_denominator_unstated"],
                    )
                )
                break
    return out


RETURN_TABLE_ANCHORS = (
    "Average Annual Total Return",
    "Average Annual Total Returns",
)
_PERIOD_COLUMNS = {
    M_RETURN_1Y: (r"1\s*year", r"one\s*year"),
    M_RETURN_3Y: (r"3\s*year", r"three\s*year"),
    M_RETURN_5Y: (r"5\s*year", r"five\s*year"),
}


def return_tables(doc: Doc) -> list[Candidate]:
    """Stated trailing returns from an "Average Annual Total Returns" table.

    This is the fund's own published figure -- the number the analyst used to
    transcribe by hand -- so where it exists it is the authoritative answer for
    a stated trailing return, and a strong check on anything we derived.
    """
    out: list[Candidate] = []
    for pos in anchors(doc.html, RETURN_TABLE_ANCHORS):
        rows = table_after(doc.html, pos)
        if not rows or len(rows) < 2:
            continue
        header = rows[0]
        col_for: dict[int, str] = {}
        for i, cell in enumerate(header):
            for metric, pats in _PERIOD_COLUMNS.items():
                if any(re.search(p, cell, re.I) for p in pats):
                    col_for[i] = metric
        if not col_for:
            continue
        for row in rows[1:]:
            label = row[0]
            for i, metric in col_for.items():
                if i >= len(row):
                    continue
                pct = _pct_in(row[i])
                if pct is None:
                    continue
                out.append(
                    doc.candidate(
                        metric,
                        pct,
                        unit="pct",
                        tier=SourceTier.HTML_TABLE,
                        locator=f"average annual total return table @ char {pos}, row {label!r}",
                        excerpt=f"{' | '.join(header[:6])} || {' | '.join(row[:6])}",
                        basis={
                            "return_basis": "stated_average_annual_total_return",
                            "share_class": label[:60],
                            "net_of_fees": True,
                        },
                    )
                )
    return out


# ------------------------------------------------------------------- prose

# (metric, anchor phrases, compiled patterns, basis, note)
PROSE_RULES: list[tuple[str, tuple[str, ...], list[str], dict[str, Any]]] = [
    (
        M_MGMT_FEE,
        ("management fee", "investment management fee"),
        [
            # Authoritative present-tense statements first.
            r"management fee is calculated at an annual rate (?:of|equal to)\s*" + _PCT,
            r"management fee[^.]{0,160}?at an annual rate of\s*" + _PCT,
            r"annual rate of\s*" + _PCT + r"[^.]{0,80}?(?:of|based upon)[^.]{0,60}?net assets",
            r"management fee[^.]{0,120}?equal to\s*" + _PCT + r"[^.]{0,60}?per annum",
        ],
        {"fee_basis": "stated_annual_rate"},
    ),
    (
        M_HURDLE,
        ("hurdle rate", "hurdle", "weighted average adjusted equity"),
        [
            r"annualized hurdle rate of\s*" + _PCT,
            r"hurdle rate[^.]{0,100}?equal to\s*" + _PCT + r"[^.]{0,40}?per\s*annum",
            r"hurdle rate[^.]{0,80}?of\s*" + _PCT,
            # REIT form: the hurdle is stated before it is named.
            _PCT + r"\s*of the trailing 12-month weighted average adjusted equity",
        ],
        {"hurdle_basis": "annualized"},
    ),
    (
        M_INCENTIVE_FEE,
        ("incentive fee", "incentive compensation", "carried interest"),
        [
            # BDC form: "...equal to 15.0% of our Cumulative Pre-Incentive Fee
            # Net Income". REIT form: "incentive compensation equal to 20.0% of
            # the excess of...". The prefix window is generous because the fee
            # is often named a clause or two before the rate.
            r"incentive (?:fee|compensation)[^.]{0,200}?equal to\s*" + _PCT
            + r"\s*of\s+(?:the|our|its)?\s*(?:excess|cumulative)",
            r"incentive fee[^.]{0,120}?equal to\s*" + _PCT
            + r"\s*(?:of|on)\s+(?:the\s+)?(?:fund's\s+)?(?:pre-incentive|net|"
            r"ordinary|investment|realized|capital|income|profits)",
            r"carried interest[^.]{0,80}?of\s*" + _PCT + r"\s*(?:of|on)\s",
        ],
        {"fee_basis": "stated_rate"},
    ),
]

# A hurdle quoted per quarter is not an annual hurdle. The board deck compares
# against Apex Ridge's 6.00% annual hurdle, so a 1.50%-per-quarter disclosure
# must be annualized -- and labelled as converted -- rather than reported raw.
_PERIOD_QUALIFIER = re.compile(
    r"\b(per\s+quarter|quarterly|calendar\s+quarter|per\s+annum|annualized|"
    r"per\s+year|annual|trailing\s+12-month)\b",
    re.I,
)
_QUARTERLY = {"per quarter", "quarterly", "calendar quarter"}


def _hurdle_basis(
    window: str, match_start: int, match_end: int
) -> tuple[float, dict[str, Any], list[str], str]:
    """Return (multiplier, basis, transforms, note) for a hurdle match.

    The period qualifier can sit on either side of the number -- "equal to 1.50%
    per quarter" but also "in respect of the relevant calendar quarter, to a
    hurdle rate of 1.50%" -- so both sides are searched, nearest first.
    """
    # Nearest qualifier wins, and the words immediately BEFORE the number are
    # nearest of all: in "equal to 1.50% per quarter, or an annualized hurdle
    # rate of 6.00%", the 6.00% is already annual even though "per quarter"
    # appears earlier in the same sentence. Searching the wider context first
    # would double-count it to 24%.
    near_head = window[max(0, match_start - 60) : match_start]
    tail = window[match_end : match_end + 60]
    wide_head = window[max(0, match_start - 160) : max(0, match_start - 60)]

    qualifier = ""
    for scope, take_last in ((near_head, True), (tail, False), (wide_head, True)):
        found = list(_PERIOD_QUALIFIER.finditer(scope))
        if found:
            qualifier = (found[-1] if take_last else found[0]).group(1).lower()
            break
    qualifier = re.sub(r"\s+", " ", qualifier)
    if qualifier in _QUARTERLY:
        return (
            4.0,
            {"hurdle_basis": "annualized"},
            ["stated quarterly; x4 to annualize"],
            "converted from a quarterly rate",
        )
    return 1.0, {"hurdle_basis": "annualized"}, [f"stated as {qualifier or 'unqualified'}"], ""


# A 10-K mentions "incentive fee" fifty times; the first dozen hits are the
# table of contents and risk factors, and the agreement itself sits past them.
# Scanning too few anchors silently loses the metric.
PROSE_ANCHOR_LIMIT = 40

# Filings restate their own history in the present document. TAKIX's prospectus
# says "Prior to April 1, 2020, the Management Fee was ... at the annual rate of
# 1.50%" a few paragraphs from the current 1.00%; GBDC's 10-K uses the "reduced
# from X to Y" form handled separately. Both are correct statements of a rate
# that is no longer in force, and both are exactly the misread that reached the
# client's board. A match carrying one of these markers is flagged as a
# superseded rate, which makes it a non-measurement in the confidence model: it
# is kept as evidence and shown in the conflict log, but it can neither
# corroborate nor outvote the rate actually in force.
_HISTORICAL_MARKER = re.compile(
    r"\b(prior to|previously|formerly|until\s+\w+\s+\d{1,2},\s*\d{4}|"
    r"through\s+\w+\s+\d{1,2},\s*\d{4}|"
    r"(?:fee|rate)\s+was\s+(?:calculated|payable|equal))\b",
    re.I,
)


def _is_historical(window: str, match_start: int) -> str | None:
    """The historical marker governing a match, if the clause carries one.

    Scoped to the text between the previous sentence boundary and the match, so
    a marker in an unrelated neighbouring sentence does not condemn a current
    rate standing beside it.
    """
    head = window[max(0, match_start - 320) : match_start]
    boundary = max(head.rfind(". "), head.rfind("; "))
    clause = head[boundary + 1 :] if boundary != -1 else head
    m = _HISTORICAL_MARKER.search(clause)
    return m.group(1) if m else None


def prose_patterns(doc: Doc) -> list[Candidate]:
    """Deterministic regex extraction over bounded windows around anchors."""
    out: list[Candidate] = []
    seen: set[tuple[str, float]] = set()
    for metric, phrases, patterns, basis in PROSE_RULES:
        for pos in anchors(doc.html, phrases, limit_per_phrase=PROSE_ANCHOR_LIMIT):
            text = window_text(doc.html, pos)
            for pat in patterns:
                m = re.search(pat, text, re.I)
                if not m:
                    continue
                value = float(m.group(1))
                use_basis = dict(basis)
                transforms: list[str] = []
                flags: list[str] = []
                note = ""
                if metric == M_HURDLE:
                    # Context is measured around the captured number, not the
                    # whole match: "annualized hurdle rate of 6.00%" starts
                    # after "1.50% per quarter, or an", and anchoring on the
                    # match start would pick up that quarterly qualifier and
                    # quadruple an already-annual figure.
                    mult, use_basis, transforms, note = _hurdle_basis(
                        text, m.start(1), m.end(1)
                    )
                    value *= mult
                historical = _is_historical(text, m.start())
                if historical:
                    flags.append("superseded_rate")
                if metric == M_INCENTIVE_FEE and not 5.0 <= value <= 25.0:
                    # Outside the range every externally-managed credit fund
                    # actually charges. Almost always a pattern that latched
                    # onto a hurdle or a catch-up rate instead of the fee.
                    flags.append("implausible_incentive_fee_rate")
                if (metric, value) in seen:
                    continue
                seen.add((metric, value))
                start = max(0, m.start() - 90)
                out.append(
                    doc.candidate(
                        metric,
                        value,
                        unit="pct",
                        tier=SourceTier.TEXT_PATTERN,
                        locator=f"prose pattern @ char {pos}"
                        + (f" [{note}]" if note else "")
                        + (f" [superseded: '{historical}']" if historical else ""),
                        excerpt=text[start : m.end() + 90],
                        basis=use_basis,
                        transforms=transforms,
                        flags=flags,
                    )
                )
                break
    return out


# ---------------------------------------------------------- superseded rates

# "the base management fee rate was reduced from 1.375% to 1.0%" states the old
# and the current rate in one sentence. Both are real values from the filing and
# reading the wrong one is exactly the misread that put a wrong basis point in
# the client's board deck, so we do NOT quietly pick one inside the extractor.
# Both are emitted as candidates on the same basis; reconciliation resolves them
# and logs the conflict, so the appendix can show a PM why 1.0% beat 1.375%
# rather than a flag noting that an ambiguity existed somewhere.
SUPERSEDED_RULES: list[tuple[str, tuple[str, ...], str, dict[str, Any]]] = [
    (
        M_MGMT_FEE,
        ("management fee", "base management fee"),
        r"management fee rate (?:was|were) reduced from\s*" + _PCT + r"\s*to\s*" + _PCT,
        # Must match the basis the plain prose rule emits for this metric,
        # otherwise the superseded rate lands in a separate basis group and is
        # reported as a legitimate alternative rather than losing a conflict.
        {"fee_basis": "stated_annual_rate"},
    ),
    (
        M_INCENTIVE_FEE,
        ("incentive fee",),
        r"incentive fee (?:rates?|cap)? ?(?:were|was) reduced from\s*"
        + _PCT + r"\s*to\s*" + _PCT,
        {"fee_basis": "stated_rate"},
    ),
]


def superseded_rates(doc: Doc) -> list[Candidate]:
    """Emit both sides of a "reduced from X% to Y%" disclosure as candidates."""
    out: list[Candidate] = []
    seen: set[tuple[str, float]] = set()
    for metric, phrases, pattern, basis in SUPERSEDED_RULES:
        for pos in anchors(doc.html, phrases, limit_per_phrase=PROSE_ANCHOR_LIMIT):
            text = window_text(doc.html, pos)
            m = re.search(pattern, text, re.I)
            if not m:
                continue
            old_rate, current_rate = float(m.group(1)), float(m.group(2))
            excerpt = text[max(0, m.start() - 90) : m.end() + 90]
            for value, is_current in ((current_rate, True), (old_rate, False)):
                if (metric, value) in seen:
                    continue
                seen.add((metric, value))
                out.append(
                    doc.candidate(
                        metric,
                        value,
                        unit="pct",
                        tier=SourceTier.TEXT_PATTERN,
                        locator=f"superseded-rate disclosure @ char {pos} "
                        f"({'current' if is_current else 'superseded'} rate)",
                        excerpt=excerpt,
                        basis=dict(basis),
                        transforms=[
                            f"read as the {'current' if is_current else 'superseded'} "
                            f"rate in \"reduced from {old_rate}% to {current_rate}%\""
                        ],
                        # The superseded rate must lose reconciliation on
                        # evidence, not on ordering: the flag is what makes it
                        # lose the fewest-flags tiebreak against the current one.
                        flags=[] if is_current else ["superseded_rate"],
                    )
                )
    return out


# --------------------------------------------------------------------- LLM


def llm_extract(
    doc: Doc,
    metrics: Iterable[str],
    *,
    client: Any = None,
    model: str = "claude-sonnet-5",
    passes: int = 2,
) -> list[Candidate]:
    """Optional LLM tier, with verbatim-quote verification.

    The model is asked for a value *and* the exact sentence supporting it. We
    then check that sentence appears literally in the source window. An answer
    whose quote is not found in the document is discarded outright -- it is the
    signature of a fabricated number, and no confidence discount is an adequate
    substitute for dropping it.

    Two independent passes are run; disagreement between them flags the value
    rather than silently taking one. Returns [] when no API key is configured,
    which is why the pipeline runs end-to-end without one.
    """
    try:
        import anthropic  # noqa: PLC0415
    except ImportError:
        log.info("anthropic SDK not installed; skipping LLM tier")
        return []
    if client is None:
        try:
            client = anthropic.Anthropic()
        except Exception:
            log.info("no Anthropic API key configured; skipping LLM tier")
            return []

    wanted = [m for m in metrics]
    if not wanted:
        return []

    windows: list[tuple[int, str]] = []
    for metric, phrases, _pats, _basis in PROSE_RULES:
        if metric not in wanted:
            continue
        for pos in anchors(doc.html, phrases)[:4]:
            windows.append((pos, window_text(doc.html, pos, before=1500, after=3000)))
    if not windows:
        return []

    schema_hint = (
        '{"findings": [{"metric": "management_fee_pct|incentive_fee_pct|'
        'incentive_hurdle_pct", "value_pct": 1.25, "quote": "<exact sentence '
        'copied verbatim from the excerpt>"}]}'
    )

    results: list[list[dict[str, Any]]] = []
    for attempt in range(passes):
        findings: list[dict[str, Any]] = []
        for pos, text in windows[:8]:
            prompt = (
                "You are extracting fee terms from an SEC filing excerpt for a "
                f"fund called {doc.fund.name}.\n\n"
                "Return ONLY JSON matching this shape:\n"
                f"{schema_hint}\n\n"
                "Rules: report a metric only if the excerpt states it explicitly. "
                "The 'quote' must be copied character-for-character from the "
                "excerpt. If nothing is stated, return {\"findings\": []}.\n\n"
                f"EXCERPT:\n{text[:6000]}"
            )
            try:
                resp = client.messages.create(
                    model=model,
                    max_tokens=800,
                    temperature=1.0 if attempt else 0.0,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = resp.content[0].text
            except Exception as exc:
                log.warning("LLM call failed: %s", exc)
                continue
            import json  # noqa: PLC0415

            m = re.search(r"\{.*\}", raw, re.S)
            if not m:
                continue
            try:
                parsed = json.loads(m.group(0))
            except json.JSONDecodeError:
                continue
            for f in parsed.get("findings", []):
                f["_pos"] = pos
                f["_window"] = text
                findings.append(f)
        results.append(findings)

    # Fold the passes together, keeping only quote-verified findings.
    out: list[Candidate] = []
    seen: set[tuple[str, float]] = set()
    first = results[0] if results else []
    for f in first:
        metric = f.get("metric")
        value = f.get("value_pct")
        quote = (f.get("quote") or "").strip()
        if metric not in wanted or not isinstance(value, (int, float)) or not quote:
            continue
        window = f.get("_window", "")
        if _normalise(quote) not in _normalise(window):
            log.warning(
                "%s: discarding unverifiable LLM extraction for %s (=%s); "
                "supporting quote not found in source",
                doc.fund.ticker, metric, value,
            )
            continue
        agreed = any(
            g.get("metric") == metric and abs(float(g.get("value_pct", -999)) - value) < 1e-6
            for run in results[1:]
            for g in run
        )
        key = (metric, float(value))
        if key in seen:
            continue
        seen.add(key)
        out.append(
            doc.candidate(
                metric,
                float(value),
                unit="pct",
                tier=SourceTier.NARRATIVE_LLM,
                locator=f"LLM extraction @ char {f['_pos']} (quote-verified)",
                excerpt=quote,
                basis={"fee_basis": "stated_rate"},
                flags=[] if agreed else ["llm_low_agreement"],
            )
        )
    return out


def _normalise(s: str) -> str:
    """Whitespace- and punctuation-tolerant comparison for quote verification."""
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip().lower()


# ------------------------------------------------------------------ driver

# Which forms to read for narrative metrics, per entity type, best first.
NARRATIVE_FORMS = {
    "interval_fund": ("486BPOS", "424B3", "N-CSR"),
    "bdc": ("10-K", "424B2"),
    "mortgage_reit": ("10-K",),
}
# Anchor scanning is a linear regex over the raw HTML and only bounded windows
# are ever handed to the HTML parser, so large documents are affordable -- a
# BDC 10-K runs to ~25 MB and carries fee terms found nowhere else. The cap
# exists only to keep a pathological filing (one CCLFX N-CSR is 67 MB, almost
# entirely schedule-of-investments rows) from dominating a run; the same fee
# terms appear in that fund's prospectus.
MAX_DOC_BYTES = 40_000_000


def load_docs(
    fund: Fund,
    client: EdgarClient,
    per_form: int = 1,
    anchor: date | None = None,
) -> list[Doc]:
    """Load the narrative documents in force as of `anchor`.

    Document selection has to respect the anchor the same way figure selection
    does, but the test is different. A figure is eligible on the period it
    covers; a prospectus or 10-K is eligible on when it was *filed*, because it
    states the terms in force from that date. Taking the newest prospectus
    regardless would report a fee rate the client's own reporting quarter never
    saw -- and would do it silently, since a fee rate carries no period end to
    give the mismatch away.
    """
    docs: list[Doc] = []
    for form in NARRATIVE_FORMS.get(fund.entity_type, ()):
        # Over-fetch, then take the newest filing at or before the anchor.
        found = client.filings(fund.cik, forms=[form], limit=max(per_form, 8))
        if anchor is not None:
            eligible = [f for f in found if f.filing_date and f.filing_date <= anchor]
            if not eligible and found:
                log.info(
                    "%s: no %s filed on or before anchor %s; earliest available %s",
                    fund.ticker, form, anchor, found[-1].filing_date,
                )
            found = eligible
        for filing in found[:per_form]:
            try:
                blob = client.get(filing.primary_url)
            except Exception:
                log.warning("could not fetch %s %s", fund.ticker, filing.accession)
                continue
            if len(blob) > MAX_DOC_BYTES:
                log.info(
                    "%s: skipping %s (%s, %.1f MB > %.0f MB cap)",
                    fund.ticker, form, filing.accession, len(blob) / 1e6, MAX_DOC_BYTES / 1e6,
                )
                continue
            docs.append(Doc(fund, filing, blob.decode("utf-8", errors="replace")))
    return docs


def amendment_clock(
    fund: Fund, client: EdgarClient, anchor: date
) -> tuple[date | None, str]:
    """Latest filing at or before `anchor` that could have amended fee terms.

    Returns (date, form). This is the date through which no amendment has been
    disclosed -- deliberately not "the date the rate was confirmed in force".
    A filer is not obliged to restate an unamended fee, so a later silent
    filing is evidence that nothing changed, not confirmation that the rate was
    re-read. The distinction is stated to the client and is preserved in the
    label the cell carries.
    """
    latest: date | None = None
    latest_form = ""
    for form in AMENDABLE_FORMS.get(fund.entity_type, ()):
        for filing in client.filings(fund.cik, forms=[form], limit=6):
            if filing.filing_date and filing.filing_date <= anchor:
                if latest is None or filing.filing_date > latest:
                    latest, latest_form = filing.filing_date, form
                break  # filings come newest-first; the first in range is enough
    return latest, latest_form


def _apply_terms_clock(
    candidates: list[Candidate],
    fund: Fund,
    client: EdgarClient,
    anchor: date,
) -> None:
    """Attach the amendment clock to contractual-terms candidates in place."""
    terms = [c for c in candidates if c.metric in TERMS_METRICS]
    if not terms:
        return
    clock, form = amendment_clock(fund, client, anchor)
    if clock is None:
        return
    for cand in terms:
        # Only ever extends the clock forward; a rate read from a document
        # newer than the last amendable filing keeps its own date.
        if cand.as_of and clock <= cand.as_of:
            continue
        cand.terms_clock = clock
        cand.transforms.append(
            f"staleness measured to {clock} ({form}, no amendment disclosed)"
        )
        # If the rate itself was not restated inside the staleness window, we
        # are relying on the absence of an amendment rather than on a re-read.
        # The client asked to see that difference.
        if cand.as_of and (clock - cand.as_of).days > STALE_LIMIT_DAYS:
            cand.flags.append("rate_not_restated_within_window")


def extract_all(
    fund: Fund,
    client: EdgarClient,
    *,
    use_llm: bool = False,
    llm_client: Any = None,
    anchor: date | None = None,
) -> list[Candidate]:
    out: list[Candidate] = []
    for doc in load_docs(fund, client, anchor=anchor):
        for fn in (fee_tables, return_tables, prose_patterns, superseded_rates):
            try:
                out.extend(fn(doc))
            except Exception:
                log.exception("%s failed on %s %s", fn.__name__, fund.ticker, doc.filing.accession)
        if use_llm:
            missing = {M_MGMT_FEE, M_INCENTIVE_FEE, M_HURDLE} - {c.metric for c in out}
            if missing:
                out.extend(llm_extract(doc, missing, client=llm_client))

    kept = [c for c in out if c.metric in fund.supported_metrics]
    if anchor is not None:
        _apply_terms_clock(kept, fund, client, anchor)
    return kept
