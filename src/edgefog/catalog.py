"""Default tiers and the chapter's applications as workloads.

The chapter gives no numbers. Every figure below is an engineering assumption chosen to be
plausible for 2025-era hardware and networks; see docs/assumptions.md for the reasoning.
"""
from __future__ import annotations

from .models import CLOUD, EDGE, FOG, Scenario, Tier, Workload

DEFAULT_TIERS = {
    # Per-device compute; capacity is overridden per device class by Workload.edge_gflops.
    EDGE: Tier(EDGE, gflops=5.0, workers=1, rtt_ms=0.0, jitter_ms=0.0, link_mbps=float("inf"),
               usd_per_gflop=2e-7, usd_per_gb=0.0, off_premises=False),
    # Hospital fog node reached over private 5G / hospital LAN.
    FOG: Tier(FOG, gflops=2000.0, workers=4, rtt_ms=4.0, jitter_ms=0.5, link_mbps=1000.0,
              usd_per_gflop=4e-6, usd_per_gb=0.0, off_premises=False),
    # Public cloud region reached over the hospital's WAN uplink.
    CLOUD: Tier(CLOUD, gflops=20000.0, workers=64, rtt_ms=60.0, jitter_ms=8.0, link_mbps=100.0,
                usd_per_gflop=1e-5, usd_per_gb=0.02, off_premises=True),
}

# Batch jobs (training, genomics, outbreak) carry only a job manifest on the real-time link;
# their datasets are assumed pre-staged at fog and cloud by a separate bulk channel.
WORKLOADS = (
    # --- 9.3.1 cloud applications ---
    Workload("virtual_doctor", "AI chatbot / virtual doctor", "9.3.1-1",
             input_kb=4, output_kb=4, gflop=100, rate_hz=0.5, sources=20, deadline_ms=5000,
             data_scope="device", chapter_tier=CLOUD, safety_critical=False, edge_gflops=20),
    Workload("ehr_analytics", "Cloud EMR history analysis", "9.3.1-2",
             input_kb=2000, output_kb=50, gflop=50, rate_hz=0.2, sources=5, deadline_ms=30000,
             data_scope="hospital", chapter_tier=CLOUD, safety_critical=False),
    Workload("outbreak_prediction", "Disease outbreak prediction", "9.3.1-3",
             input_kb=10, output_kb=100, gflop=50000, rate_hz=1 / 60, sources=1, deadline_ms=600000,
             data_scope="population", chapter_tier=CLOUD, safety_critical=False),
    Workload("genomics", "Genomic analysis for precision medicine", "9.3.1-4",
             input_kb=10, output_kb=500, gflop=100000, rate_hz=1 / 60, sources=2, deadline_ms=900000,
             data_scope="hospital", chapter_tier=CLOUD, safety_critical=False),
    Workload("model_training", "Diagnostic model (re)training", "9.3-1",
             input_kb=10, output_kb=200000, gflop=1e7, rate_hz=1 / 3600, sources=1, deadline_ms=3600000,
             data_scope="hospital", chapter_tier=CLOUD, safety_critical=False),
    # --- 9.4 / 9.4.1 edge applications ---
    Workload("rpm_ecg", "Remote patient monitoring (ECG/SpO2/BP anomaly)", "9.4.1-1",
             input_kb=8, output_kb=0.5, gflop=0.02, rate_hz=1, sources=200, deadline_ms=1000,
             data_scope="device", chapter_tier=EDGE, safety_critical=True, edge_gflops=5),
    Workload("stroke_seizure", "Real-time stroke / seizure detection", "9.4.1-2",
             input_kb=32, output_kb=0.5, gflop=0.2, rate_hz=2, sources=50, deadline_ms=500,
             data_scope="device", chapter_tier=EDGE, safety_critical=True, edge_gflops=5),
    Workload("infusion_pump", "Smart infusion pump dose control", "9.4b",
             input_kb=1, output_kb=0.2, gflop=0.005, rate_hz=1, sources=40, deadline_ms=200,
             data_scope="device", chapter_tier=EDGE, safety_critical=True, edge_gflops=5),
    Workload("prosthesis", "AI prosthesis motion adaptation", "9.4.1-3",
             input_kb=2, output_kb=0.2, gflop=0.01, rate_hz=100, sources=10, deadline_ms=20,
             data_scope="device", chapter_tier=EDGE, safety_critical=True, edge_gflops=10),
    # --- 9.5.1 fog applications ---
    Workload("icu_monitoring", "Real-time ICU early warning", "9.5.1",
             input_kb=64, output_kb=1, gflop=1, rate_hz=1, sources=30, deadline_ms=2000,
             data_scope="hospital", chapter_tier=FOG, safety_critical=True),
    Workload("er_triage", "AI-assisted ER triage", "9.5.1",
             input_kb=200, output_kb=2, gflop=5, rate_hz=0.1, sources=10, deadline_ms=3000,
             data_scope="hospital", chapter_tier=FOG, safety_critical=False),
    Workload("surgery_vision", "5G fog robotic-surgery vision assist", "9.5.1",
             input_kb=300, output_kb=5, gflop=20, rate_hz=30, sources=2, deadline_ms=50,
             data_scope="device", chapter_tier=FOG, safety_critical=True, edge_gflops=200),
    Workload("haptic_feedback", "AI haptic feedback for tele-surgery", "9.5.1",
             input_kb=0.5, output_kb=0.5, gflop=0.05, rate_hz=500, sources=2, deadline_ms=10,
             data_scope="device", chapter_tier=FOG, safety_critical=True, edge_gflops=200),
    Workload("vr_cbt", "VR cognitive behavioural therapy", "9.5.1",
             input_kb=100, output_kb=50, gflop=2, rate_hz=10, sources=5, deadline_ms=100,
             data_scope="device", chapter_tier=FOG, safety_critical=False, edge_gflops=30),
)

# A small device-scope task used to compare the tiers in isolation (Table 9.1 probe).
REFERENCE_TASK = Workload("reference", "Reference inference (8 KB, 0.02 GFLOP)", "9.6",
                          input_kb=8, output_kb=0.5, gflop=0.02, rate_hz=1, sources=20,
                          deadline_ms=1000, data_scope="device", chapter_tier=EDGE,
                          safety_critical=False, edge_gflops=5)


def baseline(duration_s: float = 60.0, seed: int = 7) -> Scenario:
    return Scenario("baseline", duration_s, seed, dict(DEFAULT_TIERS), WORKLOADS)


def cloud_outage(duration_s: float = 60.0, seed: int = 7,
                 window: tuple[float, float] = (20.0, 35.0)) -> Scenario:
    return Scenario("cloud-outage", duration_s, seed, dict(DEFAULT_TIERS), WORKLOADS,
                    outages={CLOUD: (window,)})
