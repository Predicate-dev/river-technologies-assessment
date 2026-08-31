"""Command-line entry point.

    python -m apexridge                      # full run, writes to output/
    python -m apexridge --funds GBDC KREF    # subset
    python -m apexridge --anchor 2025-09-30  # a different reporting quarter
    python -m apexridge --offline            # cache only, no network
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path

from .config import ALL_METRICS, FUNDS, OUTPUT_DIR, SEC_USER_AGENT
from .edgar import EdgarClient
from .pipeline import run as run_pipeline
from .render.table import board_markdown, write_outputs


def _date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="apexridge",
        description="Benchmark Apex Ridge against competitor credit funds using SEC EDGAR.",
    )
    parser.add_argument(
        "--anchor", type=_date, default=None,
        help="Reporting quarter end, YYYY-MM-DD (default: the Q4 2025 anchor).",
    )
    parser.add_argument(
        "--funds", nargs="*", metavar="TICKER",
        help="Subset of competitor tickers (default: all four).",
    )
    parser.add_argument(
        "--out", default=str(OUTPUT_DIR),
        help="Output directory (default: output/).",
    )
    parser.add_argument(
        "--nport-limit", type=int, default=8,
        help="N-PORT filings to download per interval fund. Each is ~8MB; "
             "this caps trailing-return depth, so a shortfall is our limit, "
             "not the filer's (default: 8).",
    )
    parser.add_argument(
        "--offline", action="store_true",
        help="Use only cached filings. Fails on a cache miss rather than "
             "silently reporting less.",
    )
    parser.add_argument(
        "--use-llm", action="store_true",
        help="Enable the LLM narrative tier. Requires ANTHROPIC_API_KEY and, "
             "per the open compliance item, client sign-off.",
    )
    parser.add_argument(
        "--find", metavar="QUERY",
        help="Search EDGAR for a fund by ticker or name and print candidates "
             "with their classification. Does not run the benchmark.",
    )
    parser.add_argument(
        "--add-cik", nargs="*", metavar="CIK", default=None,
        help="Add filers to the comparison set by CIK, alongside the configured "
             "peers. Each is classified from its own filings and refused if the "
             "classification is not confident.",
    )
    parser.add_argument(
        "--metrics", metavar="JSON", default=None,
        help="A JSON file of custom metric definitions, added to the built-in "
             "set. See metrics/custom_metrics.json for the format.",
    )
    parser.add_argument(
        "--compare-to", metavar="COVERAGE_CSV", default=None,
        help="A previous run's coverage_breakdown.csv. Reports what populated "
             "then and blanks now -- the signal that a filer changed wording. "
             "Exits non-zero if any coverage was lost, so it can gate a "
             "scheduled run.",
    )
    parser.add_argument("--print", action="store_true", help="Print the table to stdout.")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.find:
        from .discovery import classify, search

        client = EdgarClient(offline=args.offline)
        hits = search(client, args.find)
        if not hits:
            print(f"No filers matched {args.find!r}.", file=sys.stderr)
            print(
                "Note: SEC's ticker files do not list non-traded interval funds, "
                "and the name-search endpoint rate-limits heavily. Try the exact "
                "registrant name, or supply the CIK directly with --add-cik.",
                file=sys.stderr,
            )
            return 1
        print(f"{len(hits)} candidate(s) for {args.find!r}:\n")
        for h in hits:
            c = classify(client, h.cik)
            mark = "usable" if c.usable else "NOT USABLE"
            print(f"  CIK {h.cik_padded}  {c.name or h.name}")
            print(f"      {mark}: {c.entity_type or 'unclassified'}, "
                  f"fiscal year end {c.fiscal_year_end or 'unknown'}")
            for r in c.reasons:
                print(f"      - {r}")
            print()
        print("Add one with: --add-cik <CIK>", file=sys.stderr)
        return 0

    if args.metrics:
        from . import config as _config
        from .metrics import build_registry

        registry = build_registry(args.metrics)
        _config.use_registry(registry)
        added = [s.key for s in registry.custom]
        print(f"Custom metrics: {', '.join(added)}", file=sys.stderr)

    funds = FUNDS
    if args.funds:
        wanted = {t.upper() for t in args.funds}
        funds = tuple(f for f in FUNDS if f.ticker in wanted)
        missing = wanted - {f.ticker for f in funds}
        if missing:
            parser.error(f"unknown ticker(s): {', '.join(sorted(missing))}")

    client = EdgarClient(offline=args.offline)

    if args.add_cik:
        from .discovery import classify, to_fund

        added = []
        for cik in args.add_cik:
            c = classify(client, cik)
            if not c.usable:
                parser.error(
                    f"cannot add CIK {cik} ({c.name or 'unknown'}): "
                    + "; ".join(c.reasons)
                    + ". Adding a filer we cannot classify would produce "
                    "confidently wrong figures rather than blanks."
                )
            added.append(to_fund(c))
        funds = funds + tuple(added)
        for f in added:
            print(
                f"Added {f.ticker} ({f.name}) as {f.entity_type}, "
                f"fiscal year end {f.fiscal_year_end}",
                file=sys.stderr,
            )

    anchor_kwargs = {"anchor": args.anchor} if args.anchor else {}

    print(f"SEC User-Agent: {SEC_USER_AGENT}", file=sys.stderr)
    result = run_pipeline(
        funds=funds,
        client=client,
        nport_limit=args.nport_limit,
        use_llm=args.use_llm,
        **anchor_kwargs,
    )

    paths = write_outputs(result, args.out, client=client)
    if args.print:
        print(board_markdown(result))

    lost_coverage: list = []
    if args.compare_to:
        from .render.regression import LOST, run_regression

        changes, report = run_regression(
            args.compare_to, Path(args.out) / "coverage_breakdown.csv"
        )
        (Path(args.out) / "regression_report.md").write_text(report)
        lost = lost_coverage = [c for c in changes if c.kind == LOST]
        print(f"Regression:  {Path(args.out) / 'regression_report.md'}", file=sys.stderr)
        if lost:
            print(
                f"\nWARNING: {len(lost)} cell(s) populated in the previous run and "
                "blank now:",
                file=sys.stderr,
            )
            for c in lost:
                print(f"  - {c.fund} {c.label}", file=sys.stderr)

    filled = sum(
        1
        for res in result.results.values()
        for m in ALL_METRICS
        if res.resolved[m].value is not None
    )
    total = len(result.results) * len(ALL_METRICS)
    print(
        f"\nAnchor {result.anchor}: {filled}/{total} competitor cells populated, "
        f"{len(result.conflicts)} conflict(s) resolved, "
        f"{len(result.notices)} blank(s) explained.",
        file=sys.stderr,
    )
    print(
        f"Board table: {paths['board']}\n"
        f"Audit trail: {paths['audit']}\n"
        f"Coverage:    {paths['coverage']}\n"
        f"Apex vs peers: {paths['comparison']}"
        + (f"\nWord report: {paths['word']}" if "word" in paths else "")
        + (f"\nNAV trend:   {paths['trend']}" if "trend" in paths else ""),
        file=sys.stderr,
    )
    return 2 if lost_coverage else 0


if __name__ == "__main__":
    raise SystemExit(main())
