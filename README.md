# Smart Healthcare Edge / Fog / Cloud Placement Simulator

> **SIMULATION ONLY. NOT FOR CLINICAL OR PATIENT USE.** No real devices, networks or patient
> data are involved. All parameters are assumptions (`docs/assumptions.md`).

A research prototype based on Chapter 9 of *Surgical Robots in Smart Hospitals*, "AI-fused metaverse
integration in smart healthcare: 9 applications deployed on fog, edge and cloud computing".
The chapter is qualitative. Its central claim is Table 9.1 (latency, cost and security of cloud,
edge and fog) together with a tier assignment for each application. This project turns that claim
into a testable model:

* 14 workloads taken from Sections 9.3–9.5, for example remote patient monitoring, stroke/seizure
  detection, smart infusion pumps, prostheses, ICU early warning, ER triage, 5G fog robotic-surgery
  vision, tele-surgery haptics, VR CBT, virtual doctor, EHR analytics, outbreak prediction,
  genomics and model training.
* Three tiers with compute, shared uplinks, propagation and jitter, prices, link outages and data
  locality.
* Five placement policies: `all-edge`, `all-fog`, `all-cloud`, `chapter` (the chapter's mapping)
  and `adaptive` (deadline-aware, cheapest feasible tier, fog admission control for long batch jobs).

## Findings (default assumptions, 60 s, seed 7; full tables in `docs/results.md`)

* **Latency and cost** in isolation follow Table 9.1: edge < fog < cloud. This is mostly by
  construction (see assumptions).
* **Security**: the chapter rates fog "very high", above edge. In this model, edge and fog both
  keep raw data on premises (0 KB/task leaves the hospital). The simulation does not support
  ranking fog above edge.
* **Availability** is missing from Table 9.1, yet it separates the tiers most clearly. During a
  15 s link outage, edge misses no deadlines, while fog and cloud each miss about 24 %.
* **No single tier works.** `all-cloud` misses about 100 % of safety-critical deadlines (surgery,
  haptics, prosthesis, pumps). `all-fog` misses about 24 %, because training and genomics jobs
  occupy the shared fog servers. `all-edge` cannot run surgery vision.
* The **chapter's mapping** is nearly right (0.02 % safety misses). The `adaptive` policy reaches
  0 % and keeps 0 % through the cloud outage. It disagrees with the chapter in three places: it
  runs tele-surgery haptics and VR CBT on the device, and the virtual doctor and EHR analytics on
  fog, because those options are cheaper and still meet the deadlines.

## Setup and use (Windows)

```bash
cd D:\robot\smart-healthcare-edge-fog-cloud
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e ".[test,plot]"
.venv\Scripts\python -m pytest
.venv\Scripts\python -m edgefog run --policy adaptive            # per-application table
.venv\Scripts\python -m edgefog compare --cloud-outage 20:35     # all policies
.venv\Scripts\python -m edgefog report                           # docs/results.md + docs/results.png
```

## Layout

| Path | Purpose |
|---|---|
| `src/edgefog/models.py` | Tier, Workload, Scenario, data scopes |
| `src/edgefog/catalog.py` | Default tiers and the chapter's applications |
| `src/edgefog/sim.py` | Trace-driven simulator and placement policies |
| `src/edgefog/metrics.py` | Percentiles, miss rate, cost, off-premises bytes |
| `src/edgefog/report.py` | Markdown report, Table 9.1 check and chart |
