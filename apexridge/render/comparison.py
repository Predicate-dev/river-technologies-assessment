"""Comparison of Apex Ridge against the peer set.

Placing columns side by side is adjacency, not comparison. This module does the
comparison the brief asks for: where Apex sits in the peer distribution, and by
how much.

Two things it is careful about.

**Basis.** A peer figure struck on a different basis is not in the same
distribution. KREF's management fee is a percentage of adjusted equity; the
credit funds' are percentages of net or managed assets. Averaging them produces
a number describing nothing, so peers whose basis diverges from the row's
reference are excluded from the statistics and named as excluded.

**Direction.** A rank only means something if better and worse are defined. They
are for returns, yields and fee terms. They are not for NAV per share (a share
price, not a quality) or leverage (a risk posture, not a score), so those report
position without ranking anything.

**The Apex gate.** Peer-to-peer statistics are valid today. Apex-versus-peer
deltas are not: the client cannot yet confirm the share class or fee treatment
behind her own column, and a delta between two numbers of unknown basis is
precisely the confidently-wrong figure this system exists to prevent. So the
deltas are computed and withheld, behind one flag, exactly as the technical
document claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

from ..config import (
    APEX_BASIS_CONFIRMED,
    APEX_LEVERAGE_BASIS_CONFIRMED,
    ALL_METRICS,
    METRIC_LABELS,
    M_DIST_YIELD,
    M_HURDLE,
    M_INCENTIVE_FEE,
    LEVERAGE_METRICS,
    M_LEVERAGE_ECON,
    M_LEVERAGE_REG,
    M_MGMT_FEE,
    M_NAV_PS,
    M_RETURN_1Y,
    M_RETURN_3Y,
    M_RETURN_5Y,
)
from ..pipeline import BenchmarkRun
from .cells import format_basis
from .table import APEX_COLUMN, build_cells, format_value

# +1: higher is better for the fund's investors. -1: lower is better.
# 0: no defensible direction, so position is reported and nothing is ranked.
DIRECTION = {
    M_RETURN_1Y: 1,
    M_RETURN_3Y: 1,
    M_RETURN_5Y: 1,
    M_DIST_YIELD: 1,
    M_MGMT_FEE: -1,
    M_INCENTIVE_FEE: -1,
    M_HURDLE: 1,  # a higher hurdle means carry is earned above a higher bar
    M_NAV_PS: 0,  # a share price, not a quality
    M_LEVERAGE_REG: 0,  # a risk posture, not a score
    M_LEVERAGE_ECON: 0,
}


# What actually breaks comparability, per metric. Deliberately NOT the whole
# basis string: two figures can measure the same thing by different methods and
# still belong in one distribution. GBDC's NAV total return and TAKIX's
# chain-linked annual total return are both net returns on NAV, so they compare;
# KREF's fee on adjusted equity and GBDC's on net assets do not. Excluding on
# method rather than on base would defeat the normalization the system exists to
# do, and leave most rows with a single "peer".
def comparability_key(metric: str, basis: dict[str, object]) -> str:
    if metric in (M_MGMT_FEE, M_INCENTIVE_FEE):
        fee_basis = str(basis.get("fee_basis", ""))
        return "adjusted_equity" if "adjusted_equity" in fee_basis else "assets"
    if metric == M_NAV_PS:
        return str(basis.get("measure", "nav_per_share"))
    if metric == M_DIST_YIELD:
        return str(basis.get("denominator", ""))
    if metric in LEVERAGE_METRICS:
        return str(basis.get("leverage_basis", ""))
    # Returns and hurdles: every construction here is the same concept, and the
    # share class is already enforced upstream by the render layer.
    return ""


@dataclass
class MetricComparison:
    metric: str
    apex: float | None
    peers: dict[str, float] = field(default_factory=dict)
    excluded: dict[str, str] = field(default_factory=dict)  # ticker -> basis
    reference_basis: str = ""

    @property
    def peer_median(self) -> float | None:
        return median(self.peers.values()) if self.peers else None

    @property
    def peer_range(self) -> tuple[float, float] | None:
        if not self.peers:
            return None
        return min(self.peers.values()), max(self.peers.values())

    @property
    def direction(self) -> int:
        return DIRECTION.get(self.metric, 0)

    @property
    def apex_delta(self) -> float | None:
        """Apex minus the peer median. Meaningless until Apex's basis is known."""
        if self.apex is None or self.peer_median is None:
            return None
        return self.apex - self.peer_median

    @property
    def apex_rank(self) -> tuple[int, int] | None:
        """(position, out_of) with Apex included, best first. None if undirected."""
        if self.apex is None or not self.peers or self.direction == 0:
            return None
        values = list(self.peers.values()) + [self.apex]
        ordered = sorted(values, reverse=self.direction > 0)
        return ordered.index(self.apex) + 1, len(ordered)

    @property
    def peers_ranked(self) -> list[tuple[str, float]]:
        """Peers alone, best first. Valid regardless of Apex's basis."""
        if self.direction == 0:
            return sorted(self.peers.items(), key=lambda kv: kv[1])
        return sorted(self.peers.items(), key=lambda kv: kv[1], reverse=self.direction > 0)


def compare(run: BenchmarkRun) -> dict[str, MetricComparison]:
    grid = build_cells(run)
    out: dict[str, MetricComparison] = {}
    for metric in ALL_METRICS:
        row = grid[metric]
        apex_cell = row[APEX_COLUMN]

        # The reference is the comparability key most peers share; a peer off
        # it is not in the same distribution and is excluded, not averaged in.
        keys: dict[str, str] = {}
        for ticker, res in run.results.items():
            cell = row[ticker]
            rm = res.resolved.get(metric)
            if cell.value is None or rm is None or rm.chosen is None:
                continue
            keys[ticker] = comparability_key(metric, rm.chosen.basis)
        reference = (
            max(set(keys.values()), key=list(keys.values()).count) if keys else ""
        )

        comparison = MetricComparison(
            metric=metric,
            apex=apex_cell.value,
            reference_basis=reference,
        )
        for ticker in run.results:
            cell = row[ticker]
            if cell.value is None:
                continue
            if keys.get(ticker, reference) != reference:
                comparison.excluded[ticker] = cell.basis
            else:
                comparison.peers[ticker] = cell.value
        out[metric] = comparison
    return out


def comparison_markdown(run: BenchmarkRun) -> str:
    comps = compare(run)
    lines = [
        "# Apex Ridge versus the peer set",
        "",
        f"Reporting quarter {run.anchor.isoformat()}.",
        "",
    ]
    if APEX_BASIS_CONFIRMED and not APEX_LEVERAGE_BASIS_CONFIRMED:
        lines += [
            "> **Leverage deltas only are withheld.** The client confirmed the "
            "share class and fee treatment behind their figures, which is what "
            "unblocks returns, fees and yield. It did not establish which "
            "leverage basis their single unlabelled ratio uses, and the two "
            "bases differ by more than a factor of two. Their figure is shown "
            "on the regulatory row and kept out of the leverage medians, "
            "ranges and deltas until they state the basis.",
            "",
        ]
    if not APEX_BASIS_CONFIRMED:
        lines += [
            "> **Apex-versus-peer deltas are withheld.** The share class and fee "
            "treatment behind Apex Ridge's own figures are not yet confirmed, and "
            "a delta between two numbers of unknown basis is exactly the "
            "confidently-wrong figure this system exists to prevent. The "
            "comparison is computed and will render on confirmation — it is a "
            "single flag (`APEX_BASIS_CONFIRMED`), not a rebuild.",
            "",
            "Peer-to-peer statistics below are unaffected: they do not depend on "
            "Apex's basis.",
            "",
        ]

    lines += [
        "| Metric | Peer median | Peer range | Peers, best first | Apex |",
        "| --- | --- | --- | --- | --- |",
    ]
    for metric in ALL_METRICS:
        c = comps[metric]
        unit = "usd" if metric.endswith("_usd") else ("ratio" if metric.endswith("_dte") else "pct")
        if not c.peers:
            lines.append(f"| {METRIC_LABELS[metric]} | — | — | no comparable peers | — |")
            continue
        lo, hi = c.peer_range
        ranked = ", ".join(
            f"{t} {format_value(v, unit)}" for t, v in c.peers_ranked
        )
        if c.direction == 0:
            ranked = ", ".join(f"{t} {format_value(v, unit)}" for t, v in c.peers_ranked)
            ranked += " _(ordered, not ranked)_"

        if c.apex is None:
            apex_cell = "—"
        elif not APEX_BASIS_CONFIRMED:
            apex_cell = f"{format_value(c.apex, unit)} _(delta withheld)_"
        elif metric in LEVERAGE_METRICS and not APEX_LEVERAGE_BASIS_CONFIRMED:
            apex_cell = (
                f"{format_value(c.apex, unit)} _(delta withheld: leverage basis "
                "unconfirmed)_"
            )
        else:
            delta = c.apex_delta
            rank = c.apex_rank
            parts = [format_value(c.apex, unit)]
            if delta is not None:
                parts.append(f"({delta:+.2f} vs median)")
            if rank is not None:
                parts.append(f"rank {rank[0]}/{rank[1]}")
            apex_cell = " ".join(parts)

        lines.append(
            f"| {METRIC_LABELS[metric]} | {format_value(c.peer_median, unit)} "
            f"| {format_value(lo, unit)}–{format_value(hi, unit)} | {ranked} | {apex_cell} |"
        )

    excluded_any = {m: c for m, c in comps.items() if c.excluded}
    if excluded_any:
        lines += [
            "",
            "## Excluded from the statistics — different basis",
            "",
            "A figure on a different basis is not in the same distribution. These "
            "are reported in the board table but kept out of the medians and "
            "ranges above rather than averaged into them.",
            "",
        ]
        for metric, c in excluded_any.items():
            for ticker, basis in c.excluded.items():
                lines.append(
                    f"- **{ticker} — {METRIC_LABELS[metric]}**: {basis} "
                    f"(row reference: {c.reference_basis or 'none'})"
                )

    undirected = [m for m in ALL_METRICS if DIRECTION.get(m, 0) == 0]
    lines += [
        "",
        "## Not ranked",
        "",
        "A rank implies better and worse. For "
        + " and ".join(METRIC_LABELS[m] for m in undirected)
        + " that is not defined — a NAV per share is a share price, not a "
        "quality, and a leverage ratio is a risk posture, not a score. Both are "
        "shown in order without a ranking claim.",
    ]
    return "\n".join(lines)
