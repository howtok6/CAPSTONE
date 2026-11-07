#!/usr/bin/env python3
"""Evalúa todos los controladores clásicos con múltiples semillas.

Las semillas son *idénticas* entre controladores, de modo que la comparación
sea pareada y el test estadístico gane potencia.

    python scripts/run_baselines.py --scenario scenarios/grid4x4 --seeds 10
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from tsc.controllers import (
    FixedTimeController,
    GreedyQueueController,
    MaxPressureController,
    WebsterController,
)
from tsc.controllers.base import PhaseSwitchingController
from tsc.demand import ruta_evaluacion
from tsc.runner import run_episode


def build_controllers(scenario: str, which: list, profile: str | None = None) -> list:
    available = {
        "fixed": lambda: FixedTimeController(),
        "greedy": lambda: GreedyQueueController(),
        "maxpressure": lambda: MaxPressureController(),
    }
    # Plan de Webster del perfil (build_webster.py --profile); si no hay, el general
    plan = os.path.join(scenario, f"webster_plan_{profile}.json") if profile else ""
    if not os.path.exists(plan):
        plan = os.path.join(scenario, "webster_plan.json")
    if os.path.exists(plan):
        print(f"  Webster: {plan}")
        available["webster"] = lambda: WebsterController(plan)
    out = []
    for name in which:
        if name not in available:
            print(f"  [aviso] controlador '{name}' no disponible, se omite")
            continue
        out.append(available[name])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--profile", default=None, help="Nombre del perfil de demanda (valle, punta_manana, punta_tarde, sobresaturado)")
    ap.add_argument("--routes", default=None, help="Ruta directa al archivo de rutas .rou.xml")
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--end", type=int, default=3600)
    ap.add_argument("--warmup", type=int, default=300)
    ap.add_argument(
        "--controllers",
        default="fixed,webster,greedy,maxpressure",
        help="lista separada por comas",
    )
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    net = os.path.join(args.scenario, "net.net.xml")
    if args.routes:
        rou = args.routes
    elif args.profile:
        rou = os.path.join(args.scenario, "demand", f"routes_{args.profile}.rou.xml")
        if not os.path.exists(rou):
            rou = os.path.join(args.scenario, f"routes_{args.profile}.rou.xml")
    else:
        rou = os.path.join(args.scenario, "routes.rou.xml")

    if not os.path.exists(rou) and ruta_evaluacion(args.scenario, args.profile, 0, rou) == rou:
        sys.exit(f"Error: No se encontró el archivo de rutas {rou}")

    factories = build_controllers(args.scenario, args.controllers.split(","), args.profile)

    eje = None
    ruta_eje = os.path.join(args.scenario, "tls_eje.json")
    if os.path.exists(ruta_eje):
        with open(ruta_eje, encoding="utf-8") as f:
            eje = json.load(f)["eje"]
        print(f"  Adaptativos: {len(eje)} semáforos del eje; el resto sigue su programa")

    rows = []
    for factory in factories:
        for seed in range(args.seeds):
            ctrl = factory()
            if eje and isinstance(ctrl, PhaseSwitchingController):
                ctrl.tls_ids = eje  # mismo alcance que el agente
            rou_k = rou if args.routes else ruta_evaluacion(args.scenario, args.profile, seed, rou)
            r = run_episode(ctrl, net, rou_k, seed=seed, end=args.end, warmup=args.warmup)
            r["rutas"] = rou_k
            rows.append(r)
            print(
                f"  {r['controller']:12s} seed={seed:2d}  "
                f"timeLoss={r.get('time_loss_mean', float('nan')):6.2f}  "
                f"queue={r.get('queue_mean', float('nan')):6.2f}"
            )

    tag = f"_{args.profile}" if args.profile else ""
    out = args.out or os.path.join("results", f"{os.path.basename(args.scenario)}{tag}_baselines.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(rows, fh, indent=2)
    print(f"\nOK  {len(rows)} corridas -> {out}")
    print("    Analiza con:  python scripts/compare.py --results", out)


if __name__ == "__main__":
    main()
