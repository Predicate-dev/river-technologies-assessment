"""SEC EDGAR client: rate-limited, disk-cached, User-Agent compliant.

Design notes:
  * SEC caps automated access at 10 requests/second and requires a descriptive
    User-Agent. We self-throttle below the cap and back off on 429/403.
  * Everything is cached to disk keyed by URL. Re-runs are offline, which makes
    the pipeline deterministic and means a live demo cannot be broken by a
    network hiccup or a rate-limit trip.
  * Filing documents are large (one CCLFX N-PORT primary_doc.xml is 8.3 MB), so
    the cache is on disk rather than in memory and callers stream where they can.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import requests

from .config import CACHE_DIR, SEC_MAX_RPS, SEC_USER_AGENT

log = logging.getLogger(__name__)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
ARCHIVE_BASE = "https://www.sec.gov/Archives/edgar/data"


class EdgarError(RuntimeError):
    pass


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


@dataclass(frozen=True)
class Filing:
    """One filing from a company's submission history."""

    cik: str
    form: str
    accession: str
    filing_date: date | None
    report_date: date | None
    primary_document: str
    primary_doc_description: str = ""

    @property
    def accession_nodash(self) -> str:
        return self.accession.replace("-", "")

    @property
    def base_url(self) -> str:
        return f"{ARCHIVE_BASE}/{int(self.cik)}/{self.accession_nodash}"

    @property
    def primary_url(self) -> str:
        return f"{self.base_url}/{self.primary_document}"

    @property
    def filing_index_url(self) -> str:
        """Human-facing index page -- what a compliance reviewer would open."""
        return f"{self.base_url}/{self.accession}-index.htm"

    def doc_url(self, filename: str) -> str:
        return f"{self.base_url}/{filename}"


class EdgarClient:
    """Thin, polite, cached HTTP client for EDGAR."""

    def __init__(
        self,
        user_agent: str = SEC_USER_AGENT,
        cache_dir: Path = CACHE_DIR,
        max_rps: float = SEC_MAX_RPS,
        offline: bool = False,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.offline = offline
        self._min_interval = 1.0 / max_rps
        self._last_request = 0.0
        self._lock = threading.Lock()
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept-Encoding": "gzip, deflate",
            }
        )

    # ------------------------------------------------------------------ HTTP

    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode()).hexdigest()[:20]
        # Keep a readable suffix so the cache is inspectable by hand.
        tail = url.rstrip("/").split("/")[-1][-60:].replace("?", "_")
        return self.cache_dir / f"{digest}_{tail}"

    def _throttle(self) -> None:
        with self._lock:
            elapsed = time.monotonic() - self._last_request
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_request = time.monotonic()

    def get(self, url: str, *, force: bool = False) -> bytes:
        path = self._cache_path(url)
        if path.exists() and not force:
            return path.read_bytes()
        if self.offline:
            raise EdgarError(f"offline and not cached: {url}")

        last_err: Exception | None = None
        for attempt in range(4):
            self._throttle()
            try:
                resp = self._session.get(url, timeout=60)
            except requests.RequestException as exc:  # network flake
                last_err = exc
                time.sleep(2**attempt)
                continue
            if resp.status_code == 200:
                path.write_bytes(resp.content)
                log.debug("fetched %s (%d bytes)", url, len(resp.content))
                return resp.content
            if resp.status_code in (403, 429, 500, 502, 503):
                # SEC throttles with 403 as well as 429.
                wait = 2**attempt
                log.warning("EDGAR %s on %s, retry in %ss", resp.status_code, url, wait)
                last_err = EdgarError(f"HTTP {resp.status_code} for {url}")
                time.sleep(wait)
                continue
            raise EdgarError(f"HTTP {resp.status_code} for {url}")
        raise EdgarError(f"failed after retries: {url} ({last_err})")

    def get_json(self, url: str, *, force: bool = False) -> dict[str, Any]:
        return json.loads(self.get(url, force=force))

    def get_text(self, url: str, *, force: bool = False) -> str:
        return self.get(url, force=force).decode("utf-8", errors="replace")

    # -------------------------------------------------------------- EDGAR API

    def submissions(self, cik: str) -> dict[str, Any]:
        """Company submission history. Includes the most recent ~1000 filings."""
        return self.get_json(SUBMISSIONS_URL.format(cik=self._pad(cik)))

    def company_facts(self, cik: str) -> dict[str, Any]:
        """XBRL company facts. Rich for 10-K/10-Q filers, near-empty for the
        interval funds -- callers must handle both."""
        return self.get_json(COMPANYFACTS_URL.format(cik=self._pad(cik)))

    def filings(
        self,
        cik: str,
        forms: Iterable[str] | None = None,
        limit: int | None = None,
        since: date | None = None,
    ) -> list[Filing]:
        """Filing history, newest first, optionally filtered by form type."""
        data = self.submissions(cik)
        recent = data.get("filings", {}).get("recent", {})
        wanted = {f.upper() for f in forms} if forms else None
        out: list[Filing] = []
        cols = ("form", "accessionNumber", "filingDate", "reportDate",
                "primaryDocument", "primaryDocDescription")
        series = [recent.get(c, []) for c in cols]
        for form, acc, fdate, rdate, doc, desc in zip(*series):
            if wanted and form.upper() not in wanted:
                continue
            fd = _parse_date(fdate)
            if since and fd and fd < since:
                continue
            out.append(
                Filing(
                    cik=self._pad(cik),
                    form=form,
                    accession=acc,
                    filing_date=fd,
                    report_date=_parse_date(rdate),
                    primary_document=doc,
                    primary_doc_description=desc or "",
                )
            )
            if limit and len(out) >= limit:
                break
        return out

    def filing_documents(self, filing: Filing) -> list[dict[str, Any]]:
        """Every document in a filing, from its JSON index."""
        idx = self.get_json(f"{filing.base_url}/index.json")
        return idx.get("directory", {}).get("item", [])

    @staticmethod
    def _pad(cik: str | int) -> str:
        return f"{int(cik):010d}"
