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
NAME_SEARCH = (
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={q}"
    "&type=&dateb=&owner=include&count=40&output=atom"
)

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


def search(client: EdgarClient, query: str, limit: int = 15) -> list[SearchHit]:
    """Candidate filers matching a name or ticker. Never auto-resolves.

    Ticker lookup first because it is exact when it works; name search after,
    because it is the only route to the non-traded funds.
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
        log.warning("ticker file unavailable; falling back to name search only")

    try:
        raw = client.get(NAME_SEARCH.format(q=urllib.parse.quote(q))).decode(
            "utf-8", errors="replace"
        )
        for m in re.finditer(
            r"<CIK>(\d+)</CIK>.*?<conformed-name>([^<]+)</conformed-name>", raw, re.S
        ):
            cik, name = m.group(1), m.group(2).strip()
            hits.setdefault(str(int(cik)), SearchHit(cik=str(int(cik)), name=name))
        if not hits:
            for cik in re.findall(r"<CIK>(\d+)</CIK>", raw):
                hits.setdefault(str(int(cik)), SearchHit(cik=str(int(cik)), name=""))
    except Exception as exc:
        log.warning("name search failed for %r: %s", q, exc)

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
