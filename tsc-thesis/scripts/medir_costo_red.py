#!/usr/bin/env python3
"""Mide cuánto cuesta simular una red grande antes de planificar el entrenamiento.

Con demanda aleatoria (randomTrips, NO es demanda de tesis) corre una hora:
  1. SUMO solo, sin control externo           -> costo base de la simulación
  2. libsumo leyendo cada --delta s, para todos los semáforos, colas y
     vehículos de sus pistas controladas      -> costo aproximado de observar
     a todos los agentes como lo haría sumo-rl (sin la red neuronal)

Uso:
    python scripts/medir_costo_red.py --scenario scenarios/las_condes_providencia --veh-h 10000
Escribe <scenario>/costo_red.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
try:
    import tsc.sumo_env  # noqa: F401,E402 (fija SUMO_HOME)
except ImportError:
    import sumo
    os.environ.setdefault("SUMO_HOME", sumo.SUMO_HOME)
import sumolib  # noqa: E402


def estadisticas(texto: str) -> dict:
    claves = {"Inserted": "insertados", "Running": "en_red_al_final", "Teleports": "teletransportes",
              "TimeLoss": "time_loss_s", "WaitingTime": "espera_s", "Duration": "duracion_viaje_s"}
    r = {}
    for k, v in claves.items():
        m = re.findall(rf"\b{k}: ([\d.]+)", texto)
        if m:
            r[v] = float(m[-1])
    return r


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--veh-h", type=int, default=10000)
    ap.add_argument("--fin", type=int, default=3600)
    ap.add_argument("--delta", type=int, default=5, help="s entre decisiones del agente")
    a = ap.parse_args()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    net = os.path.join(a.scenario, "net.net.xml")
    rutas = os.path.join(a.scenario, f"prueba_{a.veh_h}.rou.xml")
    if not os.path.exists(rutas):
        print("Generando demanda aleatoria de prueba…", flush=True)
        subprocess.run([sys.executable, os.path.join(os.environ["SUMO_HOME"], "tools", "randomTrips.py"),
                        "-n", net, "-o", rutas.replace(".rou.xml", ".trips.xml"), "-r", rutas,
                        "--begin", "0", "--end", str(a.fin), "--period", str(3600 / a.veh_h),
                        "--seed", "1", "--fringe-factor", "10", "--min-distance", "1000", "--validate"],
                       check=True, stdout=subprocess.DEVNULL)
    base = ["-n", net, "-r", rutas, "--begin", "0", "--end", str(a.fin), "--no-step-log", "true",
            "--time-to-teleport", "300", "--no-warnings", "true", "--duration-log.statistics", "true"]

    print("1. SUMO solo…", flush=True)
    t0 = time.perf_counter()
    p = subprocess.run([sumolib.checkBinary("sumo"), *base], capture_output=True, text=True)
    t_sumo = time.perf_counter() - t0
    est = estadisticas(p.stdout + p.stderr)

    print("2. libsumo observando todos los semáforos…", flush=True)
    import libsumo as ls
    ls.start(["sumo", *base])
    tls = ls.trafficlight.getIDList()
    pistas = {t: sorted(set(ls.trafficlight.getControlledLanes(t))) for t in tls}
    t0, lecturas = time.perf_counter(), 0
    while ls.simulation.getTime() < a.fin:
        ls.simulation.step()
        if int(ls.simulation.getTime()) % a.delta == 0:
            for t in tls:
                ls.trafficlight.getPhase(t)
                for ln in pistas[t]:
                    ls.lane.getLastStepHaltingNumber(ln)
                    ls.lane.getLastStepVehicleNumber(ln)
                    lecturas += 2
    t_obs = time.perf_counter() - t0
    ls.close()

    r = {"veh_h": a.veh_h, "horas_simuladas": a.fin / 3600, "semaforos": len(tls),
         "pistas_controladas": sum(len(v) for v in pistas.values()),
         "s_sumo_solo": round(t_sumo, 1), "s_libsumo_con_observacion": round(t_obs, 1),
         "lecturas_libsumo": lecturas, "estadisticas_sumo": est}
    json.dump(r, open(os.path.join(a.scenario, f"costo_red_{a.veh_h}.json"), "w"), indent=1)
    print(json.dumps(r, indent=1))


if __name__ == "__main__":
    main()
