import pytest

from edgefog import catalog
from edgefog.metrics import by_workload, percentile, safety_critical, summarize
from edgefog.models import CLOUD, EDGE, FOG, Scenario
from edgefog.report import probe_tiers
from edgefog.sim import Adaptive, ChapterMapping, FixedTier, simulate, transfer_ms

DUR = 20.0  # short runs keep the suite fast; the report uses 60 s


@pytest.fixture(scope="module")
def base_runs():
    sc = catalog.baseline(DUR, seed=3)
    return {p.name: simulate(sc, p) for p in
            (FixedTier(EDGE), FixedTier(FOG), FixedTier(CLOUD), ChapterMapping(), Adaptive())}


def test_transfer_ms():
    assert transfer_ms(125, 1000) == pytest.approx(1.0)  # 1 Mbit over 1 Gbit/s
    assert transfer_ms(10, float("inf")) == 0.0


def test_percentile_nearest_rank():
    assert percentile([1, 2, 3, 4], 50) == 2
    assert percentile([1, 2, 3, 4], 100) == 4


def test_deterministic_for_seed():
    sc = catalog.baseline(5.0, seed=11)
    a = [r.done_ms for r in simulate(sc, Adaptive())]
    b = [r.done_ms for r in simulate(sc, Adaptive())]
    assert a == b


def test_data_scope_respected(base_runs):
    scope = {w.key: w.allowed_tiers() for w in catalog.WORKLOADS}
    for res in base_runs.values():
        assert all(r.tier in scope[r.workload] for r in res)


def test_isolated_latency_ordering_matches_table_91():
    probe = probe_tiers(DUR, seed=3)
    assert probe[EDGE]["p50"] < probe[FOG]["p50"] < probe[CLOUD]["p50"]


def test_cost_ordering_matches_table_91():
    probe = probe_tiers(DUR, seed=3)
    assert probe[EDGE]["usd_per_1k"] < probe[FOG]["usd_per_1k"] < probe[CLOUD]["usd_per_1k"]


def test_only_cloud_sends_data_off_premises():
    probe = probe_tiers(DUR, seed=3)
    assert probe[EDGE]["off_kb_per_task"] == 0 == probe[FOG]["off_kb_per_task"]
    assert probe[CLOUD]["off_kb_per_task"] > 0


def test_adaptive_meets_all_safety_deadlines(base_runs):
    assert safety_critical(base_runs["adaptive"]).miss_rate == 0.0


def test_cloud_cannot_serve_surgery_loops(base_runs):
    per = by_workload(base_runs["all-cloud"])
    assert per["surgery_vision"].miss_rate > 0.9
    assert per["haptic_feedback"].miss_rate > 0.9


def test_edge_lacks_compute_for_surgery_vision(base_runs):
    assert by_workload(base_runs["all-edge"])["surgery_vision"].miss_rate > 0.9


def test_training_needs_cloud(base_runs):
    assert by_workload(base_runs["all-fog"])["model_training"].miss_rate == 1.0
    assert by_workload(base_runs["adaptive"])["model_training"].tiers == {CLOUD: 1}


def test_adaptive_survives_cloud_outage():
    res = simulate(catalog.cloud_outage(40.0, seed=3, window=(10.0, 25.0)), Adaptive())
    assert safety_critical(res).miss_rate == 0.0


def test_outage_holds_cloud_tasks():
    sc = Scenario("t", 10.0, 1, dict(catalog.DEFAULT_TIERS), (catalog.REFERENCE_TASK,),
                  outages={CLOUD: ((2.0, 6.0),)})
    res = simulate(sc, FixedTier(CLOUD))
    held = [r for r in res if 2000 <= r.gen_ms < 6000]
    assert held and all(r.done_ms >= 6000 for r in held)


def test_summary_counts(base_runs):
    s = summarize(base_runs["adaptive"])
    assert s.n == sum(s.tiers.values()) == len(base_runs["adaptive"])
