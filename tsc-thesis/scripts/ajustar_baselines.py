#!/usr/bin/env python3
"""Ajusta Max-Pressure y Webster usando solo demandas de entrenamiento.

Un baseline mal ajustado infla la ventaja del agente, así que cada uno recibe la
misma oportunidad de buscar su mejor configuración. Las demandas de evaluación
no se tocan aquí: de lo contrario el baseline quedaría ajustado a ellas y el
agente no.

Webster mide los flujos con la réplica t00 y los candidatos se comparan en las
réplicas t01 en adelante, para no medir el plan sobre la misma demanda que lo creó.

    python scripts/ajustar_baselines.py --scenario scenarios/eje_comunal --profile punta_tarde
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import statistics
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from build_webster import SENTIDO_POR_PERFIL, armar_plan  # noqa: E402
from tsc.controllers import GreedyQueueController, MaxPressureController, WebsterController  # noqa: E402
from tsc.demand import rutas_entrenamiento  # noqa: E402
from tsc.runner import measure_phase_flows, run_episode  # noqa: E402

# Histéresis en la escala de cada medida: la presión suma las diferencias de todos
# los movimientos de la fase, de ahí que los valores sean mayores que 1.
GRILLA_MP = {"densidad": [0.05, 0.5, 1.0, 2.0], "vehiculos": [0.0, 2.0, 5.0, 10.0],
             "cola": [0.0, 2.0, 5.0, 10.0]}
GRILLA_CICLO = [60.0, 90.0, 120.0, 150.0]
GRILLA_COORDINACION = [("ninguna", 1.0, False), ("avenida", 1.0, False), ("avenida", 1.0, True),
                       ("avenida", 0.5, False), ("avenida", 0.5, True), ("avenida", 0.75, True)]


def _correr(trabajo: dict) -> dict:
    """Una corrida; se ejecuta en un proceso propio (libsumo: una simulación por proceso)."""
    with open(os.path.join(trabajo["scenario"], "tls_eje.json"), encoding="utf-8") as f:
        eje = json.load(f)["eje"]
    if trabajo["tipo"] == "maxpressure":
        ctrl = MaxPressureController(medida=trabajo["medida"], switch_penalty=trabajo["penalizacion"])
        ctrl.tls_ids = eje
    else:
        ctrl = WebsterController(trabajo["plan"])
    r = run_episode(ctrl, os.path.join(trabajo["scenario"], "net.net.xml"), trabajo["rutas"],
                    seed=trabajo["semilla"], end=trabajo["end"])
    return {"config": trabajo["config"], "tipo": trabajo["tipo"], "semilla": trabajo["semilla"],
            "delay_all_mean": r["delay_all_mean"], "waiting_time_p95": r["waiting_time_p95"],
            "vehicles_finished": r["vehicles_finished"], "pendientes": r["vehicles_pending_end"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--replicas", type=int, default=3, help="demandas de entrenamiento por candidato")
    ap.add_argument("--end", type=int, default=3600)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--solo", default="maxpressure,webster")
    ap.add_argument("--flujos", default="fijo", choices=["fijo", "voraz"],
                    help="controlador de la corrida que mide los flujos de Webster")
    args = ap.parse_args()

    pool = rutas_entrenamiento(args.scenario, args.profile)
    if len(pool) < args.replicas + 1:
        sys.exit(f"faltan demandas de entrenamiento para {args.profile}: hay {len(pool)}")
    rutas = pool[1: args.replicas + 1]
    net = os.path.join(args.scenario, "net.net.xml")
    trabajos = []

    if "maxpressure" in args.solo:
        for medida, penalizaciones in GRILLA_MP.items():
            for pen in penalizaciones:
                for k, rou in enumerate(rutas):
                    trabajos.append({"tipo": "maxpressure", "config": f"{medida}|{pen}", "medida": medida,
                                     "penalizacion": pen, "rutas": rou, "semilla": 100 + k,
                                     "scenario": args.scenario, "end": args.end})

    carpeta = tempfile.mkdtemp(prefix="webster_")
    if "webster" in args.solo:
        print(f"Midiendo flujos con {pool[0]} (calibración: {args.flujos}) …", flush=True)
        calibrador = None
        if args.flujos == "voraz":
            calibrador = GreedyQueueController()
            with open(os.path.join(args.scenario, "tls_eje.json"), encoding="utf-8") as f:
                calibrador.tls_ids = json.load(f)["eje"]
        flujos = measure_phase_flows(net, pool[0], seed=0, end=args.end, controller=calibrador)
        sentido = SENTIDO_POR_PERFIL.get(args.profile, "ninguno")
        for ciclo, (coord, q, onda) in itertools.product(GRILLA_CICLO, GRILLA_COORDINACION):
            nombre = f"ciclo{ciclo:.0f}|{coord}|q{q}|{'onda' if onda else 'sin_onda'}"
            planes, _ = armar_plan(flujos, args.scenario, net, sentido=sentido if onda else "ninguno",
                                   coordinar=coord == "avenida", max_cycle=ciclo, cuantil=q)
            ruta_plan = os.path.join(carpeta, nombre.replace("|", "_") + ".json")
            with open(ruta_plan, "w", encoding="utf-8") as f:
                json.dump(planes, f)
            for k, rou in enumerate(rutas):
                trabajos.append({"tipo": "webster", "config": nombre, "plan": ruta_plan, "rutas": rou,
                                 "semilla": 100 + k, "scenario": args.scenario, "end": args.end})

    print(f"{len(trabajos)} corridas con {args.workers} procesos", flush=True)
    filas = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, fila in enumerate(ex.map(_correr, trabajos), 1):
            filas.append(fila)
            print(f"  [{i}/{len(trabajos)}] {fila['tipo']} {fila['config']} "
                  f"delayAll={fila['delay_all_mean']:.1f}", flush=True)

    resumen = {}
    for f in filas:
        resumen.setdefault((f["tipo"], f["config"]), []).append(f)
    orden = sorted(resumen.items(), key=lambda kv: (kv[0][0], statistics.fmean(x["delay_all_mean"] for x in kv[1])))
    print(f"\n{'tipo':12s}{'configuración':38s}{'demora':>8s}{'p95':>8s}{'fin':>7s}")
    for (tipo, config), xs in orden:
        print(f"{tipo:12s}{config:38s}{statistics.fmean(x['delay_all_mean'] for x in xs):8.1f}"
              f"{statistics.fmean(x['waiting_time_p95'] for x in xs):8.1f}"
              f"{statistics.fmean(x['vehicles_finished'] for x in xs):7.0f}")

    salida = os.path.join("results", f"ajuste_{os.path.basename(args.scenario)}_{args.profile}"
                                     f"{'_flujos_voraz' if args.flujos == 'voraz' else ''}.json")
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(filas, f, indent=1)
    print(f"\nOK  {salida}")


if __name__ == "__main__":
    main()
