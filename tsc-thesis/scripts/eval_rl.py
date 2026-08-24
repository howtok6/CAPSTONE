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

import numpy as np  # noqa: E402

from tsc.metrics import parse_tripinfo  # noqa: E402
from tsc.rl_env import make_parallel_env  # noqa: E402


def evaluate(model, net, rou, seed, seconds, warmup, deterministic=True) -> dict:
    tmp = tempfile.NamedTemporaryFile(suffix=".xml", delete=False)
    tmp.close()
    env = make_parallel_env(
        net_file=net,
        route_file=rou,
        num_seconds=seconds,
        seed=seed,
    )
    env.unwrapped.env.additional_sumo_cmd = f"--tripinfo-output {tmp.name}"

    obs, _ = env.reset()
    obs_dim = model.observation_space.shape[0]
    queues = []
    t = 0
    while env.agents:
        actions = {}
        for agent, o in obs.items():
            padded = np.zeros(obs_dim, dtype=np.float32)
            padded[: len(o)] = o
            a, _ = model.predict(padded, deterministic=deterministic)
            n_actions = env.action_space(agent).n
            actions[agent] = int(a) % n_actions   # deshace el padding de acciones
        obs, _, term, trunc, info = env.step(actions)
        delta = env.unwrapped.env.delta_time
        t += delta
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

    res = {"controller": "ppo", "seed": seed}
    res.update(parse_tripinfo(tmp.name))
    if queues:
        res["queue_mean"] = statistics.fmean(queues)
        res["queue_max"] = max(queues)
    res["throughput"] = res.get("vehicles_finished", 0) / max(1e-9, seconds / 3600.0)
    os.unlink(tmp.name)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--seconds", type=int, default=3600)
    ap.add_argument("--warmup", type=int, default=300)
    ap.add_argument("--name", default="ppo")
    ap.add_argument("--merge-into", default=None,
                    help="JSON de baselines al que agregar estas filas")
    args = ap.parse_args()

    from stable_baselines3 import PPO

    net = os.path.join(args.scenario, "net.net.xml")
    rou = os.path.join(args.scenario, "routes.rou.xml")
    model = PPO.load(args.model, device="cpu")

    rows = []
    for seed in range(args.seeds):
        r = evaluate(model, net, rou, seed, args.seconds, args.warmup)
        r["controller"] = args.name
        rows.append(r)
        print(f"  {args.name:12s} seed={seed:2d}  "
              f"timeLoss={r.get('time_loss_mean', float('nan')):6.2f}  "
              f"queue={r.get('queue_mean', float('nan')):6.2f}")

    target = args.merge_into or os.path.join(
        "results", f"{os.path.basename(args.scenario)}_baselines.json"
    )
    existing = json.load(open(target)) if os.path.exists(target) else []
    existing = [r for r in existing if r.get("controller") != args.name]
    existing.extend(rows)
    with open(target, "w") as fh:
        json.dump(existing, fh, indent=2)
    print(f"\nOK  resultados agregados → {target}")


if __name__ == "__main__":
    main()
