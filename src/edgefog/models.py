"""Core data model: compute tiers, workloads and scenarios."""
from __future__ import annotations

from dataclasses import dataclass, field

EDGE, FOG, CLOUD = "edge", "fog", "cloud"
TIERS = (EDGE, FOG, CLOUD)

# Where the data a workload needs actually lives decides which tiers may run it.
#   device     - produced by one device; any tier can run it
#   hospital   - aggregated from many devices in one hospital; fog or cloud
#   population - multi-site / public-health data; only the cloud holds it
SCOPE_TIERS = {
    "device": (EDGE, FOG, CLOUD),
    "hospital": (FOG, CLOUD),
    "population": (CLOUD,),
}


@dataclass(frozen=True)
class Tier:
    name: str
    gflops: float  # per worker
    workers: int  # fog/cloud: per site. edge: ignored (one device per source)
    rtt_ms: float  # device <-> tier round trip, propagation only
    jitter_ms: float  # mean extra one-way delay (exponential)
    link_mbps: float  # shared hospital uplink to this tier (FIFO serialised)
    usd_per_gflop: float
    usd_per_gb: float  # transfer price
    off_premises: bool  # raw data leaves the hospital


@dataclass(frozen=True)
class Workload:
    key: str
    title: str
    section: str  # chapter section the application comes from
    input_kb: float
    output_kb: float
    gflop: float  # per task
    rate_hz: float  # per source
    sources: int
    deadline_ms: float
    data_scope: str
    chapter_tier: str  # tier the chapter assigns this application to
    safety_critical: bool
    edge_gflops: float = 5.0  # compute of the device class that produces the data

    def allowed_tiers(self) -> tuple[str, ...]:
        return SCOPE_TIERS[self.data_scope]


@dataclass(frozen=True)
class Scenario:
    name: str
    duration_s: float
    seed: int
    tiers: dict[str, Tier]
    workloads: tuple[Workload, ...]
    # tier -> [(start_s, end_s)] windows where the hospital's link to that tier is down
    outages: dict[str, tuple[tuple[float, float], ...]] = field(default_factory=dict)
