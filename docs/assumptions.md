# Assumptions

Chapter 9 gives no numbers. Every value below is an engineering assumption, chosen to be plausible
for 2025-era hardware. Change them in `src/edgefog/catalog.py`, then rerun `edgefog report`.

## Tiers

| Tier | Compute per worker | Workers | RTT to devices | Link | Price | Data off premises |
|---|---|---|---|---|---|---|
| edge | per device class: 5 GFLOP/s wearable/pump, 10 prosthesis, 20 phone, 30 VR headset, 200 surgical console | 1 per source device | 0 | none | $2e-7/GFLOP (energy) | no |
| fog | 2,000 GFLOP/s (one GPU-class server) | 4 | 4 ms + exp(0.5 ms) jitter each way | 1 Gbit/s private 5G / LAN, FIFO-shared | $4e-6/GFLOP | no |
| cloud | 20,000 GFLOP/s | 64 | 60 ms + exp(8 ms) jitter each way | 100 Mbit/s hospital WAN uplink, FIFO-shared | $1e-5/GFLOP + $0.02/GB | yes |

The cost ordering (edge < fog < cloud) comes straight from these unit prices, so it reproduces
Table 9.1 by construction. It is **not** an independent finding. The latency ordering also follows
from the assumed RTTs. What the simulation adds is queueing and contention: which workloads still
meet their deadlines once shared links and servers are loaded.

## Workloads

Each application in Sections 9.3–9.5 has an input size, an output size, GFLOP per task, an
arrival rate, a source count, a deadline and a data scope (see `catalog.WORKLOADS`).
The data scope decides where a task can run:

* `device`: any tier.
* `hospital`: fog or cloud. The task needs data aggregated from many devices.
* `population`: cloud only (multi-site and public-health data).

Batch jobs (training, genomics, outbreak prediction) send only a small job manifest. Their
datasets are assumed to be pre-staged at fog and cloud over a separate bulk channel. Without this,
a single 1 GB upload would block the 100 Mbit/s WAN for 80 s.

## Simplifications

* Tasks are dispatched in generation order. Servers are FIFO and taken earliest-free first.
  There is no preemption and no priority. This is why long batch jobs on fog delay real-time work
  under `all-fog`.
* Only the uplink is contended. Replies have no contention.
* During an outage, sends and replies wait until the window ends. Nothing is dropped.
* "Security" is approximated by the bytes of raw patient data that leave the hospital. Attack
  surface, patching, encryption and insider risk are not modelled.
* Periodic arrivals with ±5 % jitter. No bursts or correlated emergencies.
