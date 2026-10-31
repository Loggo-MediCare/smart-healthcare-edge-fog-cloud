"""Aggregate simulation results."""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass

from .sim import Result


def percentile(sorted_vals: list[float], q: float) -> float:
    """Nearest-rank percentile of an already sorted list."""
    if not sorted_vals:
        return float("nan")
    k = max(0, math.ceil(q / 100.0 * len(sorted_vals)) - 1)
    return sorted_vals[k]


@dataclass(frozen=True)
class Summary:
    n: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    miss_rate: float
    cost_usd: float
    off_premises_mb: float
    tiers: dict[str, int]

    @property
    def tier_mix(self) -> str:
        return " ".join(f"{t}:{c}" for t, c in sorted(self.tiers.items()))


def summarize(results: list[Result]) -> Summary:
    lat = sorted(r.latency_ms for r in results)
    n = len(results)
    return Summary(
        n=n,
        p50_ms=percentile(lat, 50),
        p95_ms=percentile(lat, 95),
        p99_ms=percentile(lat, 99),
        miss_rate=sum(r.missed for r in results) / n if n else float("nan"),
        cost_usd=sum(r.cost_usd for r in results),
        off_premises_mb=sum(r.off_premises_kb for r in results) / 1000.0,
        tiers=dict(Counter(r.tier for r in results)),
    )


def by_workload(results: list[Result]) -> dict[str, Summary]:
    groups: dict[str, list[Result]] = defaultdict(list)
    for r in results:
        groups[r.workload].append(r)
    return {k: summarize(v) for k, v in groups.items()}


def safety_critical(results: list[Result]) -> Summary:
    return summarize([r for r in results if r.safety_critical])
