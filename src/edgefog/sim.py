"""Trace-driven placement simulator.

Tasks are dispatched in generation order. For each task a policy picks a tier, then the task is
committed against that tier's resources:

* edge  - one device per (workload, source); FIFO on that device.
* fog / cloud - the hospital's uplink to the tier is one FIFO transmitter of ``link_mbps``;
  the tier has ``workers`` identical servers taken earliest-free-first (FIFO multi-server).
  Downlink is not contended. Propagation is rtt/2 each way plus exponential jitter.
* An outage window on a tier's link holds any send or reply that would start inside it until
  the window ends (store-and-forward, nothing is dropped).
"""
from __future__ import annotations

import heapq
import random
from dataclasses import dataclass
from typing import Protocol

from .models import CLOUD, EDGE, FOG, TIERS, Scenario, Workload


def transfer_ms(kb: float, mbps: float) -> float:
    """Serialisation time of ``kb`` kilobytes over a ``mbps`` link, in ms."""
    if mbps == float("inf"):
        return 0.0
    return kb * 8.0 / mbps


@dataclass(frozen=True)
class Task:
    gen_ms: float
    workload: Workload
    source: int


@dataclass(frozen=True)
class Result:
    workload: str
    tier: str
    gen_ms: float
    done_ms: float
    deadline_ms: float
    cost_usd: float
    off_premises_kb: float
    safety_critical: bool

    @property
    def latency_ms(self) -> float:
        return self.done_ms - self.gen_ms

    @property
    def missed(self) -> bool:
        return self.latency_ms > self.deadline_ms


def generate_tasks(scenario: Scenario, rng: random.Random) -> list[Task]:
    """Periodic arrivals per source with a random phase and +-5% period jitter.

    The phase is drawn inside min(period, duration) so every source emits at least once.
    """
    horizon = scenario.duration_s * 1000.0
    tasks: list[Task] = []
    for wl in scenario.workloads:
        period = 1000.0 / wl.rate_hz
        for src in range(wl.sources):
            t = rng.uniform(0.0, min(period, horizon))
            while t < horizon:
                tasks.append(Task(t, wl, src))
                t += period * rng.uniform(0.95, 1.05)
    tasks.sort(key=lambda k: k.gen_ms)
    return tasks


class Policy(Protocol):
    name: str

    def choose(self, task: Task, sim: "Simulator") -> str: ...


class Simulator:
    def __init__(self, scenario: Scenario):
        self.sc = scenario
        self.rng = random.Random(scenario.seed)
        self.device_free: dict[tuple[str, int], float] = {}
        self.link_free = {t: 0.0 for t in (FOG, CLOUD)}
        self.servers = {t: [0.0] * scenario.tiers[t].workers for t in (FOG, CLOUD)}

    # --- resource helpers -------------------------------------------------------------
    def _available(self, tier: str, t_ms: float) -> float:
        for start, end in self.sc.outages.get(tier, ()):
            if start * 1000.0 <= t_ms < end * 1000.0:
                return end * 1000.0
        return t_ms

    def link_up(self, tier: str, t_ms: float) -> bool:
        return self._available(tier, t_ms) == t_ms

    def service_ms(self, tier: str, wl: Workload) -> float:
        gflops = wl.edge_gflops if tier == EDGE else self.sc.tiers[tier].gflops
        return wl.gflop / gflops * 1000.0

    def cost_usd(self, tier: str, wl: Workload) -> float:
        t = self.sc.tiers[tier]
        moved_gb = 0.0 if tier == EDGE else (wl.input_kb + wl.output_kb) / 1e6
        return wl.gflop * t.usd_per_gflop + moved_gb * t.usd_per_gb

    def _timeline(self, tier: str, task: Task, commit: bool) -> float:
        """Completion time of ``task`` on ``tier``. Mutates state only when ``commit``."""
        wl = task.workload
        svc = self.service_ms(tier, wl)
        if tier == EDGE:
            key = (wl.key, task.source)
            start = max(task.gen_ms, self.device_free.get(key, 0.0))
            done = start + svc
            if commit:
                self.device_free[key] = done
            return done

        t = self.sc.tiers[tier]
        if commit:
            jit_up = self.rng.expovariate(1.0 / t.jitter_ms) if t.jitter_ms else 0.0
            jit_down = self.rng.expovariate(1.0 / t.jitter_ms) if t.jitter_ms else 0.0
        else:
            jit_up = jit_down = t.jitter_ms
        send_start = self._available(tier, max(task.gen_ms, self.link_free[tier]))
        send_end = send_start + transfer_ms(wl.input_kb, t.link_mbps)
        arrive = send_end + t.rtt_ms / 2 + jit_up
        free = self.servers[tier][0]  # heap: earliest-free server
        finish = max(arrive, free) + svc
        reply = self._available(tier, finish)
        done = reply + transfer_ms(wl.output_kb, t.link_mbps) + t.rtt_ms / 2 + jit_down
        if commit:
            self.link_free[tier] = send_end
            heapq.heapreplace(self.servers[tier], finish)
        return done

    def estimate_ms(self, tier: str, task: Task) -> float:
        """Expected latency of ``task`` on ``tier`` given current queues (no state change)."""
        return self._timeline(tier, task, commit=False) - task.gen_ms

    # --- run --------------------------------------------------------------------------
    def run(self, policy: Policy) -> list[Result]:
        results = []
        for task in generate_tasks(self.sc, self.rng):
            wl = task.workload
            tier = policy.choose(task, self)
            if tier not in wl.allowed_tiers():
                raise ValueError(f"{policy.name} placed {wl.key} on {tier}; data lives in {wl.allowed_tiers()}")
            done = self._timeline(tier, task, commit=True)
            off = (wl.input_kb + wl.output_kb) if self.sc.tiers[tier].off_premises else 0.0
            results.append(Result(wl.key, tier, task.gen_ms, done, wl.deadline_ms,
                                  self.cost_usd(tier, wl), off, wl.safety_critical))
        return results


# --- policies ---------------------------------------------------------------------------

def _nearest_allowed(wl: Workload, wanted: str) -> str:
    allowed = wl.allowed_tiers()
    if wanted in allowed:
        return wanted
    order = TIERS[TIERS.index(wanted):] + TIERS[:TIERS.index(wanted)][::-1]
    return next(t for t in order if t in allowed)


@dataclass
class FixedTier:
    """Send everything to one tier; tasks whose data is not there go to the nearest tier that holds it."""
    tier: str

    @property
    def name(self) -> str:
        return f"all-{self.tier}"

    def choose(self, task: Task, sim: Simulator) -> str:
        return _nearest_allowed(task.workload, self.tier)


class ChapterMapping:
    """The tier the chapter assigns to each application (sections 9.3-9.5)."""
    name = "chapter"

    def choose(self, task: Task, sim: Simulator) -> str:
        return _nearest_allowed(task.workload, task.workload.chapter_tier)


@dataclass
class Adaptive:
    """Deadline-aware, cost-then-exposure-minimising placement.

    1. Candidates are the tiers that hold the data.
    2. A candidate is feasible if its estimated latency (current queues, mean jitter, link
       state) is within ``margin`` x deadline. Fog additionally refuses tasks whose service
       time exceeds ``fog_admission_ms``: the fog node is a shared real-time resource and long
       batch jobs would block it.
    3. Pick the cheapest feasible tier, then the one keeping data on premises, then the fastest.
       If nothing is feasible, pick the fastest candidate.
    """
    margin: float = 0.8
    fog_admission_ms: float = 1000.0
    name: str = "adaptive"

    def choose(self, task: Task, sim: Simulator) -> str:
        wl = task.workload
        cands = wl.allowed_tiers()
        est = {t: sim.estimate_ms(t, task) for t in cands}
        feasible = [t for t in cands
                    if est[t] <= self.margin * wl.deadline_ms
                    and not (t == FOG and sim.service_ms(FOG, wl) > self.fog_admission_ms)]
        if not feasible:
            return min(cands, key=est.__getitem__)
        return min(feasible, key=lambda t: (sim.cost_usd(t, wl), sim.sc.tiers[t].off_premises, est[t]))


def all_policies() -> list[Policy]:
    return [FixedTier(EDGE), FixedTier(FOG), FixedTier(CLOUD), ChapterMapping(), Adaptive()]


def simulate(scenario: Scenario, policy: Policy) -> list[Result]:
    return Simulator(scenario).run(policy)
