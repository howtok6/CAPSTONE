#!/usr/bin/env python3
"""Mide cuánto tarda una actualización de PPO (sin SUMO) en CPU y en GPU.

    .venv\\Scripts\\python.exe scripts/medir_actualizacion_ppo.py --agentes 206 487

Arma un lote del mismo tamaño que el de train_rl.py (n_steps 256 × agentes, minilotes de 256,
10 épocas, MLP 64-64) con observaciones al azar y cronometra `model.train()`, que es lo que
corre entre dos recolecciones. Sirve para decidir si conviene --device cuda: la simulación
siempre corre en CPU, pero la actualización es ~la mitad del tiempo de entrenamiento con
cientos de agentes, y en CPU usa un solo hilo (th.set_num_threads(1)).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def medir(device: str, agentes: int, dim: int, mappo: bool, repeticiones: int) -> float:
    import gymnasium as gym
    import torch as th
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv

    th.set_num_threads(1)

    class Falso(gym.Env):
        observation_space = gym.spaces.Box(0.0, 1.0, (dim,), np.float32)
        action_space = gym.spaces.Discrete(4)

        def reset(self, seed=None, options=None):
            return self.observation_space.sample(), {}

        def step(self, a):
            return self.observation_space.sample(), 0.0, False, False, {}

    politica = "MlpPolicy"
    if mappo:
        from tsc.mappo import MaskedActorCriticPolicy
        politica = MaskedActorCriticPolicy
    env = DummyVecEnv([Falso])
    # Un solo entorno con n_steps = 256 × agentes: mismo tamaño de lote y de minilote
    model = PPO(politica, env, n_steps=256 * agentes, batch_size=256, n_epochs=10, device=device, verbose=0)
    from stable_baselines3.common.logger import configure
    model.set_logger(configure(None, []))  # train() registra métricas; sin logger falla
    buf = model.rollout_buffer
    rng = np.random.default_rng(0)
    buf.reset()
    buf.observations[:] = rng.random(buf.observations.shape, dtype=np.float32)
    buf.actions[:] = rng.integers(0, 4, buf.actions.shape)
    buf.rewards[:] = rng.normal(size=buf.rewards.shape)
    buf.values[:] = rng.normal(size=buf.values.shape)
    buf.log_probs[:] = -1.386
    buf.episode_starts[:] = 0
    buf.compute_returns_and_advantage(last_values=th.zeros(1), dones=np.zeros(1))
    buf.full = True
    tiempos = []
    for _ in range(repeticiones):
        buf.generator_ready = False
        model._n_updates = 0
        t0 = time.perf_counter()
        model.train()
        if device == "cuda":
            th.cuda.synchronize()
        tiempos.append(time.perf_counter() - t0)
    return min(tiempos)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--agentes", type=int, nargs="+", default=[206, 487])
    ap.add_argument("--repeticiones", type=int, default=2)
    a = ap.parse_args()
    import torch as th

    dispositivos = ["cpu"] + (["cuda"] if th.cuda.is_available() else [])
    print(f"torch {th.__version__} · cuda {th.cuda.is_available()}"
          f"{' · ' + th.cuda.get_device_name(0) if th.cuda.is_available() else ''}", flush=True)
    res = []
    for agentes in a.agentes:
        for mappo, dim in ((False, 22), (True, 33)):
            for d in dispositivos:
                s = medir(d, agentes, dim, mappo, a.repeticiones)
                fila = {"agentes": agentes, "algo": "mappo" if mappo else "ippo", "device": d, "segundos": round(s, 1)}
                res.append(fila)
                print(json.dumps(fila), flush=True)
    os.makedirs("results", exist_ok=True)
    json.dump(res, open(os.path.join("results", "medicion_actualizacion_ppo.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
