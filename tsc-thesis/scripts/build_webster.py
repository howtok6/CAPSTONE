#!/usr/bin/env python3
"""Calcula el plan de Webster para un escenario y lo guarda como JSON.

    python scripts/build_webster.py --scenario scenarios/grid4x4
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from tsc.controllers.webster import webster_plan
from tsc.runner import measure_phase_flows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--net", default=None)
    ap.add_argument("--routes", default=None)
    ap.add_argument("--end", type=int, default=3600)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    net = args.net or os.path.join(args.scenario, "net.net.xml")
    rou = args.routes or os.path.join(args.scenario, "routes.rou.xml")
    out = args.out or os.path.join(args.scenario, "webster_plan.json")

    print("Corrida de calibración (tiempo fijo) para medir flujos por fase…")
    flows = measure_phase_flows(net, rou, seed=args.seed, end=args.end)

    plans = {}
    for tls_id, phase_flows in flows.items():
        pf = {int(k): v for k, v in phase_flows.items()}
        plan = webster_plan(pf)
        plans[tls_id] = {
            "cycle": plan["cycle"],
            "Y": plan["Y"],
            "greens": {str(k): round(v, 1) for k, v in plan["greens"].items()},
            "measured_flows": {str(k): round(v, 1) for k, v in pf.items()},
        }

    with open(out, "w") as fh:
        json.dump(plans, fh, indent=2)

    cycles = [p["cycle"] for p in plans.values()]
    print(f"OK  {len(plans)} intersecciones → {out}")
    print(f"    ciclo: min={min(cycles):.0f}s  medio={sum(cycles)/len(cycles):.0f}s  max={max(cycles):.0f}s")


if __name__ == "__main__":
    main()
