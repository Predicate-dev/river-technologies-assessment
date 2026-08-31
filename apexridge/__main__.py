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

    funds = FUNDS
    if args.funds:
        wanted = {t.upper() for t in args.funds}
        funds = tuple(f for f in FUNDS if f.ticker in wanted)
        missing = wanted - {f.ticker for f in funds}
        if missing:
            parser.error(f"unknown ticker(s): {', '.join(sorted(missing))}")

    client = EdgarClient(offline=args.offline)
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
        + (f"\nNAV trend:   {paths['trend']}" if "trend" in paths else ""),
        file=sys.stderr,
    )
    return 2 if lost_coverage else 0


if __name__ == "__main__":
    raise SystemExit(main())
