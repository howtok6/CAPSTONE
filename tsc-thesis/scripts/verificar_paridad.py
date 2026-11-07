#!/usr/bin/env python3
"""Comprueba que los dos arneses de medición dan el mismo resultado.

El agente corre sobre sumo-rl (`eval_rl.py`) y los controladores clásicos sobre
`tsc.runner`. Si un arnés favoreciera a uno de los lados, la mejora del agente
sería un artefacto. Aquí la misma regla (voraz por cola) corre en ambos, sobre las
mismas demandas y semillas: las demoras deben coincidir dentro del ruido.

    python scripts/verificar_paridad.py --scenario scenarios/eje_comunal --profile punta_tarde
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

if __name__ == "__main__":
    os.environ.setdefault("LIBSUMO_AS_TRACI", "1")

from eval_rl import evaluate  # noqa: E402
from tsc.controllers import GreedyQueueController  # noqa: E402
from tsc.demand import ruta_evaluacion  # noqa: E402
from tsc.rl_env import controlled_tls  # noqa: E402
from tsc.runner import run_episode  # noqa: E402


def voraz(inner, agentes) -> dict:
    """La misma regla de GreedyQueueController, sobre el entorno de sumo-rl."""
    acciones = {}
    for a in agentes:
        ts = inner.traffic_signals[a]
        mejor, valor = ts.green_phase, float("-inf")
        for i, (entrada, _) in enumerate(ts.observation_fn._por_fase):
            v = sum(ts.sumo.lane.getLastStepHaltingNumber(p) for p in entrada)
            if i == ts.green_phase:
                v += 0.5
            if v > valor:
                mejor, valor = i, v
        acciones[a] = mejor
    return acciones


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--seconds", type=int, default=3600)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    net = os.path.join(args.scenario, "net.net.xml")
    eje = controlled_tls(args.scenario, "auto")
    filas = []
    for k in range(args.seeds):
        rou = ruta_evaluacion(args.scenario, args.profile, k, None)
        ctrl = GreedyQueueController()
        ctrl.tls_ids = eje
        a = run_episode(ctrl, net, rou, seed=k, end=args.seconds)
        b = evaluate(voraz, net, rou, k, args.seconds, 300, tls_ids=eje, obs_kind="fase")
        filas.append({"seed": k, "runner": a["delay_all_mean"], "sumo_rl": b["delay_all_mean"],
                      "fin_runner": a["vehicles_finished"], "fin_sumo_rl": b["vehicles_finished"],
                      "cambios_runner": a["phase_switches"], "cambios_sumo_rl": b["phase_switches"]})
        print(filas[-1], flush=True)
    r, s = [f["runner"] for f in filas], [f["sumo_rl"] for f in filas]
    dif = (statistics.fmean(s) - statistics.fmean(r)) / statistics.fmean(r) * 100
    print(f"\nDemora media: runner {statistics.fmean(r):.1f} s · sumo-rl {statistics.fmean(s):.1f} s "
          f"· diferencia {dif:+.1f} %")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(filas, f, indent=1)


if __name__ == "__main__":
    main()
