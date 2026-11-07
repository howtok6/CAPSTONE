#!/usr/bin/env python3
"""Cola de cada semáforo del eje a lo largo del tiempo, para un controlador.

Alimenta el diagrama espacio-tiempo (posición en el eje × hora): muestra dónde
y cuándo se forma la congestión con cada controlador. Mide lo mismo en los dos
arneses (tsc.runner para los clásicos y sumo-rl para el agente) leyendo la red
directamente, no lo que cada controlador cree.

    python scripts/medir_colas_eje.py --scenario scenarios/eje_comunal \
        --profile punta_tarde --controller ppo \
        --model models/eje_comunal/ppo_fase_wait_adam_punta_tarde_s1.zip
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

if __name__ == "__main__":
    os.environ.setdefault("LIBSUMO_AS_TRACI", "1")

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np  # noqa: E402

# sumo-rl debe importarse antes que tsc.sumo_env: si libsumo se carga primero,
# el `import traci` de sumo-rl queda sin `traci.start`.
from tsc.rl_env import accion_real, controlled_tls  # noqa: E402, I001
from build_webster import geometria_eje  # noqa: E402
from tsc.demand import ruta_evaluacion  # noqa: E402

CLASICOS = ("fixed", "webster", "maxpressure", "greedy")


class Muestreo:
    """Cada `cada` segundos: detenidos en las pistas de entrada de cada semáforo del eje."""

    def __init__(self, conn, eje: list, cada: int):
        self.conn, self.eje, self.cada = conn, eje, cada
        self.pistas = {t: list(dict.fromkeys(conn.trafficlight.getControlledLanes(t))) for t in eje}
        self.tiempos, self.cola, self.red = [], [], []
        self.llegados = 0

    def paso(self, t: float) -> None:
        self.llegados += self.conn.simulation.getArrivedNumber()
        if int(t) % self.cada:
            return
        c = self.conn
        self.tiempos.append(int(t))
        self.cola.append([sum(c.lane.getLastStepHaltingNumber(p) for p in self.pistas[tl]) for tl in self.eje])
        ids = c.vehicle.getIDList()
        detenidos = sum(1 for v in ids if c.vehicle.getSpeed(v) < 0.1)
        self.red.append({"en_red": len(ids), "detenidos": detenidos, "llegados": self.llegados,
                         "esperando_entrar": len(c.simulation.getPendingVehicles())})


def correr_clasico(nombre, scenario, profile, net, rou, eje, seed, end, cada):
    from run_baselines import build_controllers
    from tsc.controllers.base import PhaseSwitchingController
    from tsc.sumo_env import SumoSimulation

    ctrl = build_controllers(scenario, [nombre], profile)[0]()
    if isinstance(ctrl, PhaseSwitchingController):
        ctrl.tls_ids = eje
    sim = SumoSimulation(net_file=net, route_file=rou, end=end, seed=seed)
    with sim:
        ctrl.setup(sim)
        m = Muestreo(sim.conn, eje, cada)
        intervalo = max(1, int(getattr(ctrl, "decision_interval", 5)))
        t = 0
        while sim.running():
            for _ in range(intervalo):
                sim.step(1)
                t += 1
                m.paso(sim.time)
            ctrl.act(sim)
        ctrl.teardown(sim)
    return m


def correr_ppo(modelo, net, rou, eje, seed, end, cada):
    from eval_rl import leer_metadatos
    from stable_baselines3 import PPO

    from tsc.rl_env import make_parallel_env

    model = PPO.load(modelo, device="cpu")
    meta = leer_metadatos(modelo)
    env = make_parallel_env(net_file=net, route_file=rou, num_seconds=end, seed=seed, tls_ids=eje,
                            obs=meta.get("obs", "estandar"), delta_time=meta.get("delta_time", 5),
                            min_green=meta.get("min_green", 10), max_green=meta.get("max_green", 60))
    obs, _ = env.reset()
    inner = env.unwrapped.env
    m = Muestreo(inner.sumo, eje, cada)
    original = inner._sumo_step

    def paso_con_muestreo():
        original()
        m.paso(inner.sumo.simulation.getTime())

    inner._sumo_step = paso_con_muestreo
    dim = model.observation_space.shape[0]
    while env.agents:
        agentes = list(obs)
        lote = np.zeros((len(agentes), dim), dtype=np.float32)
        for i, a in enumerate(agentes):
            lote[i, : len(obs[a])] = obs[a]
        salidas, _ = model.predict(lote, deterministic=True)
        acciones = {a: accion_real(salidas[i], env.action_space(a).n) for i, a in enumerate(agentes)}
        obs, _, term, trunc, _ = env.step(acciones)
        if all(term.values()) or all(trunc.values()):
            break
    env.close()
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--controller", required=True, choices=[*CLASICOS, "ppo"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--replica", type=int, default=0)
    ap.add_argument("--end", type=int, default=3600)
    ap.add_argument("--cada", type=int, default=30, help="segundos entre muestras")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    net = os.path.join(args.scenario, "net.net.xml")
    rou = ruta_evaluacion(args.scenario, args.profile, args.replica, None)
    eje = controlled_tls(args.scenario, "eje")
    grupo, _ = geometria_eje(net, eje)

    # Orden y posición a lo largo del eje: de poniente a oriente, distancia acumulada
    import sumolib
    red = sumolib.net.readNet(net)
    centro = {}
    for tl in red.getTrafficLights():
        if tl.getID() in eje:
            p = [e.getToNode().getCoord() for e in tl.getEdges()]
            centro[tl.getID()] = (sum(x for x, _ in p) / len(p), sum(y for _, y in p) / len(p))
    eje = sorted(eje, key=lambda t: centro[t][0])
    pos, acum = [], 0.0
    for i, t in enumerate(eje):
        if i:
            acum += math.dist(centro[eje[i - 1]], centro[t])
        pos.append(round(acum))

    if args.controller == "ppo":
        m = correr_ppo(args.model, net, rou, eje, args.replica, args.end, args.cada)
    else:
        m = correr_clasico(args.controller, args.scenario, args.profile, net, rou, eje,
                           args.replica, args.end, args.cada)

    salida = {"controlador": args.controller, "perfil": args.profile, "replica": args.replica,
              "rutas": rou, "modelo": args.model, "cada_s": args.cada, "semaforos": eje,
              "posicion_m": pos, "avenida": [grupo.get(t, "") for t in eje],
              "coordenadas": [[round(c) for c in centro[t]] for t in eje],
              "tiempos": m.tiempos, "cola": m.cola, "red": m.red}
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False)
    total = [sum(c) for c in m.cola]
    print(f"OK {args.controller}: {len(m.tiempos)} muestras, cola media en el eje {np.mean(total):.1f} veh "
          f"-> {args.out}")


if __name__ == "__main__":
    main()
