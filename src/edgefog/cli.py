"""Command line: ``python -m edgefog {run,compare,report}``."""
from __future__ import annotations

import argparse
from pathlib import Path

from . import catalog
from .metrics import by_workload, safety_critical, summarize
from .report import build_report, policy_table, run_all, workload_table
from .sim import all_policies, simulate


def _scenario(args):
    if args.cloud_outage:
        start, end = (float(x) for x in args.cloud_outage.split(":"))
        return catalog.cloud_outage(args.duration, args.seed, (start, end))
    return catalog.baseline(args.duration, args.seed)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="edgefog", description="SIMULATION ONLY edge/fog/cloud placement simulator")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("run", "compare", "report"):
        s = sub.add_parser(name)
        s.add_argument("--duration", type=float, default=60.0, help="simulated seconds")
        s.add_argument("--seed", type=int, default=7)
        if name != "report":
            s.add_argument("--cloud-outage", metavar="START:END", help="cloud link down, seconds")
    sub.choices["run"].add_argument("--policy", default="adaptive", choices=[x.name for x in all_policies()])
    sub.choices["report"].add_argument("--out", type=Path, default=Path("docs/results.md"))
    sub.choices["report"].add_argument("--no-chart", action="store_true")
    args = p.parse_args(argv)

    if args.cmd == "run":
        policy = next(x for x in all_policies() if x.name == args.policy)
        res = simulate(_scenario(args), policy)
        print("| Application | Tasks | p50 ms | p99 ms | Miss | Cost USD | Tiers |\n|---|---:|---:|---:|---:|---:|---|")
        for key, s in by_workload(res).items():
            print(f"| {key} | {s.n:,} | {s.p50_ms:,.1f} | {s.p99_ms:,.1f} | {s.miss_rate:.1%} "
                  f"| {s.cost_usd:.4f} | {s.tier_mix} |")
        a, sc = summarize(res), safety_critical(res)
        print(f"\nall: miss {a.miss_rate:.2%}, cost ${a.cost_usd:.2f}, off-premises {a.off_premises_mb:,.1f} MB; "
              f"safety-critical miss {sc.miss_rate:.2%}")
    elif args.cmd == "compare":
        runs = run_all(_scenario(args))
        print(policy_table(runs), "", workload_table(runs), sep="\n")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        chart = None if args.no_chart else args.out.with_suffix(".png")
        args.out.write_text(build_report(args.duration, args.seed, chart), encoding="utf-8")
        print(f"wrote {args.out}" + (f" and {chart}" if chart else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
