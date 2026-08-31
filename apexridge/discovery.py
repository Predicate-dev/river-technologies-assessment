"""Fund discovery: search EDGAR, classify a filer, add it to the peer set.

The PMs want to find a fund and add it rather than being locked to four
pre-configured ones. Two things make that harder than a lookup, and both are
handled here rather than papered over.

**Search does not identify a fund.** Neither CCLFX nor TAKIX appears in SEC's
ticker files at all -- the interval funds, which are the type this client cares
most about, are invisible to a ticker-based lookup. And a name search for "Golub
Capital BDC" returns three CIKs, none of them the right one; they are affiliated
entities. So search returns *candidates for a person to choose from* and never
auto-resolves.

**A fund only works if we can classify it.** Every adapter keys off entity type,
fiscal year end and share class. Guessing those wrong does not produce a blank
-- it produces confidently wrong numbers, which is the one outcome this system
exists to prevent. Classification is therefore evidence-based and refuses when
the evidence is thin: an unclassifiable filer is reported as such rather than
added on a guess.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import date

from .config import Fund, registry
from .edgar import EdgarClient

log = logging.getLogger(__name__)

TICKER_FILE = "https://www.sec.gov/files/company_tickers.json"
# EDGAR full-text search. Preferred over the legacy browse-edgar endpoint, which
# rate-limits and times out heavily, and -- more importantly -- over the ticker
# files, which omit non-traded interval funds entirely. Full-text search finds
# CCLFX and returns its ticker, which no other SEC index does.
FULL_TEXT_SEARCH = "https://efts.sec.gov/LATEST/search-index?q={q}"
NAME_SEARCH = (
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={q}"
    "&type=&dateb=&owner=include&count=40&output=atom"
)
_DISPLAY = re.compile(r"^(?P<name>.+?)\s*(?:\((?P<ticker>[A-Z]{2,6})\)\s*)?\(CIK\s*(?P<cik>\d+)\)")

# Forms that identify what a filer is. An interval fund files N-CSR and never a
# 10-K; a BDC files both a 10-K and BDC-specific closed-end fund tags; a REIT
# files a 10-K and carries a REIT SIC code.
_INTERVAL_FORMS = {"N-CSR", "N-CSRS", "NPORT-P", "486BPOS"}
_OPERATING_FORMS = {"10-K", "10-Q"}
_REIT_SIC = {"6798"}


@dataclass
class SearchHit:
    cik: str
    name: str
    ticker: str = ""

    @property
    def cik_padded(self) -> str:
        return f"{int(self.cik):010d}"


@dataclass
class Classification:
    """What we could establish about a filer, and how sure we are."""

    cik: str
    name: str
    entity_type: str = ""
    fiscal_year_end: str = ""
    forms: tuple[str, ...] = ()
    sic: str = ""
    tickers: tuple[str, ...] = ()
    confident: bool = False
    reasons: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return bool(self.entity_type and self.fiscal_year_end and self.confident)


# Forms whose reporting period ends on the filer's fiscal year end.
_ANNUAL_FORMS = ("10-K", "N-CSR")


def _annual_period_end(recent: dict) -> date | None:
    """Period end of the most recent annual filing, as evidence of fiscal year."""
    forms = recent.get("form", [])
    reports = recent.get("reportDate", [])
    best: date | None = None
    for form, rep in zip(forms, reports):
        if form.upper() not in _ANNUAL_FORMS or not rep:
            continue
        try:
            d = date.fromisoformat(rep[:10])
        except ValueError:
            continue
        if best is None or d > best:
            best = d
    return best


def _from_full_text(client: EdgarClient, query: str) -> dict[str, SearchHit]:
    """Candidates from EDGAR full-text search, the only index that sees all
    fund types."""
    hits: dict[str, SearchHit] = {}
    url = FULL_TEXT_SEARCH.format(q=urllib.parse.quote(f'"{query}"'))
    payload = json.loads(client.get(url))
    for hit in payload.get("hits", {}).get("hits", []):
        src = hit.get("_source", {})
        for display in src.get("display_names", []):
            m = _DISPLAY.match(display.strip())
            if not m:
                continue
            cik = str(int(m.group("cik")))
            existing = hits.get(cik)
            ticker = m.group("ticker") or (existing.ticker if existing else "")
            hits[cik] = SearchHit(
                cik=cik, name=m.group("name").strip(), ticker=ticker or ""
            )
    return hits


def search(client: EdgarClient, query: str, limit: int = 15) -> list[SearchHit]:
    """Candidate filers matching a name or ticker. Never auto-resolves.

    Exact ticker lookup first because it is unambiguous when it works, then
    full-text search, which is the only SEC index that sees non-traded interval
    funds -- the ticker files omit them entirely and the legacy company-search
    endpoint rate-limits to the point of being unusable.
    """
    hits: dict[str, SearchHit] = {}
    q = query.strip()

    try:
        tickers = json.loads(client.get(TICKER_FILE))
        for row in tickers.values():
            if q.upper() == str(row.get("ticker", "")).upper():
                hits[str(row["cik_str"])] = SearchHit(
                    cik=str(row["cik_str"]), name=row["title"], ticker=row["ticker"]
                )
    except Exception:
        log.info("ticker file unavailable; relying on full-text search")

    try:
        for cik, hit in _from_full_text(client, q).items():
            hits.setdefault(cik, hit)
    except Exception as exc:
        log.warning("full-text search failed for %r: %s", q, exc)

    return list(hits.values())[:limit]


def classify(client: EdgarClient, cik: str) -> Classification:
    """Establish entity type and fiscal year end from the filer's own history.

    Evidence, not inference from the name: which forms it actually files, its
    SIC code, and the fiscal year end EDGAR records. Where the forms do not
    settle it, `confident` stays False and the caller must not add the fund.
    """
    data = client.submissions(cik)
    recent = data.get("filings", {}).get("recent", {})
    forms = tuple(sorted(set(recent.get("form", []))))
    sic = str(data.get("sic", "") or "")
    fye_raw = str(data.get("fiscalYearEnd", "") or "")  # "MMDD"
    name = data.get("name", "")
    tickers = tuple(data.get("tickers", []) or [])

    c = Classification(
        cik=str(int(cik)), name=name, forms=forms, sic=sic, tickers=tickers
    )

    # Fiscal year end comes from the filer's own annual filings, not from
    # EDGAR's `fiscalYearEnd` field. That field is registration metadata and
    # goes stale: EDGAR records 12-31 for CCLFX, whose N-CSR plainly covers a
    # year ended 31 March. Every anchoring and staleness decision keys off this,
    # so it is derived from evidence and only falls back to the field.
    annual = _annual_period_end(recent)
    if annual is not None:
        c.fiscal_year_end = annual.strftime("%m-%d")
        c.reasons.append(
            f"fiscal year end {c.fiscal_year_end} taken from the most recent "
            f"annual filing (period ended {annual.isoformat()})"
        )
        if len(fye_raw) == 4 and fye_raw != annual.strftime("%m%d"):
            c.reasons.append(
                f"note: EDGAR's registered fiscalYearEnd is {fye_raw[:2]}-{fye_raw[2:]}, "
                "which disagrees with the filings; the filings were used"
            )
    elif len(fye_raw) == 4 and fye_raw.isdigit():
        c.fiscal_year_end = f"{fye_raw[:2]}-{fye_raw[2:]}"
        c.reasons.append(
            "fiscal year end taken from EDGAR registration metadata; no annual "
            "filing found to confirm it"
        )
    else:
        c.reasons.append("no fiscal year end could be established")

    form_set = set(forms)
    has_interval = bool(form_set & _INTERVAL_FORMS)
    has_operating = bool(form_set & _OPERATING_FORMS)

    if has_interval and not has_operating:
        c.entity_type = "interval_fund"
        c.confident = True
        c.reasons.append(
            f"files {sorted(form_set & _INTERVAL_FORMS)} and no 10-K: a registered "
            "closed-end fund, not an operating company"
        )
    elif has_operating and sic in _REIT_SIC:
        c.entity_type = "mortgage_reit"
        c.confident = True
        c.reasons.append(f"files 10-K with REIT SIC {sic}")
    elif has_operating and not has_interval:
        c.entity_type = "bdc"
        c.confident = True
        c.reasons.append(
            "files 10-K/10-Q without closed-end fund reporting forms: treated as "
            "a BDC-style operating filer"
        )
        if sic and sic not in {"6726", "6199", ""}:
            c.confident = False
            c.reasons.append(
                f"SIC {sic} is not an investment-company code; entity type is a "
                "guess and the fund should not be added without review"
            )
    elif has_operating and has_interval:
        c.reasons.append(
            "files both 10-K and closed-end fund forms; entity type is ambiguous "
            "and the adapters would not know which basis applies"
        )
    else:
        c.reasons.append(
            "files neither 10-K/10-Q nor N-CSR/N-PORT: no source adapter reaches "
            "this filer"
        )

    if not c.fiscal_year_end:
        c.confident = False
    return c


def to_fund(c: Classification, institutional_class: str = "") -> Fund:
    """Build a registry entry from a confident classification."""
    if not c.usable:
        raise ValueError(
            f"cannot add {c.name or c.cik}: {'; '.join(c.reasons) or 'unclassified'}"
        )
    forms = {
        "interval_fund": ("NPORT-P", "N-CSR", "N-CSRS", "486BPOS"),
        "bdc": ("10-K", "10-Q", "8-K"),
        "mortgage_reit": ("10-K", "10-Q", "8-K"),
    }[c.entity_type]
    supported = tuple(
        k for k in registry().keys
        if c.entity_type != "mortgage_reit" or not k.startswith("net_return")
    )
    return Fund(
        name=c.name,
        ticker=(c.tickers[0] if c.tickers else c.cik),
        cik=f"{int(c.cik):010d}",
        entity_type=c.entity_type,
        fiscal_year_end=c.fiscal_year_end,
        primary_forms=forms,
        supported_metrics=supported,
        institutional_class=institutional_class
        or ("Class I" if c.entity_type == "interval_fund" else ""),
        notes="added via fund discovery; classification: " + "; ".join(c.reasons),
    )


# --------------------------------------------------------------- peer sets


def fund_to_dict(f: Fund) -> dict:
    return {
        "name": f.name,
        "ticker": f.ticker,
        "cik": f.cik,
        "entity_type": f.entity_type,
        "fiscal_year_end": f.fiscal_year_end,
        "primary_forms": list(f.primary_forms),
        "supported_metrics": list(f.supported_metrics),
        "institutional_class": f.institutional_class,
        "notes": f.notes,
    }


def save_peers(funds: tuple[Fund, ...], path) -> str:
    """Persist a peer set so it survives between runs.

    Written as plain JSON rather than a pickle so a reviewer can read it, and
    so the CIO -- who owns the peer list -- can see exactly what is in it
    without running anything.
    """
    from pathlib import Path as _Path

    p = _Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([fund_to_dict(f) for f in funds], indent=2) + "\n")
    return str(p)


def load_peers(path) -> tuple[Fund, ...]:
    """Read a saved peer set.

    Classification is NOT re-derived here: it was established from filings when
    the fund was added, and silently re-classifying on load could change which
    extractors run without anyone asking for it. Re-add the fund to refresh it.
    """
    from pathlib import Path as _Path

    raw = json.loads(_Path(path).read_text())
    if not isinstance(raw, list):
        raise ValueError(f"{path}: expected a JSON list of funds")
    out = []
    for r in raw:
        out.append(
            Fund(
                name=r["name"],
                ticker=r["ticker"],
                cik=r["cik"],
                entity_type=r["entity_type"],
                fiscal_year_end=r["fiscal_year_end"],
                primary_forms=tuple(r.get("primary_forms", ())),
                supported_metrics=tuple(r.get("supported_metrics", ())),
                institutional_class=r.get("institutional_class", ""),
                notes=r.get("notes", ""),
            )
        )
    return tuple(out)
