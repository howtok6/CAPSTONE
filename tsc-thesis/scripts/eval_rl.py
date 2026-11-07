#!/usr/bin/env python3
"""Evalúa una política entrenada con el MISMO protocolo que los baselines.

Punto metodológico importante: las métricas primarias se leen del archivo
`tripinfo` de SUMO, exactamente igual que en `run_baselines.py`. Así, la
comparación entre el agente aprendido y los controladores clásicos no depende
de cómo cada uno recorre el bucle de simulación.

    python scripts/eval_rl.py --scenario scenarios/grid4x4 \
        --model models/grid4x4/ppo_wait.zip --seeds 8
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# libsumo corre SUMO dentro del proceso: varias veces más rápido que TraCI
if __name__ == "__main__":
    os.environ.setdefault("LIBSUMO_AS_TRACI", "1")

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np  # noqa: E402

from tsc.metrics import (  # noqa: E402
    GreenSwitchCounter,
    combine_delay,
    end_state_from_conn,
    parse_tripinfo,
    planned_departures,
)
from tsc.demand import ruta_evaluacion  # noqa: E402
from tsc.rl_env import accion_real, controlled_tls, make_parallel_env  # noqa: E402


def leer_metadatos(modelo: str) -> dict:
    """Metadatos del entrenamiento: <modelo>.json, o el de la corrida si es un checkpoint."""
    base = modelo[:-4] if modelo.endswith(".zip") else modelo
    carpeta = os.path.dirname(base)
    candidatos = [base + ".json"]
    if carpeta.endswith("_ckpt"):
        candidatos.append(carpeta[: -len("_ckpt")] + ".json")
    for ruta in candidatos:
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                return json.load(f)
    return {}


def evaluate(model, net, rou, seed, seconds, warmup, deterministic=True, use_waze_obs=False,
             tls_ids=None, obs_kind="estandar", delta_time=5, min_green=10, max_green=60) -> dict:
    tmp = tempfile.NamedTemporaryFile(suffix=".xml", delete=False)
    tmp.close()
    env = make_parallel_env(
        net_file=net,
        route_file=rou,
        num_seconds=seconds,
        seed=seed,
        use_waze_obs=use_waze_obs,
        tls_ids=tls_ids,
        obs=obs_kind,
        delta_time=delta_time,
        min_green=min_green,
        max_green=max_green,
    )
    env.unwrapped.env.additional_sumo_cmd = f"--tripinfo-output {tmp.name}"

    obs, _ = env.reset()
    regla = model if callable(model) else None  # regla fija: ver verificar_paridad.py
    obs_dim = 0 if regla else model.observation_space.shape[0]
    queues = []
    switches = GreenSwitchCounter()
    end_state = {}
    t = 0
    while env.agents:
        if regla is not None:
            actions = regla(env.unwrapped.env, env.agents)
        else:
            agentes = list(obs)
            lote = np.zeros((len(agentes), obs_dim), dtype=np.float32)
            for i, agent in enumerate(agentes):
                lote[i, : len(obs[agent])] = obs[agent]
            salidas, _ = model.predict(lote, deterministic=deterministic)
            actions = {agent: accion_real(salidas[i], env.action_space(agent).n)
                       for i, agent in enumerate(agentes)}
        obs, _, term, trunc, info = env.step(actions)
        delta = env.unwrapped.env.delta_time
        t += delta
        inner = env.unwrapped.env
        if t >= warmup:
            switches.update(inner.sumo, inner.ts_ids)
        if all(term.values()) or all(trunc.values()):
            # mismo cierre que el runner: demora de los que no terminaron
            end_state = end_state_from_conn(inner.sumo, inner.sumo.simulation.getTime(),
                                            planned_departures(rou))
        if t >= warmup:
            # se muestrea cada 10 s, igual que `StepSampler` en el runner de
            # los baselines: si los intervalos difieren, las colas medias no
            # son comparables entre controladores
            if t % 10 < delta:
                queues.append(
                    sum(ts.get_total_queued()
                        for ts in env.unwrapped.env.traffic_signals.values())
                )
        if all(term.values()) or all(trunc.values()):
            break
    env.close()

    res = {"controller": "ppo", "seed": seed, "rutas": rou}
    res.update(parse_tripinfo(tmp.name))
    res.update(end_state)
    combine_delay(res)
    res["phase_switches"] = switches.switches
    if queues:
        res["queue_mean"] = statistics.fmean(queues)
        res["queue_max"] = max(queues)
    res["throughput"] = res.get("vehicles_finished", 0) / max(1e-9, seconds / 3600.0)
    os.unlink(tmp.name)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--profile", default=None, help="Nombre del perfil de demanda (valle, punta_manana, punta_tarde, sobresaturado)")
    ap.add_argument("--routes", default=None, help="Ruta directa al archivo de rutas .rou.xml")
    ap.add_argument("--model", required=True)
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--seconds", type=int, default=3600)
    ap.add_argument("--warmup", type=int, default=300)
    ap.add_argument("--name", default="ppo")
    ap.add_argument("--merge-into", default=None,
                    help="JSON de baselines al que agregar estas filas")
    ap.add_argument("--stochastic", action="store_true",
                    help="muestrea la acción en vez de tomar la más probable")
    ap.add_argument("--use-waze-obs", action="store_true")
    ap.add_argument("--control", default="auto", choices=["auto", "eje", "todos"],
                    help="debe coincidir con el usado al entrenar")
    args = ap.parse_args()
    tls_ids = controlled_tls(args.scenario, args.control)

    from stable_baselines3 import PPO

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

    model = PPO.load(args.model, device="cpu")
    # La evaluación repite la especificación del entrenamiento, no la supone
    meta = leer_metadatos(args.model)
    entorno = {"obs_kind": meta.get("obs", "estandar"), "delta_time": meta.get("delta_time", 5),
               "min_green": meta.get("min_green", 10), "max_green": meta.get("max_green", 60)}
    print(f"Entorno de evaluación: {entorno}")

    rows = []
    for seed in range(args.seeds):
        rou_k = rou if args.routes else ruta_evaluacion(args.scenario, args.profile, seed, rou)
        r = evaluate(model, net, rou_k, seed, args.seconds, args.warmup,
                     deterministic=not args.stochastic, use_waze_obs=args.use_waze_obs,
                     tls_ids=tls_ids, **entorno)
        r["controller"] = args.name
        rows.append(r)
        print(f"  {args.name:12s} seed={seed:2d}  "
              f"delayAll={r.get('delay_all_mean', float('nan')):7.2f}  "
              f"timeLoss={r.get('time_loss_mean', float('nan')):6.2f}  "
              f"queue={r.get('queue_mean', float('nan')):6.2f}  "
              f"fin={r.get('vehicles_finished', 0)}  cambios={r.get('phase_switches', 0)}", flush=True)

    tag = f"_{args.profile}" if args.profile else ""
    target = args.merge_into or os.path.join(
        "results", f"{os.path.basename(args.scenario)}{tag}_baselines.json"
    )
    existing = json.load(open(target)) if os.path.exists(target) else []
    existing = [r for r in existing if r.get("controller") != args.name]
    existing.extend(rows)
    with open(target, "w") as fh:
        json.dump(existing, fh, indent=2)
    print(f"\nOK  resultados agregados -> {target}")


if __name__ == "__main__":
    main()
